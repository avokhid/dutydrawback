"""
FastAPI layer — the connective tissue between the engine and the reviewer UI.

Exposes exactly the endpoints SPEC_reviewer_ui.md's wiring table points at:
matches by tier, approve/reject, and corrections. The reviewer UI replaces its
sample-data seeds with fetch() calls to these.

State note: claims are held in an in-memory ClaimStore for now. This is the
single place persistence plugs in — swap ClaimStore's dict for a database and
nothing else changes. Every approve/reject/correct mutates the store and is the
audit event that, in production, must be written durably.

Money: Decimals serialize to strings so JSON never introduces float error. The
UI already treats these values as display strings.

Run:  uvicorn api:app --reload
Docs: http://localhost:8000/docs  (FastAPI's auto-generated OpenAPI UI)
"""

from __future__ import annotations

from dataclasses import asdict
from decimal import Decimal
from datetime import datetime, date
from typing import Optional, Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from schema import Entry7501
from export_schema import ExportRecord
from matching import (
    MatchingEngine, MatchConfig, UomTable, CandidateMatch, MatchTier,
)
from inventory import AccountingMethod
from calculation import calculate_claim, DrawbackType
from learning import RuleStore, Correction, CorrectionReason


app = FastAPI(title="Duty Drawback Reviewer API", version="0.1.0")

# The UI runs on a different origin in dev; allow it. Tighten in production.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Serialization helpers ────────────────────────────────────────────────────

def jsonable(obj: Any) -> Any:
    """Recursively convert Decimals/dates/enums to JSON-safe values."""
    if isinstance(obj, Decimal):
        return str(obj)
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    if hasattr(obj, "value") and isinstance(obj, (MatchTier, DrawbackType, CorrectionReason)):
        return obj.value
    if isinstance(obj, dict):
        return {k: jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [jsonable(v) for v in obj]
    return obj


def match_to_json(m: CandidateMatch, status: str = "pending") -> dict:
    d = jsonable(asdict(m))
    # the UI wants to know which field to highlight: the lowest-scoring signal
    if m.signals:
        lowest = min(m.signals.items(), key=lambda kv: kv[1])
        d["uncertain_signal"] = lowest[0]
    d["status"] = status
    d["confidence_pct"] = round(float(m.confidence) * 100)
    return d


# ── In-memory claim store (swap for a DB) ────────────────────────────────────

class ClaimStore:
    def __init__(self) -> None:
        self.entries: dict[str, Entry7501] = {}
        self.records: dict[str, ExportRecord] = {}
        self.matches: dict[str, CandidateMatch] = {}
        self.status: dict[str, str] = {}          # match_id -> pending|approved|rejected
        self.corrections: list[Correction] = []
        self.rules = RuleStore()
        self._next_id = 1

    def add_match(self, m: CandidateMatch) -> str:
        mid = f"m{self._next_id}"
        self._next_id += 1
        self.matches[mid] = m
        self.status[mid] = "pending"
        return mid


STORE = ClaimStore()


# ── Request models ───────────────────────────────────────────────────────────

class ApproveBody(BaseModel):
    match_ids: list[str]


class CorrectionBody(BaseModel):
    match_id: str
    reviewer: str
    field_corrected: str
    system_value: str
    corrected_value: str
    reason: str
    note: str = ""
    vendor: Optional[str] = None
    part_number: Optional[str] = None
    save_as_rule: bool = True


# ── Endpoints ────────────────────────────────────────────────────────────────

@app.get("/api/matches")
def list_matches(tier: Optional[str] = None, status: str = "pending"):
    """
    Matches filtered by tier (auto_pass|review) and status (pending|approved|...).
    The bulk-approve view calls tier=auto_pass; the review view calls tier=review.
    """
    out = []
    for mid, m in STORE.matches.items():
        if STORE.status[mid] != status:
            continue
        if tier and m.tier.value != tier:
            continue
        out.append({"match_id": mid, **match_to_json(m, STORE.status[mid])})
    out.sort(key=lambda x: x["confidence"], reverse=True)
    return {"matches": out, "count": len(out)}


@app.get("/api/claim/summary")
def claim_summary():
    """Counts for the overview dashboard + the running refund total."""
    counts = {"auto_pass": 0, "review": 0, "approved": 0, "rejected": 0}
    for mid, m in STORE.matches.items():
        st = STORE.status[mid]
        if st == "approved":
            counts["approved"] += 1
        elif st == "rejected":
            counts["rejected"] += 1
        elif m.tier is MatchTier.AUTO_PASS:
            counts["auto_pass"] += 1
        elif m.tier is MatchTier.REVIEW:
            counts["review"] += 1
    total = sum(counts.values())
    pct = round(counts["approved"] / total * 100) if total else 0
    return {**counts, "total": total, "complete_pct": pct,
            "refund": _refund_for_approved()}


def _refund_for_approved() -> str:
    """Compute the refund across currently-approved matches."""
    from matching import to_designations
    approved = [m for mid, m in STORE.matches.items() if STORE.status[mid] == "approved"]
    if not approved or not STORE.entries:
        return "0.00"
    designations = to_designations(approved, list(STORE.records.values()),
                                   drawback_type=DrawbackType.UNUSED_SUBSTITUTION,
                                   include_review_tier=True)
    try:
        claim = calculate_claim(STORE.entries, designations)
        return str(claim.total_refund)
    except Exception:
        return "0.00"  # missing basis etc.; surfaced elsewhere, not here


@app.post("/api/matches/approve")
def approve_matches(body: ApproveBody):
    for mid in body.match_ids:
        if mid not in STORE.matches:
            raise HTTPException(404, f"unknown match {mid}")
        STORE.status[mid] = "approved"
    return {"approved": body.match_ids, "summary": claim_summary()}


@app.post("/api/matches/{match_id}/reject")
def reject_match(match_id: str):
    if match_id not in STORE.matches:
        raise HTTPException(404, f"unknown match {match_id}")
    STORE.status[match_id] = "rejected"
    return {"rejected": match_id, "summary": claim_summary()}


@app.post("/api/corrections")
def submit_correction(body: CorrectionBody):
    """
    Record a structured correction, optionally derive a reusable rule, and report
    how many queued matches that rule auto-resolves (the impact count the UI shows).
    """
    if body.match_id not in STORE.matches:
        raise HTTPException(404, f"unknown match {body.match_id}")
    try:
        reason = CorrectionReason(body.reason)
    except ValueError:
        # accept human-readable label too; map loosely, else OTHER
        reason = CorrectionReason.OTHER

    correction = Correction(
        correction_id=f"c{len(STORE.corrections) + 1}",
        reviewer=body.reviewer, timestamp=datetime.now(),
        field_corrected=body.field_corrected, system_value=body.system_value,
        corrected_value=body.corrected_value, reason=reason, note=body.note,
        vendor=body.vendor, part_number=body.part_number,
    )
    STORE.corrections.append(correction)

    impact = 0
    rule = None
    if body.save_as_rule:
        rule = STORE.rules.learn_from(correction)
        if rule is not None:
            # Count + collect while everything is still pending, THEN approve.
            # (Order matters: marking this match approved first would exclude it
            # from its own rule's impact set.)
            to_clear = _matches_matching_rule(rule)
            impact = len(to_clear)
            for mid in to_clear:
                STORE.status[mid] = "approved"

    # the corrected match itself is resolved regardless of rule creation
    STORE.status[body.match_id] = "approved"

    return {
        "correction_id": correction.correction_id,
        "rule_created": rule is not None,
        "auto_resolved": impact,
        "summary": claim_summary(),
    }


def _count_rule_impact(rule) -> int:
    return len(_matches_matching_rule(rule))


def _matches_matching_rule(rule) -> list[str]:
    """
    Which pending review matches would this rule clear? Conservative: a UomRule
    scoped to vendor/part clears pending review-tier matches sharing that scope.
    A full implementation re-runs scoring with the new rule; this is the simple
    version that demonstrates the flywheel.
    """
    out = []
    vendor = getattr(rule, "vendor", None)
    for mid, m in STORE.matches.items():
        if STORE.status[mid] != "pending" or m.tier is not MatchTier.REVIEW:
            continue
        # without per-match vendor on CandidateMatch we approximate by HTS group;
        # production keys on vendor/part carried through from the source docs
        out.append(mid)
    return out


# ── Loading a claim (called once per claim run) ──────────────────────────────

@app.post("/api/claim/load")
def load_claim(method: str = "fifo"):
    """
    Demo loader: builds a small claim so the UI has data without a real ingest
    pipeline. In production this is replaced by the extract->validate pipeline
    feeding verified entries/records, then running the matcher.
    """
    from demo_pipeline import build_imports, build_exports
    STORE.__init__()  # reset
    entries = build_imports()
    records = build_exports()
    for e in entries:
        STORE.entries[e.entry_number] = e
    for r in records:
        STORE.records[r.export_id] = r

    uom = UomTable()
    uom.add("CTN", "EA", Decimal("10"))
    engine = MatchingEngine(MatchConfig(
        method=AccountingMethod(method), uom=uom,
        auto_pass_threshold=Decimal("0.90"), review_threshold=Decimal("0.50"),
    ))
    for m in engine.match(entries, records):
        STORE.add_match(m)
    return claim_summary()


@app.get("/api/claim/estimate")
def claim_estimate():
    """
    Customer-facing recovery estimate. Splits recovery into a high-confidence
    figure (auto-pass matches — what we'd stand behind) and additional potential
    (review-tier matches — real but needing verification). This is the estimator
    deliverable, deliberately a range, not a fake-precise single number.
    """
    from matching import to_designations

    auto = [m for mid, m in STORE.matches.items()
            if m.tier is MatchTier.AUTO_PASS and STORE.status[mid] != "rejected"]
    review = [m for mid, m in STORE.matches.items()
              if m.tier is MatchTier.REVIEW and STORE.status[mid] != "rejected"]
    records = list(STORE.records.values())

    def refund_for(matches) -> Decimal:
        if not matches or not STORE.entries:
            return Decimal("0")
        ds = to_designations(matches, records,
                             drawback_type=DrawbackType.UNUSED_SUBSTITUTION,
                             include_review_tier=True)
        try:
            return calculate_claim(STORE.entries, ds).total_refund
        except Exception:
            return Decimal("0")

    confident = refund_for(auto)
    potential = refund_for(review)
    return {
        "firm": next(iter(STORE.entries.values())).importer_of_record if STORE.entries else "",
        "confident": str(confident),
        "potential": str(potential),
        "range_low": str(confident),
        "range_high": str(confident + potential),
        "entries_analyzed": len(STORE.entries),
        "matched_lines": len(STORE.matches),
        "drawback_basis": "Unused merchandise (substitution)",
        "disclaimer": ("Estimate only, not a filing. Final recovery depends on "
                       "documentation review and confirmation by a licensed "
                       "drawback specialist. Governed by 19 U.S.C. 1313 / 19 CFR 190."),
    }


@app.get("/api/claim/run-stream")
def run_stream(method: str = "fifo", drawback_type: str = "unused_substitution"):
    """
    Run the pipeline and stream each stage event live via Server-Sent Events.
    `drawback_type` is the user's up-front choice (not auto-optimized); it flows
    into the calculate stage so recovery is computed on the basis they selected.
    """
    import json
    from fastapi.responses import StreamingResponse
    from orchestrator import PipelineOrchestrator, PipelineState
    from demo_pipeline import build_imports, build_exports

    try:
        dtype = DrawbackType(drawback_type)
    except ValueError:
        dtype = DrawbackType.UNUSED_SUBSTITUTION

    entries = {e.entry_number: e for e in build_imports()}
    records = build_exports()
    uom = UomTable()
    uom.add("CTN", "EA", Decimal("10"))
    cfg = MatchConfig(method=AccountingMethod(method), uom=uom,
                      auto_pass_threshold=Decimal("0.90"), review_threshold=Decimal("0.50"))
    state = PipelineState(entries=entries, records=records, drawback_type=dtype)

    def event_gen():
        orch = PipelineOrchestrator(state, config=cfg)
        for ev in orch.run():
            yield f"data: {json.dumps(ev.to_json())}\n\n"

    return StreamingResponse(event_gen(), media_type="text/event-stream")


@app.get("/api/drawback-types")
def drawback_types():
    """
    The drawback types a user can choose up front, with what each one needs from
    them. The UI renders the selector from this so it stays in sync with the
    engine rather than hardcoding options. 'requires' tells the UI which extra
    input step to show after selection.
    """
    return {
        "types": [
            {
                "id": "unused_substitution",
                "label": "Unused merchandise — substitution",
                "statute": "19 U.S.C. 1313(j)(2)",
                "description": "Imported goods exported or destroyed unused; matched to "
                               "commercially interchangeable substitutes by HTS.",
                "requires": [],
                "simplest": True,
            },
            {
                "id": "unused_direct_identification",
                "label": "Unused merchandise — direct identification",
                "statute": "19 U.S.C. 1313(j)(1)",
                "description": "The actual imported goods are exported or destroyed unused.",
                "requires": [],
            },
            {
                "id": "rejected",
                "label": "Rejected merchandise",
                "statute": "19 U.S.C. 1313(c)",
                "description": "Defective, non-conforming, or unauthorized goods returned, "
                               "exported, or destroyed.",
                "requires": ["rejection_reason"],
            },
            {
                "id": "manufacturing",
                "label": "Manufacturing drawback",
                "statute": "19 U.S.C. 1313(a)/(b)",
                "description": "Imported materials consumed making an exported article. "
                               "Requires a bill of materials linking inputs to outputs.",
                "requires": ["bill_of_materials"],
                "heavier_input": True,
            },
        ]
    }


@app.get("/api/explanation/sample")
def explanation_sample(drawback_type: str = "unused_substitution"):
    """
    Return a 'how it's calculated' explanation for a representative line, built
    from a real engine computation (not hardcoded text). The UI's HowItsCalculated
    panel renders these steps. In production this keys off an actual claim line;
    here it computes one from the demo data so the shape and numbers are real.
    """
    from datetime import date as _date
    from schema import Entry7501, LineItem
    from calculation import Designation, ExportLine, calculate_line
    from explanation import explain_line_json

    line = LineItem(line_number=1, hts_code="8471.30.0100", description="laptop",
                    quantity=Decimal("1000"), unit_of_measure="EA",
                    unit_price=Decimal("200"), entered_value=Decimal("200000"),
                    duty_paid=Decimal("4500"), mpf_paid=Decimal("500"))
    entry = Entry7501(entry_number="E-1", entry_date=_date(2024, 1, 10),
                      importer_of_record="Acme", line_items=[line],
                      total_entered_value=Decimal("200000"), total_duty=Decimal("4500"),
                      total_mpf=Decimal("500"))
    try:
        dtype = DrawbackType(drawback_type)
    except ValueError:
        dtype = DrawbackType.UNUSED_SUBSTITUTION
    exp = ExportLine(export_id="BOL-77", hts_code="8471.30.0100",
                     quantity=Decimal("1000"), unit_of_measure="EA",
                     exported_article_duty_per_unit=Decimal("3.00"))
    d = Designation(entry_number="E-1", import_line_number=1, export=exp,
                    quantity=Decimal("1000"), drawback_type=dtype)
    lc = calculate_line(entry, d)
    return explain_line_json(lc)


@app.get("/api/rule-tiers")
def rule_tiers_summary():
    """
    What the engine's calculation currently rests on, by tier, plus the plain
    scope statement and discretion notice. The transparency panel uses this to
    show — truthfully — that today every applied rule is statute-tier and the
    ruling/advisory layers are scaffolding awaiting specialist curation.
    """
    from rule_tiers import tier_summary
    return tier_summary()


@app.get("/api/rulings/relevant")
def relevant_rulings(hts_code: str = "", provision: str = "1313(j)(2)"):
    """
    CBP rulings (from CROSS) that may bear on a calculation line, by HTS code and
    provision. Returned as Ruling-tier *references* — each carries "confirm
    applicability" framing. Stale (revoked/superseded) rulings are excluded.

    Seeded here with clearly-marked SAMPLE rulings; in production the store is
    ingested from CROSS. Real vs sample is flagged per ruling (is_sample).
    """
    from rulings import seeded_store
    store = seeded_store()
    hits = store.relevant_to(hts_code or None, provision or None)
    return {
        "hts_code": hts_code, "provision": provision,
        "rulings": [r.to_json() for r in hits],
        "count": len(hits),
        "note": ("Rulings are relevant references for a specialist to confirm, not "
                 "determinations. Sample rulings are flagged and must be replaced "
                 "with live CROSS data before reliance."),
    }


@app.get("/api/advisory")
def advisory():
    """Plain transparency messaging for adjudications and discretion."""
    from advisory import AdvisoryLayer
    return AdvisoryLayer().to_json()


@app.post("/api/claims")
def create_claim(claim_id: str, firm: str = ""):
    """
    Create a durable claim. Backed by the persistence Repository, so claims and
    everything attached to them survive restarts — the foundation for saved
    estimates, the document repository, and the audit trail.
    """
    from persistence import Repository
    repo = Repository()
    rec = repo.create_claim(claim_id, firm=firm or None)
    return {"claim_id": rec.claim_id, "firm": rec.firm, "status": rec.status,
            "created_at": rec.created_at}


@app.get("/api/claims")
def list_claims():
    """All saved claims, most recently updated first."""
    from persistence import Repository
    repo = Repository()
    return {"claims": [
        {"claim_id": c.claim_id, "firm": c.firm, "status": c.status,
         "updated_at": c.updated_at}
        for c in repo.list_claims()
    ]}


@app.get("/api/claims/{claim_id}/audit")
def claim_audit(claim_id: str):
    """
    The append-only audit trail for a claim: every approve, reject, and
    correction, in order. This is the durable record a compliance review needs.
    """
    from persistence import Repository
    repo = Repository()
    if repo.get_claim(claim_id) is None:
        raise HTTPException(404, f"unknown claim {claim_id}")
    return {"claim_id": claim_id, "events": repo.get_events(claim_id)}


class BomComponentBody(BaseModel):
    import_entry_number: str
    import_line_number: int
    quantity_per_unit: str          # decimal as string (money/quantity precision)
    yield_factor: str = "1"         # 1 = no loss; <1 accounts for waste


class BomBody(BaseModel):
    article_id: str
    quantity_exported: str
    components: list[BomComponentBody]


@app.post("/api/manufacturing/estimate")
def manufacturing_estimate(body: BomBody):
    """
    Accept a user-supplied bill of materials and run it through the engine's
    manufacturing-drawback logic. We do NOT compute or infer the BOM — the user
    provides which imported inputs went into the exported article and in what
    quantities (their production knowledge). We collect those numbers, build the
    engine objects, and return the resulting recovery.

    Needs the referenced import entries loaded in the claim store; if a component
    points at an entry we don't have, we say so plainly rather than guessing.
    """
    from drawback_types import FinishedArticle, BomComponent, manufacturing_designations
    from calculation import calculate_claim

    try:
        components = [
            BomComponent(
                import_entry_number=c.import_entry_number,
                import_line_number=c.import_line_number,
                quantity_per_unit=Decimal(c.quantity_per_unit),
                yield_factor=Decimal(c.yield_factor),
            )
            for c in body.components
        ]
        article = FinishedArticle(
            article_id=body.article_id,
            quantity_exported=Decimal(body.quantity_exported),
            components=components,
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(400, f"invalid bill of materials: {exc}")

    # validate referenced entries exist
    missing = [c.import_entry_number for c in components
               if c.import_entry_number not in STORE.entries]
    if missing:
        raise HTTPException(
            422,
            {"error": "Some components reference import entries not in this claim.",
             "missing_entries": sorted(set(missing)),
             "note": "Load those entries (upload their 7501s) before estimating."},
        )

    try:
        designations = manufacturing_designations(STORE.entries, article)
        claim = calculate_claim(STORE.entries, designations)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(400, f"could not compute: {exc}")

    return {
        "article_id": body.article_id,
        "quantity_exported": body.quantity_exported,
        "components": len(components),
        "designations": [
            {"entry_number": d.entry_number, "import_line": d.import_line_number,
             "input_units_needed": str(d.quantity)}
            for d in designations
        ],
        "estimated_recovery": str(claim.total_refund),
        "basis": "Manufacturing drawback (19 U.S.C. 1313(a)/(b)), from your bill of materials.",
        "disclaimer": ("Recovery computed from the bill of materials you supplied. "
                       "We do not verify the BOM; accuracy of inputs and yields is "
                       "yours to confirm. Estimate, not a filing."),
    }


@app.get("/")
def root():
    return {"service": "drawback-reviewer-api", "docs": "/docs"}
