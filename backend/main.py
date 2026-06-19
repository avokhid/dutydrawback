"""FastAPI application for the drawback extraction + validation pipeline."""

from __future__ import annotations

import os
import sys
from datetime import date
from pathlib import Path
from typing import Literal, Optional

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# Allow imports from project root (schema.py, validation.py)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.config import get_settings
from backend.reviewer_service import (
    approve_matches,
    compute_estimate,
    get_claim_state,
    get_stats,
    list_matches,
    reject_match,
    reset_claim_state,
    save_correction,
    send_to_review,
)
from backend.mock_extract import extract_from_pdf_stub
from extraction import extract_live
from validation import Finding, ValidationResult, validate_entry

app = FastAPI(title="Drawback Extraction API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class FindingOut(BaseModel):
    code: str
    severity: str
    message: str
    line_number: Optional[int] = None
    field: Optional[str] = None
    discrepancy: Optional[str] = None


class ValidationOut(BaseModel):
    ok: bool
    gates: list[FindingOut]
    warnings: list[FindingOut]


class ProcessResponse(BaseModel):
    entry: dict
    validation: ValidationOut


def _finding_to_dict(f: Finding) -> dict:
    return {
        "code": f.code,
        "severity": f.severity.value,
        "message": f.message,
        "line_number": f.line_number,
        "field": f.field,
        "discrepancy": str(f.discrepancy) if f.discrepancy is not None else None,
    }


def _validation_to_out(result: ValidationResult) -> ValidationOut:
    return ValidationOut(
        ok=result.ok,
        gates=[FindingOut(**_finding_to_dict(f)) for f in result.gates],
        warnings=[FindingOut(**_finding_to_dict(f)) for f in result.warnings],
    )


STATIC_DIR = Path(__file__).resolve().parent / "static"

# Serve vendored React/Babel + the reviewer HTML so the UI needs no build step.
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/")
def shell_app() -> FileResponse:
    """The default landing: the two-tab front door (importer estimate + reviewer
    console), each embedded as a real same-origin page. The reviewer console
    itself is served standalone at /reviewer (and embedded by the shell)."""
    return FileResponse(STATIC_DIR / "shell_live.html")


@app.get("/shell")
def shell_alias() -> FileResponse:
    """Alias for the front door (/)."""
    return FileResponse(STATIC_DIR / "shell_live.html")


@app.get("/reviewer")
def reviewer_app() -> FileResponse:
    """Serve the no-build reviewer console UI (vendored React, live data,
    same-origin). Also embedded as the shell's 'Reviewer console' tab."""
    return FileResponse(STATIC_DIR / "reviewer_live.html")


@app.get("/estimate")
def estimate_app() -> FileResponse:
    """Serve the no-build customer-facing recovery estimate (vendored React)."""
    return FileResponse(STATIC_DIR / "estimate_live.html")


@app.get("/activity")
def activity_app() -> FileResponse:
    """Serve the no-build live pipeline activity feed (vendored React + SSE)."""
    return FileResponse(STATIC_DIR / "activity_live.html")


@app.get("/upload")
def upload_app() -> FileResponse:
    """Serve the no-build document upload screen (front door of the estimate flow)."""
    return FileResponse(STATIC_DIR / "upload_live.html")


@app.get("/drawback-type")
def drawback_type_app() -> FileResponse:
    """Serve the no-build drawback-type selector (sits before the estimate run)."""
    return FileResponse(STATIC_DIR / "drawback_type_live.html")


@app.get("/how-calculated")
def how_calculated_app() -> FileResponse:
    """Serve the no-build 'how it's calculated' line derivation."""
    return FileResponse(STATIC_DIR / "how_calculated_live.html")


@app.get("/journey")
def journey_app() -> FileResponse:
    """Serve the no-build guided walkthrough of the whole estimate journey."""
    return FileResponse(STATIC_DIR / "journey_live.html")


@app.get("/bom")
def bom_app() -> FileResponse:
    """Serve the no-build bill-of-materials entry for manufacturing drawback."""
    return FileResponse(STATIC_DIR / "bom_live.html")


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/api/process", response_model=ProcessResponse)
async def process_entry(
    file: UploadFile = File(...),
    claim_date: Optional[str] = Form(None),
    mock_mode: Literal["clean", "corrupt", "live"] = Form("clean"),
) -> ProcessResponse:
    settings = get_settings()
    pdf_bytes = await file.read()

    if mock_mode == "live":
        if not settings.anthropic_api_key:
            raise HTTPException(
                status_code=400,
                detail="Live extraction requires ANTHROPIC_API_KEY in .env",
            )
        entry = extract_live(pdf_bytes, filename=file.filename or "upload.pdf")
    else:
        entry = extract_from_pdf_stub(pdf_bytes, mock_mode=mock_mode)

    parsed_claim_date: Optional[date] = None
    if claim_date:
        parsed_claim_date = date.fromisoformat(claim_date)
    else:
        parsed_claim_date = settings.default_claim_date

    result = validate_entry(entry, claim_date=parsed_claim_date)

    return ProcessResponse(
        entry=entry.model_dump(mode="json"),
        validation=_validation_to_out(result),
    )


class ApproveBody(BaseModel):
    ids: list[str]


class CorrectionBody(BaseModel):
    match_id: str
    field: str
    system_value: str
    corrected: str
    reason: str
    note: str = ""
    asRule: bool = False


@app.get("/api/claim/stats")
def claim_stats() -> dict:
    return get_stats(get_claim_state())


@app.get("/api/claim/estimate")
def claim_estimate() -> dict:
    return compute_estimate(get_claim_state())


@app.get("/api/claim/source-documents")
def claim_source_documents() -> dict:
    """The source documents the pipeline run will process (for the UI to show
    up front so the reviewer confirms these are their files)."""
    from demo_pipeline import build_exports, build_imports
    from orchestrator import PipelineOrchestrator, PipelineState

    state = PipelineState(
        entries={e.entry_number: e for e in build_imports()},
        records=build_exports(),
    )
    orch = PipelineOrchestrator(state)
    return {"documents": orch.source_documents()}


@app.get("/api/claim/run-stream")
def run_stream(method: str = "fifo", drawback_type: str = "unused_substitution") -> StreamingResponse:
    """Run the pipeline and stream each stage event as Server-Sent Events.

    Drives the orchestrator over the clean ``demo_pipeline`` dataset so the feed
    is a green end-to-end run. (The reviewer/estimate views use the richer
    ``demo_claim`` set, whose intentionally-mismatched entry totals would surface
    as validation gates here.)

    ``drawback_type`` is the user's up-front choice (not auto-optimized) and flows
    into the calculate stage. The engine computes the two unused bases; a type it
    can't yet compute (rejected / manufacturing, which need a reason / BOM step)
    falls back to the substitution basis, and the calculate event reports the
    basis actually used so the figure is never mislabeled.
    """
    import json
    from decimal import Decimal

    from calculation import DrawbackType
    from demo_pipeline import build_exports, build_imports
    from inventory import AccountingMethod
    from matching import MatchConfig, UomTable
    from orchestrator import PipelineOrchestrator, PipelineState

    try:
        dtype = DrawbackType(drawback_type)
    except ValueError:
        dtype = DrawbackType.UNUSED_SUBSTITUTION

    entries = {e.entry_number: e for e in build_imports()}
    records = build_exports()
    uom = UomTable()
    uom.add("CTN", "EA", Decimal("10"))
    cfg = MatchConfig(
        method=AccountingMethod(method),
        uom=uom,
        auto_pass_threshold=Decimal("0.90"),
        review_threshold=Decimal("0.50"),
    )
    state = PipelineState(
        entries=entries,
        records=records,
        claim_date=get_settings().default_claim_date,
        drawback_type=dtype,
        type_inputs={"requested": drawback_type},
    )

    def event_gen():
        orch = PipelineOrchestrator(state, config=cfg)
        for ev in orch.run():
            yield f"data: {json.dumps(ev.to_json())}\n\n"

    return StreamingResponse(event_gen(), media_type="text/event-stream")


@app.get("/api/drawback-types")
def drawback_types() -> dict:
    """The drawback bases a user can choose up front, with what each one needs.

    The selector UI renders from this so options stay in sync with the engine.
    ``estimable`` marks the bases the calculate engine computes today (the two
    unused types); ``rejected`` and ``manufacturing`` require extra input steps
    (a stated reason / a bill of materials) and are advertised but not yet wired
    into the auto-estimate — selecting them currently falls back to the
    substitution basis, reported as such in the run.
    """
    from calculation import DrawbackType

    estimable = {DrawbackType.UNUSED_SUBSTITUTION.value, DrawbackType.UNUSED_DIRECT.value}
    types = [
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
    for t in types:
        t["estimable"] = t["id"] in estimable
    return {"types": types}


@app.get("/api/claim/explanation")
def claim_explanation(line: int = 0, drawback_type: str = "unused_substitution") -> dict:
    """A step-by-step derivation of one refund line — the real arithmetic the
    engine computed, each cited step tagged with how settled its rule is.

    Built over the clean ``demo_pipeline`` claim so the figure matches the
    activity-feed run. ``explain_line_json`` narrates the engine's
    ``LineCalculation``; it never re-computes, so the explanation can't drift
    from the number. ``transparency`` reports, honestly, that every applied rule
    is statute-tier today and what the estimate does not cover.
    """
    from decimal import Decimal

    from advisory import AdvisoryLayer
    from calculation import DrawbackType, calculate_claim
    from demo_pipeline import build_exports, build_imports
    from explanation import explain_line_json
    from inventory import AccountingMethod
    from matching import MatchConfig, MatchingEngine, UomTable, to_designations
    from rule_tiers import tier_summary
    from rulings import seeded_store

    try:
        dtype = DrawbackType(drawback_type)
    except ValueError:
        dtype = DrawbackType.UNUSED_SUBSTITUTION

    entries = {e.entry_number: e for e in build_imports()}
    records = build_exports()
    uom = UomTable()
    uom.add("CTN", "EA", Decimal("10"))
    engine = MatchingEngine(
        MatchConfig(
            method=AccountingMethod("fifo"),
            uom=uom,
            auto_pass_threshold=Decimal("0.90"),
            review_threshold=Decimal("0.50"),
        )
    )
    matches = engine.match(list(entries.values()), records)
    designations = to_designations(matches, records, drawback_type=dtype, include_review_tier=True)
    claim = calculate_claim(entries, designations)
    if not claim.lines:
        raise HTTPException(status_code=404, detail="no computed lines for this claim")

    idx = max(0, min(line, len(claim.lines) - 1))
    lc = claim.lines[idx]
    data = explain_line_json(lc)
    data["line_index"] = idx
    data["line_count"] = len(claim.lines)
    data["transparency"] = tier_summary()

    # Ruling-tier references + advisory transparency for THIS line. Rulings are
    # surfaced as "confirm applicability" references (they never change the math);
    # the advisory block names what the estimate can't tell you (adjudication
    # patterns, CBP discretion). Both are honest about being sample/empty today.
    from backend.reviewer_service import _fmt_hts

    entry = entries.get(lc.entry_number)
    hts = None
    if entry is not None:
        raw_hts = next(
            (li.hts_code for li in entry.line_items if li.line_number == lc.import_line_number),
            None,
        )
        # normalize to dotted 4-2-4 so it matches rulings keyed in that form
        hts = _fmt_hts(raw_hts) if raw_hts else None
    provision = _PROVISION_BY_TYPE.get(dtype.value)
    data["hts_code"] = hts
    data["provision"] = provision
    data["rulings"] = [r.to_json() for r in seeded_store().relevant_to(hts, provision)]
    data["advisory"] = AdvisoryLayer().to_json()
    return data


# drawback provision string per type, for matching rulings to a line.
_PROVISION_BY_TYPE = {
    "unused_substitution": "1313(j)(2)",
    "unused_direct_identification": "1313(j)(1)",
    "rejected": "1313(c)",
    "manufacturing": "1313(a)/(b)",
}


@app.get("/api/rulings/relevant")
def rulings_relevant(hts: Optional[str] = None, provision: Optional[str] = None) -> dict:
    """CBP rulings (from CROSS) that may bear on a line, as Ruling-tier references
    — each marked 'confirm applicability', never as a determination. Stale
    (revoked/superseded) rulings are excluded. Ships with clearly-flagged samples
    until a live CROSS ingest replaces them."""
    from rulings import seeded_store

    store = seeded_store()
    hits = store.relevant_to(hts, provision)
    return {"rulings": [r.to_json() for r in hits], "count": len(hits)}


@app.get("/api/advisory")
def advisory_layer() -> dict:
    """The advisory transparency block: adjudication patterns (not a comprehensive
    engine — public data can't support one honestly) and CBP discretion (out of
    scope by nature). Plain messages the UI shows up front rather than burying."""
    from advisory import AdvisoryLayer

    return AdvisoryLayer().to_json()


@app.get("/api/claim/import-lines")
def claim_import_lines() -> dict:
    """The import entry lines loaded in the claim, for the BOM picker to reference.

    Manufacturing drawback ties imported inputs to the exported article by entry
    + line (not HTS substitution), so the BOM form lets the user pick from the
    real loaded 7501 lines rather than typing entry numbers. Sourced from the same
    demo entries the rest of the pipeline runs on."""
    from demo_pipeline import build_imports

    lines = []
    for e in build_imports():
        for li in e.line_items:
            qty = f"{li.quantity:,.0f}" if li.quantity == li.quantity.to_integral() else str(li.quantity)
            lines.append({
                "entry_number": e.entry_number,
                "line_number": li.line_number,
                "hts_code": li.hts_code,
                "description": li.description,
                "label": f"{li.description} · {li.hts_code} · {qty} {li.unit_of_measure}",
            })
    return {"import_lines": lines}


class BomComponentBody(BaseModel):
    import_entry_number: str
    import_line_number: int
    quantity_per_unit: str          # decimal-as-string (quantity precision)
    yield_factor: str = "1"         # 1 = no loss; <1 accounts for waste


class BomBody(BaseModel):
    article_id: str
    quantity_exported: str
    components: list[BomComponentBody]


@app.post("/api/manufacturing/estimate")
def manufacturing_estimate(body: BomBody) -> dict:
    """Run a user-supplied bill of materials through the engine's manufacturing-
    drawback logic. We do NOT compute or infer the BOM — the user supplies which
    imported inputs went into the exported article and in what quantities (their
    production knowledge); we build the engine objects from exactly those numbers
    and return the resulting recovery. Components referencing entries not loaded in
    the claim are reported plainly rather than guessed at."""
    from decimal import Decimal, InvalidOperation

    from calculation import calculate_claim
    from demo_pipeline import build_imports
    from drawback_types import BomComponent, FinishedArticle, manufacturing_designations

    entries = {e.entry_number: e for e in build_imports()}

    try:
        components = [
            BomComponent(
                import_entry_number=c.import_entry_number,
                import_line_number=c.import_line_number,
                quantity_per_unit=Decimal(c.quantity_per_unit),
                yield_factor=Decimal(c.yield_factor or "1"),
            )
            for c in body.components
        ]
        article = FinishedArticle(
            article_id=body.article_id,
            quantity_exported=Decimal(body.quantity_exported),
            components=components,
        )
    except (InvalidOperation, ValueError) as exc:
        raise HTTPException(status_code=400, detail=f"invalid bill of materials: {exc}")

    missing = sorted({c.import_entry_number for c in components if c.import_entry_number not in entries})
    if missing:
        raise HTTPException(
            status_code=422,
            detail={
                "error": "Some components reference import entries not in this claim.",
                "missing_entries": missing,
                "note": "Load those entries (upload their 7501s) before estimating.",
            },
        )

    try:
        designations = manufacturing_designations(entries, article)
        claim = calculate_claim(entries, designations)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=f"could not compute: {exc}")

    return {
        "article_id": body.article_id,
        "quantity_exported": body.quantity_exported,
        "components": len(components),
        "designations": [
            {
                "entry_number": d.entry_number,
                "import_line": d.import_line_number,
                "input_units_needed": str(d.quantity),
            }
            for d in designations
        ],
        "estimated_recovery": str(claim.total_refund),
        "basis": "Manufacturing drawback (19 U.S.C. 1313(a)/(b)), from your bill of materials.",
        "disclaimer": (
            "Recovery computed from the bill of materials you supplied. We do not "
            "verify the BOM; accuracy of inputs and yields is yours to confirm. "
            "Estimate, not a filing."
        ),
    }


class CreateClaimBody(BaseModel):
    claim_id: str
    firm: Optional[str] = None


def _repository():
    """Persistence repository, DB path from settings/env (defaults to drawback.db)."""
    from persistence import Repository

    db_path = os.environ.get("DRAWBACK_DB", "drawback.db")
    return Repository(db_path)


@app.post("/api/claims")
def create_claim(body: CreateClaimBody) -> dict:
    """Create a durable claim. Backed by the persistence Repository, so claims and
    everything attached to them survive restarts — the foundation for saved
    estimates, the document repository, and the audit trail."""
    rec = _repository().create_claim(body.claim_id, firm=body.firm)
    return {"claim_id": rec.claim_id, "firm": rec.firm, "status": rec.status,
            "created_at": rec.created_at}


@app.get("/api/claims")
def list_claims() -> dict:
    """All saved claims, most recently updated first."""
    return {"claims": [
        {"claim_id": c.claim_id, "firm": c.firm, "status": c.status,
         "updated_at": c.updated_at}
        for c in _repository().list_claims()
    ]}


@app.get("/api/claims/{claim_id}/audit")
def claim_audit(claim_id: str) -> dict:
    """The append-only audit trail for a claim: every approve, reject, and
    correction, in order — the durable record a compliance review needs."""
    repo = _repository()
    if repo.get_claim(claim_id) is None:
        raise HTTPException(status_code=404, detail=f"unknown claim {claim_id}")
    return {"claim_id": claim_id, "events": repo.get_events(claim_id)}


@app.get("/api/matches")
def get_matches(tier: Literal["auto_pass", "review"] = "auto_pass") -> list[dict]:
    return list_matches(get_claim_state(), tier)


@app.post("/api/matches/approve")
def approve_bulk(body: ApproveBody) -> dict:
    count = approve_matches(get_claim_state(), body.ids)
    return {"approved": count, "stats": get_stats(get_claim_state())}


@app.post("/api/matches/send-to-review")
def route_to_review(body: ApproveBody) -> dict:
    count = send_to_review(get_claim_state(), body.ids)
    return {"routed": count, "stats": get_stats(get_claim_state())}


@app.post("/api/matches/{match_id}/approve")
def approve_one(match_id: str) -> dict:
    count = approve_matches(get_claim_state(), [match_id])
    if count == 0:
        raise HTTPException(status_code=404, detail="Match not found or already decided")
    return {"approved": count, "stats": get_stats(get_claim_state())}


@app.post("/api/matches/{match_id}/reject")
def reject_one(match_id: str) -> dict:
    if not reject_match(get_claim_state(), match_id):
        raise HTTPException(status_code=404, detail="Match not found or already decided")
    return {"stats": get_stats(get_claim_state())}


@app.post("/api/corrections")
def post_correction(body: CorrectionBody) -> dict:
    result = save_correction(get_claim_state(), body.model_dump())
    return {**result, "stats": get_stats(get_claim_state())}


@app.post("/api/claim/reset")
def reset_claim() -> dict:
    reset_claim_state()
    return get_stats(get_claim_state())
