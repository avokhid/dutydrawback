"""
Correction-learning loop.

When a reviewer corrects a match in the structured correction form, the
correction is captured as structured data (field, corrected value, reason code,
scope). This module turns those corrections into *reusable rules* that
auto-resolve future similar cases — the flywheel that shrinks tomorrow's review
queue, and the same record that serves as the audit trail.

Two rule kinds, matching the two correction types we saw:
  - UomRule: "for vendor V part P, 1 carton = 10 units" -> feeds matching's
    UomTable so the same UoM ambiguity never reaches a human again.
  - AliasRule: "import desc 'WIDGET-A' and export desc 'Widget Assembly, Blue'
    are the same item" -> boosts the description signal for that pair.

Safety note we flagged: a rule scoped too broadly can silently push wrong
matches into the auto-pass pile. So every rule carries an explicit scope
(vendor/part), an origin (which correction created it), and is auditable. The
store supports listing what a rule would auto-resolve before it's applied, and
disabling a rule — the periodic spot-check the discussion called for.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Optional


class CorrectionReason(str, Enum):
    VENDOR_PACK_DIFFERS = "vendor_pack_configuration_differs"
    CONVERSION_WRONG_IN_SOURCE = "conversion_factor_wrong_in_source"
    PARTIAL_SHIPMENT = "partial_shipment_split_carton"
    REMEASURED = "remeasured_against_invoice"
    SAME_ITEM = "confirmed_same_item"
    OTHER = "other"


@dataclass
class Correction:
    """A single structured reviewer correction — the audit record."""

    correction_id: str
    reviewer: str
    timestamp: datetime
    field_corrected: str
    system_value: str
    corrected_value: str
    reason: CorrectionReason
    note: str = ""
    # scope for any rule derived from this correction
    vendor: Optional[str] = None
    part_number: Optional[str] = None


@dataclass
class UomRule:
    vendor: Optional[str]
    part_number: Optional[str]
    from_uom: str
    to_uom: str
    factor: Decimal
    origin_correction_id: str
    enabled: bool = True


@dataclass
class AliasRule:
    vendor: Optional[str]
    import_description: str
    export_description: str
    origin_correction_id: str
    enabled: bool = True


class RuleStore:
    """
    Holds learned rules and applies them. In production this is backed by a
    database; here it's in-memory with the same interface so Cursor can swap the
    storage without touching callers.
    """

    def __init__(self) -> None:
        self.uom_rules: list[UomRule] = []
        self.alias_rules: list[AliasRule] = []

    # --- deriving rules from corrections ---

    def learn_from(self, correction: Correction) -> Optional[object]:
        """
        Turn a correction into a rule when it generalizes. Returns the created
        rule, or None if the correction is one-off (no scope, or a reason that
        shouldn't generalize).
        """
        if correction.field_corrected == "unit_of_measure" or correction.reason in (
            CorrectionReason.VENDOR_PACK_DIFFERS,
            CorrectionReason.CONVERSION_WRONG_IN_SOURCE,
        ):
            parsed = _parse_conversion(correction.corrected_value)
            if parsed and (correction.vendor or correction.part_number):
                from_uom, to_uom, factor = parsed
                rule = UomRule(
                    vendor=correction.vendor,
                    part_number=correction.part_number,
                    from_uom=from_uom, to_uom=to_uom, factor=factor,
                    origin_correction_id=correction.correction_id,
                )
                self.uom_rules.append(rule)
                return rule

        if correction.reason is CorrectionReason.SAME_ITEM:
            rule = AliasRule(
                vendor=correction.vendor,
                import_description=correction.system_value,
                export_description=correction.corrected_value,
                origin_correction_id=correction.correction_id,
            )
            self.alias_rules.append(rule)
            return rule

        return None  # one-off correction; recorded for audit, not generalized

    # --- applying rules ---

    def uom_factor(
        self, vendor: Optional[str], part: Optional[str],
        from_uom: str, to_uom: str
    ) -> Optional[Decimal]:
        """Most specific matching enabled rule wins (vendor+part > vendor > global)."""
        best: Optional[UomRule] = None
        best_specificity = -1
        for r in self.uom_rules:
            if not r.enabled:
                continue
            if r.from_uom.upper() != from_uom.upper() or r.to_uom.upper() != to_uom.upper():
                continue
            if r.vendor and r.vendor != vendor:
                continue
            if r.part_number and r.part_number != part:
                continue
            specificity = (1 if r.vendor else 0) + (1 if r.part_number else 0)
            if specificity > best_specificity:
                best, best_specificity = r, specificity
        return best.factor if best else None

    def disable_rule(self, origin_correction_id: str) -> int:
        """Disable all rules from a given correction. Returns count disabled."""
        n = 0
        for r in self.uom_rules + self.alias_rules:
            if r.origin_correction_id == origin_correction_id and r.enabled:
                r.enabled = False
                n += 1
        return n


def _parse_conversion(text: str) -> Optional[tuple[str, str, Decimal]]:
    """
    Parse '1 carton = 10 units' -> ('CARTON', 'UNIT', Decimal('10')).
    Tolerant of plurals and spacing. Returns None if unparseable.
    """
    import re
    m = re.match(
        r"\s*1\s+([a-zA-Z]+?)s?\s*=\s*([0-9.]+)\s+([a-zA-Z]+?)s?\s*$", text
    )
    if not m:
        return None
    from_uom, factor, to_uom = m.group(1), m.group(2), m.group(3)
    try:
        return from_uom.upper(), to_uom.upper(), Decimal(factor)
    except Exception:  # noqa: BLE001
        return None
