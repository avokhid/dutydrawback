"""
Matching / entity-resolution engine.

The hard, differentiating part. Given verified import entries and verified
export records, decide which imports can be designated against which exports,
score how confident each match is, and emit Designation objects (which
calculation.py turns into a refund).

What this file implements (the buildable core):
  - HTS-based substitution matching (the primary legal mechanism).
  - Unit-of-measure reconciliation via a configurable conversion table.
  - A transparent, rules-based confidence score per candidate, with the same
    tiering the reviewer UI was designed around: high-confidence auto-pass,
    mid-confidence to the review queue, low-confidence rejected.
  - Drawing imports from the InventoryLedger in the elected accounting-method
    order, decrementing availability so units are never claimed twice.

What this file deliberately does NOT pretend to be:
  - A learned entity-resolution model. The "WIDGET-A" vs "Widget Assembly,
    Blue" description-similarity problem is approximated here with a simple
    normalized-token overlap; in production this is where a learned matcher or
    embedding similarity goes, trained on reviewer corrections. The score
    structure is built so that component can slot in without changing callers.

Confidence is a transparent weighted blend of independent signals, each in
[0,1]. We keep it interpretable on purpose: a reviewer (and an auditor) must be
able to see *why* a match scored what it did. A black-box score that can't be
explained is a liability in a compliance setting.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
from typing import Optional

from schema import Entry7501
from export_schema import ExportRecord, ExportLineItem
from inventory import InventoryLedger, AvailableLot, AccountingMethod
from calculation import Designation, ExportLine, DrawbackType


# --- Unit-of-measure conversion ---------------------------------------------
# Conversions are claimant/vendor-specific and must be confirmed, not guessed.
# This table is the hook; entries here are illustrative defaults. A reviewer's
# correction (the learning loop) writes new rows here scoped to vendor/part.

@dataclass(frozen=True)
class UomConversion:
    from_uom: str
    to_uom: str
    factor: Decimal     # quantity_in_to = quantity_in_from * factor


class UomTable:
    def __init__(self) -> None:
        self._rows: dict[tuple[str, str], Decimal] = {}

    def add(self, from_uom: str, to_uom: str, factor: Decimal) -> None:
        self._rows[(from_uom.upper(), to_uom.upper())] = factor
        # also store the inverse for convenience
        self._rows[(to_uom.upper(), from_uom.upper())] = Decimal("1") / factor

    def convert(self, qty: Decimal, from_uom: str, to_uom: str) -> Optional[Decimal]:
        fu, tu = from_uom.upper(), to_uom.upper()
        if fu == tu:
            return qty
        factor = self._rows.get((fu, tu))
        return None if factor is None else qty * factor


# --- Tiering ----------------------------------------------------------------

class MatchTier(str, Enum):
    AUTO_PASS = "auto_pass"     # high confidence, no human needed
    REVIEW = "review"           # uncertain, route to a reviewer
    REJECT = "reject"           # too weak to propose


# Thresholds are policy, set against a labeled test set (see the risk-score
# tuning discussion). These defaults are starting points, not measured values.
DEFAULT_AUTO_PASS_THRESHOLD = Decimal("0.90")
DEFAULT_REVIEW_THRESHOLD = Decimal("0.50")


@dataclass
class CandidateMatch:
    """A proposed import<->export match, scored and explained."""

    entry_number: str
    import_line_number: int
    export_id: str
    export_line_number: int
    hts_code: str
    matched_quantity: Decimal       # in import units, after UoM conversion
    confidence: Decimal             # 0..1
    tier: MatchTier
    signals: dict[str, Decimal] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)


def _normalize_tokens(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", text.lower()))


def _description_similarity(a: str, b: str) -> Decimal:
    """
    Jaccard token overlap as a transparent stand-in for a learned matcher.
    Returns 0..1. This is the seam where embedding similarity or a trained
    model plugs in later; callers only see the 0..1 score.
    """
    ta, tb = _normalize_tokens(a), _normalize_tokens(b)
    if not ta or not tb:
        return Decimal("0")
    inter = len(ta & tb)
    union = len(ta | tb)
    return Decimal(inter) / Decimal(union)


@dataclass
class MatchConfig:
    method: AccountingMethod = AccountingMethod.FIFO
    uom: UomTable = field(default_factory=UomTable)
    auto_pass_threshold: Decimal = DEFAULT_AUTO_PASS_THRESHOLD
    review_threshold: Decimal = DEFAULT_REVIEW_THRESHOLD
    # weights for the confidence blend; must sum to 1
    w_hts: Decimal = Decimal("0.5")
    w_desc: Decimal = Decimal("0.3")
    w_uom: Decimal = Decimal("0.2")


class MatchingEngine:
    def __init__(self, config: Optional[MatchConfig] = None):
        self.config = config or MatchConfig()
        self.ledger = InventoryLedger(self.config.method)

    def load_imports(self, entries: list[Entry7501]) -> None:
        for e in entries:
            self.ledger.load_entry(e)

    def _import_description(self, entry_lookup, entry_number, line_number) -> str:
        entry = entry_lookup[entry_number]
        for li in entry.line_items:
            if li.line_number == line_number:
                return li.description
        return ""

    def _score(
        self, lot: AvailableLot, import_desc: str, exp: ExportLineItem,
        converted_qty: Optional[Decimal]
    ) -> tuple[Decimal, dict[str, Decimal], list[str]]:
        c = self.config
        notes: list[str] = []

        # HTS signal: exact 10-digit match is the legal basis for substitution.
        hts_sig = Decimal("1") if (exp.hts_code and exp.hts_code == lot.hts_code) else Decimal("0")
        if exp.hts_code is None:
            notes.append("export has no HTS; substitution signal absent")

        # Description signal: transparent token overlap (learned matcher seam).
        desc_sig = _description_similarity(import_desc, exp.description)

        # UoM signal: 1 if we could reconcile units, 0 if no conversion known.
        if converted_qty is None:
            uom_sig = Decimal("0")
            notes.append(
                f"no UoM conversion {exp.unit_of_measure}->import units; "
                f"quantity not reconcilable"
            )
        else:
            uom_sig = Decimal("1")

        confidence = c.w_hts * hts_sig + c.w_desc * desc_sig + c.w_uom * uom_sig
        signals = {"hts": hts_sig, "description": desc_sig, "uom": uom_sig}
        return confidence, signals, notes

    def _tier(self, confidence: Decimal) -> MatchTier:
        if confidence >= self.config.auto_pass_threshold:
            return MatchTier.AUTO_PASS
        if confidence >= self.config.review_threshold:
            return MatchTier.REVIEW
        return MatchTier.REJECT

    def match_export_line(
        self, entry_lookup: dict[str, Entry7501], exp: ExportLineItem
    ) -> list[CandidateMatch]:
        """
        Find candidate import lots for one export line, in inventory order,
        consuming availability as we designate. Returns the matches proposed
        (auto-pass + review tiers); rejects are dropped.
        """
        proposals: list[CandidateMatch] = []
        remaining = exp.quantity

        # Substitution requires HTS match, so restrict candidates to that HTS
        # when the export has one. Without an export HTS, no substitution
        # candidates exist (direct-identification matching would use other keys,
        # which this rules core doesn't implement yet).
        lots = self.ledger.available_lots(hts_code=exp.hts_code)

        for lot in lots:
            if remaining <= 0:
                break
            import_desc = self._import_description(
                entry_lookup, lot.entry_number, lot.import_line_number
            )
            # Convert the export quantity into the import's unit of measure.
            # We need the import line's UoM; pull it from the entry.
            import_uom = self._import_uom(entry_lookup, lot)
            converted = self.config.uom.convert(remaining, exp.unit_of_measure, import_uom)

            confidence, signals, notes = self._score(lot, import_desc, exp, converted)
            tier = self._tier(confidence)
            if tier is MatchTier.REJECT:
                continue

            # Quantity we can actually designate from this lot, in import units.
            want = converted if converted is not None else remaining
            take = min(want, lot.available_quantity)
            if take <= 0:
                continue
            lot.consume(take)

            # Convert the taken quantity back to export units to decrement
            # the export's remaining demand correctly.
            back = self.config.uom.convert(take, import_uom, exp.unit_of_measure)
            remaining -= (back if back is not None else take)

            proposals.append(
                CandidateMatch(
                    entry_number=lot.entry_number,
                    import_line_number=lot.import_line_number,
                    export_id="",  # filled by caller that knows the record id
                    export_line_number=exp.line_number,
                    hts_code=lot.hts_code,
                    matched_quantity=take,
                    confidence=confidence,
                    tier=tier,
                    signals=signals,
                    notes=notes,
                )
            )
        return proposals

    def _import_uom(self, entry_lookup, lot: AvailableLot) -> str:
        entry = entry_lookup[lot.entry_number]
        for li in entry.line_items:
            if li.line_number == lot.import_line_number:
                return li.unit_of_measure
        return ""

    def match(
        self, entries: list[Entry7501], records: list[ExportRecord]
    ) -> list[CandidateMatch]:
        """Match all export lines across all records. Loads inventory first."""
        self.load_imports(entries)
        entry_lookup = {e.entry_number: e for e in entries}
        all_matches: list[CandidateMatch] = []
        for rec in records:
            for exp in rec.line_items:
                for m in self.match_export_line(entry_lookup, exp):
                    m.export_id = rec.export_id
                    all_matches.append(m)
        return all_matches


def to_designations(
    matches: list[CandidateMatch], records: list[ExportRecord],
    drawback_type: DrawbackType = DrawbackType.UNUSED_SUBSTITUTION,
    include_review_tier: bool = False,
) -> list[Designation]:
    """
    Convert accepted matches into Designation objects for calculation.py.

    By default only AUTO_PASS matches become designations; REVIEW-tier matches
    require human approval first (set include_review_tier=True to designate them
    provisionally, e.g. for an estimate before review).
    """
    exp_lookup = {
        (r.export_id, li.line_number): li
        for r in records for li in r.line_items
    }
    designations: list[Designation] = []
    for m in matches:
        if m.tier is MatchTier.REVIEW and not include_review_tier:
            continue
        if m.tier is MatchTier.REJECT:
            continue
        exp_li = exp_lookup[(m.export_id, m.export_line_number)]
        designations.append(
            Designation(
                entry_number=m.entry_number,
                import_line_number=m.import_line_number,
                export=ExportLine(
                    export_id=m.export_id,
                    hts_code=m.hts_code,
                    quantity=m.matched_quantity,
                    unit_of_measure="",  # import-unit basis already applied
                    exported_article_duty_per_unit=exp_li.exported_article_duty_per_unit,
                ),
                quantity=m.matched_quantity,
                drawback_type=drawback_type,
            )
        )
    return designations
