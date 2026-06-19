"""
Drawback calculation engine.

Operates on *verified* import entries (the objects schema.py produces and
validation.py has checked) plus *designations* — the decisions that tie a
specific imported line to a specific export. The engine does not decide what
matches what; that is the matching engine's job. It takes designations as
input and computes the refund they produce, applying the statutory rules.

Scope: unused-merchandise drawback under 19 U.S.C. 1313(j). This is the
simplest type and the right first one. The two rules that actually shape the
number are implemented here:

  1. The 99% rule. Drawback refunds 99% of the duties, taxes, and fees paid on
     the designated imported merchandise.

  2. The "lesser of" rule for substitution (1313(j)(2)). When the export is a
     *substituted* article (matched by HTS, not the same physical goods), the
     refund per unit is capped at the lesser of the duty attributable to the
     imported article vs. what would have been attributable to the exported
     article. Direct identification (1313(j)(1)) — the actual imported goods
     were exported — has no such cap.

IMPORTANT — domain validation, not just code. The mechanics here are faithful
to the statute as we discussed it, but the edge cases (per-unit apportionment
when an import line is split across several exports, MPF/HMF allocation
specifics, interaction with inventory accounting methods) are exactly the
"needs a licensed drawback specialist to confirm" territory flagged earlier.
Treat the numbers this produces as a defensible estimate to be validated, not
as a filing-ready figure. Where a rule has a known subtlety we have not pinned
down, the code raises rather than guessing silently.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal, ROUND_HALF_UP
from enum import Enum
from typing import Optional

from schema import Entry7501, LineItem


CENT = Decimal("0.01")
DRAWBACK_RATE = Decimal("0.99")  # 99%


def _money(d: Decimal) -> Decimal:
    return d.quantize(CENT, rounding=ROUND_HALF_UP)


class DrawbackType(str, Enum):
    UNUSED_DIRECT = "unused_direct_identification"      # 1313(j)(1)
    UNUSED_SUBSTITUTION = "unused_substitution"         # 1313(j)(2)


@dataclass
class ExportLine:
    """
    The export side of a designation. Minimal here — a full build would have
    its own verified schema like Entry7501. For the calculation we need the
    quantity exported and, for the substitution cap, the duty that would be
    attributable per unit to the exported article.
    """

    export_id: str
    hts_code: str
    quantity: Decimal
    unit_of_measure: str
    # Per-unit duty attributable to the EXPORTED article, used only for the
    # lesser-of cap under substitution. None for direct identification.
    exported_article_duty_per_unit: Optional[Decimal] = None


@dataclass
class Designation:
    """
    A decision: claim `quantity` units of import line `import_line_number`
    (within `entry_number`) against `export`. The matching engine produces
    these; the calculation engine consumes them.
    """

    entry_number: str
    import_line_number: int
    export: ExportLine
    quantity: Decimal                 # units designated (<= available on the line)
    drawback_type: DrawbackType


@dataclass
class LineCalculation:
    """The computed refund for one designation, with its full derivation."""

    entry_number: str
    import_line_number: int
    export_id: str
    drawback_type: DrawbackType
    quantity_designated: Decimal
    duties_taxes_fees_per_unit: Decimal     # on the imported article
    refund_before_cap: Decimal              # 99% * per-unit * qty
    cap_applied: bool
    cap_amount: Optional[Decimal]           # the lesser-of ceiling, if it bound
    refund: Decimal                         # final, after cap and rounding
    notes: list[str] = field(default_factory=list)


@dataclass
class ClaimCalculation:
    lines: list[LineCalculation] = field(default_factory=list)

    @property
    def total_refund(self) -> Decimal:
        return _money(sum((lc.refund for lc in self.lines), Decimal("0")))

    def summary(self) -> str:
        rows = [
            f"  entry {lc.entry_number} line {lc.import_line_number} "
            f"-> export {lc.export_id}: {lc.quantity_designated} units, "
            f"refund {lc.refund}"
            + (" (capped)" if lc.cap_applied else "")
            for lc in self.lines
        ]
        return "Claim calculation:\n" + "\n".join(rows) + \
            f"\n  TOTAL REFUND: {self.total_refund}"


def _find_line(entry: Entry7501, line_number: int) -> LineItem:
    for li in entry.line_items:
        if li.line_number == line_number:
            return li
    raise ValueError(f"line {line_number} not found in entry {entry.entry_number}")


def calculate_line(entry: Entry7501, designation: Designation) -> LineCalculation:
    """
    Compute the refund for a single designation against a verified entry.

    Per-unit basis: the duties/taxes/fees paid on the import line are spread
    across the line's quantity, then 99% of that per-unit amount is refunded
    for each designated unit. Under substitution, the per-unit refund is capped
    at the duty attributable to the exported article.
    """
    if designation.entry_number != entry.entry_number:
        raise ValueError("designation/entry mismatch")

    li = _find_line(entry, designation.import_line_number)
    notes: list[str] = []

    if designation.quantity <= 0:
        raise ValueError("designated quantity must be positive")
    if designation.quantity > li.quantity:
        raise ValueError(
            f"designated {designation.quantity} exceeds line quantity {li.quantity}"
        )

    # Duties, taxes, fees paid on this import line, per unit of the line.
    line_dtf = li.duty_paid + li.mpf_paid + li.hmf_paid
    per_unit_dtf = line_dtf / li.quantity   # keep full precision until the end

    refund_before_cap = DRAWBACK_RATE * per_unit_dtf * designation.quantity

    cap_applied = False
    cap_amount: Optional[Decimal] = None

    if designation.drawback_type is DrawbackType.UNUSED_SUBSTITUTION:
        per_unit_export = designation.export.exported_article_duty_per_unit
        if per_unit_export is None:
            # The lesser-of cap is mandatory under 1313(j)(2). Without the
            # exported article's duty basis we cannot compute it, and guessing
            # would produce a non-compliant figure. Refuse rather than fabricate.
            raise ValueError(
                "substitution drawback requires exported_article_duty_per_unit "
                "for the lesser-of cap; refusing to compute without it"
            )
        # Cap = 99% of the lesser of the two per-unit duty bases, times qty.
        lesser = min(per_unit_dtf, per_unit_export)
        cap_amount = DRAWBACK_RATE * lesser * designation.quantity
        if cap_amount < refund_before_cap:
            cap_applied = True
            notes.append(
                f"lesser-of cap bound: exported-article basis "
                f"{per_unit_export}/unit < imported basis {_money(per_unit_dtf)}/unit"
            )
    else:
        notes.append("direct identification: no lesser-of cap")

    refund = _money(cap_amount if cap_applied else refund_before_cap)

    return LineCalculation(
        entry_number=entry.entry_number,
        import_line_number=li.line_number,
        export_id=designation.export.export_id,
        drawback_type=designation.drawback_type,
        quantity_designated=designation.quantity,
        duties_taxes_fees_per_unit=_money(per_unit_dtf),
        refund_before_cap=_money(refund_before_cap),
        cap_applied=cap_applied,
        cap_amount=_money(cap_amount) if cap_amount is not None else None,
        refund=refund,
        notes=notes,
    )


def calculate_claim(
    entries: dict[str, Entry7501], designations: list[Designation]
) -> ClaimCalculation:
    """
    Compute a full claim across many designations.

    `entries` maps entry_number -> verified Entry7501. Designations against an
    unknown entry raise — every designation must reference a verified entry.

    A real engine would also enforce that the sum of designated quantities
    against any one import line does not exceed that line's quantity (you can't
    claim the same units twice). That cross-designation accounting belongs with
    the inventory layer (FIFO/LIFO/low-to-high) and is enforced here only at the
    single-designation level; the multi-designation guard is the next thing to
    add when the inventory layer lands.
    """
    claim = ClaimCalculation()
    for d in designations:
        entry = entries.get(d.entry_number)
        if entry is None:
            raise ValueError(f"no verified entry for {d.entry_number}")
        claim.lines.append(calculate_line(entry, d))
    return claim
