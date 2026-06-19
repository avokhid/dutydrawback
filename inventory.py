"""
Inventory accounting layer.

Sits underneath matching. Two jobs:

  1. Track how many units of each import line remain *available* to designate,
     so the same units can never be claimed twice (the multi-designation guard
     that calculation.py explicitly left as a stub).

  2. Order the available import lines by the accounting method the claimant
     elected — FIFO, LIFO, or low-to-high — so that when an export needs to be
     designated against imports, matching draws them in the correct, defensible
     order.

The accounting method matters for money: under substitution, low-to-high
deliberately designates the lowest-duty imports first (CBP's required method
for some substitution claims), while FIFO/LIFO order purely by date. The method
is a claimant election with regulatory constraints — which methods are
permitted for which drawback type is a domain question; this layer implements
the mechanics and leaves the "which is allowed when" policy to the rules config.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
from typing import Iterator

from schema import Entry7501, LineItem


class AccountingMethod(str, Enum):
    FIFO = "fifo"               # oldest imports designated first
    LIFO = "lifo"               # newest imports designated first
    LOW_TO_HIGH = "low_to_high" # lowest per-unit duty first


@dataclass
class AvailableLot:
    """An import line with a running available quantity."""

    entry_number: str
    import_line_number: int
    entry_date: object              # datetime.date; kept loose to avoid import
    hts_code: str
    per_unit_duty: Decimal
    total_quantity: Decimal
    available_quantity: Decimal

    def consume(self, qty: Decimal) -> Decimal:
        """Take up to `qty` from this lot; return the amount actually taken."""
        taken = min(qty, self.available_quantity)
        self.available_quantity -= taken
        return taken


class InventoryLedger:
    """
    Holds all import lots and hands them out in method order, decrementing
    availability as designations are made. One ledger per claim run.
    """

    def __init__(self, method: AccountingMethod):
        self.method = method
        self._lots: list[AvailableLot] = []

    def load_entry(self, entry: Entry7501) -> None:
        for li in entry.line_items:
            line_duty = li.duty_paid + li.mpf_paid + li.hmf_paid
            per_unit = (line_duty / li.quantity) if li.quantity else Decimal("0")
            self._lots.append(
                AvailableLot(
                    entry_number=entry.entry_number,
                    import_line_number=li.line_number,
                    entry_date=entry.entry_date,
                    hts_code=li.hts_code,
                    per_unit_duty=per_unit,
                    total_quantity=li.quantity,
                    available_quantity=li.quantity,
                )
            )

    def _ordered(self, candidates: list[AvailableLot]) -> list[AvailableLot]:
        if self.method is AccountingMethod.FIFO:
            return sorted(candidates, key=lambda l: l.entry_date)
        if self.method is AccountingMethod.LIFO:
            return sorted(candidates, key=lambda l: l.entry_date, reverse=True)
        if self.method is AccountingMethod.LOW_TO_HIGH:
            return sorted(candidates, key=lambda l: l.per_unit_duty)
        raise ValueError(f"unknown method {self.method}")

    def available_lots(self, hts_code: str | None = None) -> list[AvailableLot]:
        """
        Lots with remaining quantity, in method order. If `hts_code` is given,
        restrict to lots matching it (substitution requires HTS match).
        """
        cands = [
            l for l in self._lots
            if l.available_quantity > 0
            and (hts_code is None or l.hts_code == hts_code)
        ]
        return self._ordered(cands)

    def total_available(self, hts_code: str | None = None) -> Decimal:
        return sum(
            (l.available_quantity for l in self.available_lots(hts_code)),
            Decimal("0"),
        )
