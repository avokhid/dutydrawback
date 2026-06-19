"""
Additional drawback types: manufacturing (1313(a)/(b)) and rejected
merchandise (1313(c)).

These extend the calculation engine beyond unused-merchandise. They reuse the
99% and lesser-of machinery from calculation.py; what differs is *eligibility*
and, for manufacturing, the bill-of-materials layer that maps imported inputs
to exported finished articles.

DOMAIN CAVEAT (unchanged and important): the mechanics are faithful to the
statute as discussed, but manufacturing drawback in particular has substantial
edge cases — yield/waste accounting, multiple inputs per article, relative-value
apportionment when an import feeds several products — that need a licensed
drawback specialist to confirm. The BOM layer here is structurally correct but
deliberately simple; where a known subtlety isn't pinned down, it raises rather
than guessing.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional

from schema import Entry7501
from calculation import (
    Designation, ExportLine, DrawbackType, LineCalculation,
    calculate_line, _money, DRAWBACK_RATE, CENT,
)


# --- Manufacturing drawback -------------------------------------------------

@dataclass
class BomComponent:
    """One imported input consumed to make a finished article."""

    import_entry_number: str
    import_line_number: int
    quantity_per_unit: Decimal      # input units consumed per 1 finished unit
    # yield factor < 1 accounts for waste/scrap; 1.0 = no loss
    yield_factor: Decimal = Decimal("1")


@dataclass
class FinishedArticle:
    """An exported manufactured article and its bill of materials."""

    article_id: str
    quantity_exported: Decimal
    components: list[BomComponent] = field(default_factory=list)


def manufacturing_designations(
    entries: dict[str, Entry7501],
    article: FinishedArticle,
) -> list[Designation]:
    """
    Explode a finished article's BOM into per-component designations.

    For each component: input units needed = quantity_exported *
    quantity_per_unit / yield_factor. That quantity of the imported input is
    designated (direct identification of the consumed input). The 99% refund on
    those input duties then flows through calculate_line.
    """
    designations: list[Designation] = []
    for comp in article.components:
        if comp.yield_factor <= 0:
            raise ValueError("yield_factor must be positive")
        needed = (article.quantity_exported * comp.quantity_per_unit) / comp.yield_factor
        designations.append(
            Designation(
                entry_number=comp.import_entry_number,
                import_line_number=comp.import_line_number,
                export=ExportLine(
                    export_id=article.article_id,
                    hts_code="",  # manufacturing ties by BOM, not HTS substitution
                    quantity=needed,
                    unit_of_measure="",
                ),
                quantity=needed,
                # manufacturing direct identification of consumed input
                drawback_type=DrawbackType.UNUSED_DIRECT,
            )
        )
    return designations


# --- Rejected merchandise drawback ------------------------------------------

@dataclass
class RejectedMerchandise:
    """
    Imported goods that were defective, not conforming to specification, or
    shipped without consent, then exported or destroyed. Eligible under
    1313(c). Calculation is the 99% refund like unused-merchandise; the
    difference is the eligibility condition, captured here as an explicit reason.
    """

    entry_number: str
    import_line_number: int
    quantity: Decimal
    reason: str               # e.g. "defective", "not to specification"
    export_id: str


def rejected_designation(rm: RejectedMerchandise) -> Designation:
    if not rm.reason.strip():
        raise ValueError("rejected-merchandise drawback requires a stated reason")
    return Designation(
        entry_number=rm.entry_number,
        import_line_number=rm.import_line_number,
        export=ExportLine(
            export_id=rm.export_id,
            hts_code="",
            quantity=rm.quantity,
            unit_of_measure="",
        ),
        quantity=rm.quantity,
        drawback_type=DrawbackType.UNUSED_DIRECT,  # 99%, no substitution cap
    )
