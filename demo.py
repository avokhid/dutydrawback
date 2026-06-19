"""
Runnable demo: extract -> validate, showing what a reviewer would see.

This skips the live API call (no key here) and instead hand-builds two entries
to show the validation layer's behavior: a clean entry passes silently, a
corrupted one produces structured findings that name the exact field to review.

Run: python3 demo.py
"""

from datetime import date
from decimal import Decimal

from schema import Entry7501, LineItem
from validation import validate_entry


def make_entry(corrupt: bool) -> Entry7501:
    qty = Decimal("500")
    price = Decimal("248.00")
    # clean: 500 * 248 = 124000. corrupt: misread value as 142000.
    value = Decimal("142000.00") if corrupt else Decimal("124000.00")
    line1 = LineItem(
        line_number=1, hts_code="8471.30.0100",
        description="Portable data processing machine",
        quantity=qty, unit_of_measure="EA", unit_price=price,
        entered_value=value, duty_paid=Decimal("0"), mpf_paid=Decimal("442.40"),
    )
    line2 = LineItem(
        line_number=2, hts_code="8544.42.9090", description="USB-C cable",
        quantity=Decimal("2000"), unit_of_measure="EA", unit_price=Decimal("3.50"),
        entered_value=Decimal("7000.00"), duty_paid=Decimal("182.00"),
        mpf_paid=Decimal("24.97"),
    )
    total_val = (value + Decimal("7000.00"))
    return Entry7501(
        entry_number="ABC-1234567", entry_date=date(2024, 3, 11),
        importer_of_record="Acme Imports LLC", port_of_entry="2704",
        line_items=[line1, line2],
        total_entered_value=total_val, total_duty=Decimal("182.00"),
        total_mpf=Decimal("467.37"),
    )


def show(label: str, entry: Entry7501):
    print(f"\n=== {label} ===")
    result = validate_entry(entry, claim_date=date(2025, 9, 2))
    if result.ok and not result.findings:
        print("  clean: no findings, fields auto-pass")
    else:
        status = "PASS (with warnings)" if result.ok else "ROUTED TO REVIEW"
        print(f"  status: {status}")
        for f in result.findings:
            print(f"    - {f}")
    print(f"  total duties/taxes/fees available for drawback: "
          f"{entry.total_duties_taxes_fees}")


if __name__ == "__main__":
    show("Clean 7501", make_entry(corrupt=False))
    show("Corrupted 7501 (line 1 value misread)", make_entry(corrupt=True))
