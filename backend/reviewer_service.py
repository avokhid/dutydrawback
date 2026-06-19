"""In-memory reviewer state and API serialization."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Optional

from calculation import DrawbackType, calculate_claim
from export_schema import ExportRecord, ExportLineItem
from learning import Correction, CorrectionReason, RuleStore
from matching import CandidateMatch, MatchTier, to_designations
from schema import Entry7501, LineItem

from backend.demo_claim import run_demo_matching


class MatchStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


SIGNAL_TO_FIELD = {
    "hts": "hts",
    "description": "desc",
    "uom": "qty",
}

FIELD_LABELS = {
    "hts": "HTS",
    "desc": "Description",
    "qty": "Quantity / unit",
    "value": "Value",
    "date": "Date",
}

REASON_LABEL_TO_ENUM = {
    "Vendor pack configuration differs from default": CorrectionReason.VENDOR_PACK_DIFFERS,
    "Conversion factor wrong in source data": CorrectionReason.CONVERSION_WRONG_IN_SOURCE,
    "Partial shipment / split carton": CorrectionReason.PARTIAL_SHIPMENT,
    "Re-measured against commercial invoice": CorrectionReason.REMEASURED,
    "Confirmed same item": CorrectionReason.SAME_ITEM,
    "Other (specify in note)": CorrectionReason.OTHER,
}

FIELD_OPTION_TO_CORRECTION = {
    "Quantity / unit of measure": "unit_of_measure",
    "HTS classification": "hts_code",
    "Entered value": "entered_value",
    "Date / eligibility window": "entry_date",
    "Item identity (not the same product)": "description",
}


@dataclass
class StoredMatch:
    id: str
    match: CandidateMatch
    status: MatchStatus = MatchStatus.PENDING
    effective_tier: Optional[MatchTier] = None
    vendor: str = "ACME-MFG"
    part: str = ""


@dataclass
class ClaimState:
    claim_id: str = "DBK-2291"
    claimant: str = "Acme Imports LLC"
    entries: list[Entry7501] = field(default_factory=list)
    exports: list[ExportRecord] = field(default_factory=list)
    matches: list[StoredMatch] = field(default_factory=list)
    rule_store: RuleStore = field(default_factory=RuleStore)
    corrections: list[Correction] = field(default_factory=list)

    def entry_lookup(self) -> dict[str, Entry7501]:
        return {e.entry_number: e for e in self.entries}

    def export_lookup(self) -> dict[str, ExportRecord]:
        return {r.export_id: r for r in self.exports}


_state: Optional[ClaimState] = None


def get_claim_state() -> ClaimState:
    global _state
    if _state is None:
        _state = _init_demo_state()
    return _state


def reset_claim_state() -> ClaimState:
    global _state
    _state = _init_demo_state()
    return _state


def _init_demo_state() -> ClaimState:
    entries, exports, raw_matches = run_demo_matching()
    state = ClaimState(entries=entries, exports=exports)
    for m in raw_matches:
        if m.tier is MatchTier.REJECT:
            continue
        imp_line = _find_import_line(entries, m.entry_number, m.import_line_number)
        part = _part_from_description(imp_line.description if imp_line else "")
        state.matches.append(
            StoredMatch(
                id=_match_id(m),
                match=m,
                vendor="ACME-MFG",
                part=part,
            )
        )
    return state


def _match_id(m: CandidateMatch) -> str:
    return f"{m.entry_number}-{m.import_line_number}-{m.export_id}-{m.export_line_number}"


def _find_import_line(
    entries: list[Entry7501], entry_number: str, line_number: int
) -> Optional[LineItem]:
    for e in entries:
        if e.entry_number != entry_number:
            continue
        for li in e.line_items:
            if li.line_number == line_number:
                return li
    return None


def _find_export_line(
    exports: list[ExportRecord], export_id: str, line_number: int
) -> Optional[ExportLineItem]:
    for r in exports:
        if r.export_id != export_id:
            continue
        for li in r.line_items:
            if li.line_number == line_number:
                return li
    return None


def _part_from_description(desc: str) -> str:
    token = desc.split()[0] if desc else "UNKNOWN"
    return token.upper().replace(",", "")


def _effective_tier(stored: StoredMatch) -> MatchTier:
    if stored.effective_tier is not None:
        return stored.effective_tier
    return stored.match.tier


def _lowest_signal(signals: dict[str, Decimal]) -> str:
    return min(signals, key=lambda k: signals[k])


def _fmt_qty(qty: Decimal, uom: str) -> str:
    if qty == qty.to_integral():
        return f"{int(qty):,} {uom}"
    return f"{qty} {uom}"


def _fmt_money(val: Decimal) -> str:
    return f"${val:,.2f}"


def serialize_bulk_row(stored: StoredMatch, state: ClaimState) -> dict:
    m = stored.match
    imp = _find_import_line(state.entries, m.entry_number, m.import_line_number)
    exp = _find_export_line(state.exports, m.export_id, m.export_line_number)
    imp_desc = imp.description if imp else m.entry_number
    exp_desc = exp.description if exp else m.export_id
    imp_qty = _fmt_qty(m.matched_quantity, imp.unit_of_measure if imp else "EA")
    exp_qty = _fmt_qty(exp.quantity, exp.unit_of_measure) if exp else ""
    return {
        "id": stored.id,
        "imp": imp_desc,
        "impHts": m.hts_code,
        "impQty": imp_qty,
        "exp": exp_desc,
        "expHts": exp.hts_code if exp and exp.hts_code else m.hts_code,
        "expQty": exp_qty,
        "conf": float(m.confidence),
    }


def serialize_review_item(stored: StoredMatch, state: ClaimState) -> dict:
    m = stored.match
    imp = _find_import_line(state.entries, m.entry_number, m.import_line_number)
    exp = _find_export_line(state.exports, m.export_id, m.export_line_number)
    entry = state.entry_lookup().get(m.entry_number)
    export_rec = state.export_lookup().get(m.export_id)

    uncertain_key = _lowest_signal(m.signals)
    uncertain = SIGNAL_TO_FIELD.get(uncertain_key, "desc")

    imp_hts = imp.hts_code if imp else m.hts_code
    exp_hts = exp.hts_code if exp and exp.hts_code else ""
    imp_qty = _fmt_qty(imp.quantity, imp.unit_of_measure) if imp else ""
    exp_qty = _fmt_qty(exp.quantity, exp.unit_of_measure) if exp else ""
    imp_val = _fmt_money(imp.entered_value) if imp else ""
    exp_val = _fmt_money(exp.export_value) if exp else ""

    fields = {
        "hts": {
            "label": "HTS",
            "imp": imp_hts,
            "exp": exp_hts,
            "ok": m.signals.get("hts", Decimal("0")) >= Decimal("0.99"),
        },
        "desc": {
            "label": "Description",
            "imp": imp.description if imp else "",
            "exp": exp.description if exp else "",
            "ok": m.signals.get("description", Decimal("0")) >= Decimal("0.5"),
        },
        "qty": {
            "label": "Quantity / unit",
            "imp": imp_qty,
            "exp": exp_qty,
            "ok": m.signals.get("uom", Decimal("0")) >= Decimal("0.99"),
        },
        "value": {
            "label": "Value",
            "imp": imp_val,
            "exp": exp_val,
            "ok": True,
        },
        "date": {
            "label": "Date",
            "imp": str(entry.entry_date) if entry else "",
            "exp": str(export_rec.export_date) if export_rec else "",
            "ok": True,
            "note": "within 5yr",
        },
    }

    suggestion_text = m.notes[0] if m.notes else "Review suggested match"
    suggestion_detail = (
        f"Matched {m.matched_quantity} units at {int(m.confidence * 100)}% confidence"
    )
    if uncertain == "qty" and m.notes:
        suggestion_text = "Check unit conversion"
        suggestion_detail = "; ".join(m.notes)

    highlight = imp_qty if uncertain == "qty" else (imp.description if imp else "")
    proof_line = (
        f"{m.import_line_number:02d}  {imp_hts}  {imp_qty}  {imp.description if imp else ''}"
    )

    return {
        "id": stored.id,
        "vendor": stored.vendor,
        "part": stored.part,
        "conf": float(m.confidence),
        "uncertain": uncertain,
        "fields": fields,
        "suggestion": {"text": suggestion_text, "detail": suggestion_detail},
        "proof": {
            "source": f"7501 line {m.import_line_number}, entry {m.entry_number}",
            "line": proof_line,
            "highlight": highlight[:40] if highlight else "",
        },
    }


def compute_refund(state: ClaimState) -> Decimal:
    """Refund earned by the currently-approved matches, via the real calc engine.

    Follows the same path the offline pipeline does: approved matches ->
    designations -> ``calculate_claim``. Returns 0 when nothing is approved yet,
    or when a designation lacks a basis the calculator requires (e.g. the
    exported-article duty-per-unit for substitution) — the calculator refuses to
    guess, and we surface that as 0 here rather than a wrong figure.
    """
    approved = [s.match for s in state.matches if s.status is MatchStatus.APPROVED]
    if not approved or not state.entries:
        return Decimal("0.00")
    try:
        designations = to_designations(
            approved,
            state.exports,
            drawback_type=DrawbackType.UNUSED_SUBSTITUTION,
            include_review_tier=True,
        )
        if not designations:
            return Decimal("0.00")
        claim = calculate_claim(state.entry_lookup(), designations)
        return claim.total_refund
    except Exception:
        return Decimal("0.00")


def _fmt_hts(code: str) -> str:
    """Display HTS in dotted 4-2-4 form (8544.42.9090) when it's a 10-digit code."""
    digits = code.replace(".", "")
    if len(digits) == 10 and digits.isdigit():
        return f"{digits[:4]}.{digits[4:6]}.{digits[6:]}"
    return code


def _refund_and_lines(stored: list[StoredMatch], state: ClaimState, conf: str):
    """Run the calc engine over a set of matches; return (total, per-line rows).

    Returns (0, []) when there is nothing to compute or a designation lacks the
    basis the calculator requires — the engine refuses to fabricate, and we
    surface that as an empty contribution rather than a wrong number.
    """
    matches = [s.match for s in stored]
    if not matches or not state.entries:
        return Decimal("0"), []
    try:
        designations = to_designations(
            matches,
            state.exports,
            drawback_type=DrawbackType.UNUSED_SUBSTITUTION,
            include_review_tier=True,
        )
        claim = calculate_claim(state.entry_lookup(), designations)
    except Exception:
        return Decimal("0"), []

    rows: list[dict] = []
    for lc in claim.lines:
        imp = _find_import_line(state.entries, lc.entry_number, lc.import_line_number)
        rows.append(
            {
                "hts": _fmt_hts(imp.hts_code) if imp else lc.export_id,
                "desc": imp.description if imp else "",
                "duties": lc.duties_taxes_fees_per_unit * lc.quantity_designated,
                "refund": lc.refund,
                "capped": lc.cap_applied,
                "conf": conf,
            }
        )
    return claim.total_refund, rows


def _group_by_hts(rows: list[dict]) -> list[dict]:
    """Collapse per-designation rows into one row per HTS category for display."""
    grouped: dict[str, dict] = {}
    for r in rows:
        g = grouped.get(r["hts"])
        if g is None:
            g = {
                "hts": r["hts"],
                "desc": r["desc"],
                "duties": Decimal("0"),
                "refund": Decimal("0"),
                "capped": False,
                "conf": r["conf"],
            }
            grouped[r["hts"]] = g
        g["duties"] += r["duties"]
        g["refund"] += r["refund"]
        g["capped"] = g["capped"] or r["capped"]
    return [
        {
            "hts": g["hts"],
            "desc": g["desc"],
            "duties": f"{g['duties']:,.2f}",
            "refund": f"{g['refund']:,.2f}",
            "capped": g["capped"],
            "conf": g["conf"],
        }
        for g in grouped.values()
    ]


def _claim_period(state: ClaimState) -> str:
    dates = [e.entry_date for e in state.entries if e.entry_date]
    if not dates:
        return ""
    lo, hi = min(dates), max(dates)
    if lo.strftime("%b %Y") == hi.strftime("%b %Y"):
        return lo.strftime("%b %Y")
    return f"{lo.strftime('%b %Y')} \u2013 {hi.strftime('%b %Y')}"


def compute_estimate(state: ClaimState) -> dict:
    """Customer-facing recovery estimate.

    Splits recovery into a confident figure (auto-pass matches, what we'd stand
    behind) and additional potential (review-tier matches — real but unverified),
    presented as a range. Rejected matches are excluded. Numbers come straight
    from ``calculate_claim``; the per-category breakdown is the engine's own
    per-line output grouped by HTS.
    """
    auto = [
        s
        for s in state.matches
        if _effective_tier(s) is MatchTier.AUTO_PASS and s.status is not MatchStatus.REJECTED
    ]
    review = [
        s
        for s in state.matches
        if _effective_tier(s) is MatchTier.REVIEW and s.status is not MatchStatus.REJECTED
    ]

    confident, auto_rows = _refund_and_lines(auto, state, "high")
    potential, review_rows = _refund_and_lines(review, state, "review")
    high = confident + potential
    confident_pct = int((confident / high * 100).to_integral_value()) if high else 0

    return {
        "firm": state.claimant,
        "period": _claim_period(state),
        "confident": f"{confident:,.2f}",
        "potential": f"{potential:,.2f}",
        "rangeLow": f"{confident:,.2f}",
        "rangeHigh": f"{high:,.2f}",
        "confidentPct": confident_pct,
        "entriesAnalyzed": len(state.entries),
        "matchedLines": len(state.matches),
        "drawbackType": "Unused merchandise (substitution)",
        "lines": _group_by_hts(auto_rows) + _group_by_hts(review_rows),
        "disclaimer": (
            "Estimate only, not a filing. Final recovery depends on documentation "
            "review and confirmation by a licensed drawback specialist. Governed by "
            "19 U.S.C. 1313 / 19 CFR Part 190."
        ),
    }


def get_stats(state: ClaimState) -> dict:
    auto_pass = sum(
        1
        for s in state.matches
        if s.status is MatchStatus.PENDING and _effective_tier(s) is MatchTier.AUTO_PASS
    )
    review = sum(
        1
        for s in state.matches
        if s.status is MatchStatus.PENDING and _effective_tier(s) is MatchTier.REVIEW
    )
    approved = sum(1 for s in state.matches if s.status is MatchStatus.APPROVED)
    rejected = sum(1 for s in state.matches if s.status is MatchStatus.REJECTED)
    return {
        "claimId": state.claim_id,
        "claimant": state.claimant,
        "autoPass": auto_pass,
        "review": review,
        "approved": approved,
        "rejected": rejected,
        "totalProposed": len(state.matches),
        "refund": f"{compute_refund(state):,.2f}",
    }


def list_matches(state: ClaimState, tier: str) -> list[dict]:
    tier_enum = MatchTier.AUTO_PASS if tier == "auto_pass" else MatchTier.REVIEW
    pending = [
        s
        for s in state.matches
        if s.status is MatchStatus.PENDING and _effective_tier(s) is tier_enum
    ]
    if tier_enum is MatchTier.AUTO_PASS:
        return [serialize_bulk_row(s, state) for s in pending]
    return [serialize_review_item(s, state) for s in pending]


def approve_matches(state: ClaimState, ids: list[str]) -> int:
    count = 0
    for s in state.matches:
        if s.id in ids and s.status is MatchStatus.PENDING:
            s.status = MatchStatus.APPROVED
            count += 1
    return count


def reject_match(state: ClaimState, match_id: str) -> bool:
    for s in state.matches:
        if s.id == match_id and s.status is MatchStatus.PENDING:
            s.status = MatchStatus.REJECTED
            return True
    return False


def send_to_review(state: ClaimState, ids: list[str]) -> int:
    count = 0
    for s in state.matches:
        if s.id in ids and s.status is MatchStatus.PENDING:
            s.effective_tier = MatchTier.REVIEW
            count += 1
    return count


def save_correction(state: ClaimState, body: dict, reviewer: str = "reviewer") -> dict:
    match_id = body.get("match_id", "")
    stored = next((s for s in state.matches if s.id == match_id), None)

    reason_label = body.get("reason", "")
    reason = REASON_LABEL_TO_ENUM.get(reason_label, CorrectionReason.OTHER)
    field_label = body.get("field", "")
    field_corrected = FIELD_OPTION_TO_CORRECTION.get(field_label, field_label)

    correction = Correction(
        correction_id=str(uuid.uuid4()),
        reviewer=reviewer,
        timestamp=datetime.now(),
        field_corrected=field_corrected,
        system_value=body.get("system_value", ""),
        corrected_value=body.get("corrected", ""),
        reason=reason,
        note=body.get("note", ""),
        vendor=stored.vendor if stored else body.get("vendor"),
        part_number=stored.part if stored else body.get("part"),
    )
    state.corrections.append(correction)

    impact = 0
    if body.get("asRule"):
        rule = state.rule_store.learn_from(correction)
        if rule is not None and stored:
            to_resolve = [
                s
                for s in state.matches
                if s.status is MatchStatus.PENDING
                and _effective_tier(s) is MatchTier.REVIEW
                and s.vendor == stored.vendor
                and s.part == stored.part
            ]
            impact = len(to_resolve)
            for s in to_resolve:
                s.status = MatchStatus.APPROVED
    elif stored and stored.status is MatchStatus.PENDING:
        stored.status = MatchStatus.APPROVED

    return {"impact": impact, "correction_id": correction.correction_id}
