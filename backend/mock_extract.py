"""
Stub extraction for development without a live Anthropic API key.

Accepts PDF bytes but ignores content; mock_mode selects clean vs corrupt
scenario data lifted from demo.py.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from schema import Entry7501, LineItem


def make_entry(corrupt: bool) -> Entry7501:
    qty = Decimal("500")
    price = Decimal("248.00")
    value = Decimal("142000.00") if corrupt else Decimal("124000.00")
    line1 = LineItem(
        line_number=1,
        hts_code="8471.30.0100",
        description="Portable data processing machine",
        quantity=qty,
        unit_of_measure="EA",
        unit_price=price,
        entered_value=value,
        duty_paid=Decimal("0"),
        mpf_paid=Decimal("442.40"),
    )
    line2 = LineItem(
        line_number=2,
        hts_code="8544.42.9090",
        description="USB-C cable",
        quantity=Decimal("2000"),
        unit_of_measure="EA",
        unit_price=Decimal("3.50"),
        entered_value=Decimal("7000.00"),
        duty_paid=Decimal("182.00"),
        mpf_paid=Decimal("24.97"),
    )
    total_val = value + Decimal("7000.00")
    return Entry7501(
        entry_number="ABC-1234567",
        entry_date=date(2024, 3, 11),
        importer_of_record="Acme Imports LLC",
        port_of_entry="2704",
        line_items=[line1, line2],
        total_entered_value=total_val,
        total_duty=Decimal("182.00"),
        total_mpf=Decimal("467.37"),
    )


def extract_from_pdf_stub(pdf_bytes: bytes, mock_mode: str = "clean") -> Entry7501:
    """Return a mock Entry7501. PDF content is ignored until live extraction is wired."""
    _ = pdf_bytes
    corrupt = mock_mode == "corrupt"
    return make_entry(corrupt=corrupt)
