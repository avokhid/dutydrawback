"""
Tests for the drawback calculation engine.

These prove the rules that shape the refund number actually apply:
  - 99% of duties/taxes/fees, not 100%
  - per-unit apportionment when only part of a line is designated
  - the lesser-of cap binds under substitution when the exported article's
    duty basis is lower, and does NOT bind when it's higher
  - direct identification has no cap
  - the engine refuses to compute substitution drawback without the cap basis
    (refuse-rather-than-guess)

Run: python3 -m pytest test_calculation.py -v
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from schema import Entry7501, LineItem
from calculation import (
    Designation, ExportLine, DrawbackType,
    calculate_line, calculate_claim,
)


def _entry() -> Entry7501:
    # One line: 1000 units, $5,000 total duties+fees => $5/unit of DTF.
    line = LineItem(
        line_number=1, hts_code="8471.30.0100", description="laptop",
        quantity=Decimal("1000"), unit_of_measure="EA",
        unit_price=Decimal("200.00"), entered_value=Decimal("200000.00"),
        duty_paid=Decimal("4500.00"), mpf_paid=Decimal("500.00"),
        hmf_paid=Decimal("0.00"),
    )
    return Entry7501(
        entry_number="E-1", entry_date=date(2024, 1, 10),
        importer_of_record="Acme", line_items=[line],
        total_entered_value=Decimal("200000.00"), total_duty=Decimal("4500.00"),
        total_mpf=Decimal("500.00"),
    )


def test_99_percent_full_line_direct():
    e = _entry()
    # designate all 1000 units, direct identification
    d = Designation(
        entry_number="E-1", import_line_number=1,
        export=ExportLine(export_id="X1", hts_code="8471.30.0100",
                          quantity=Decimal("1000"), unit_of_measure="EA"),
        quantity=Decimal("1000"), drawback_type=DrawbackType.UNUSED_DIRECT,
    )
    lc = calculate_line(e, d)
    # 99% of $5000 = $4950
    assert lc.refund == Decimal("4950.00")
    assert lc.cap_applied is False


def test_partial_designation_apportions_per_unit():
    e = _entry()
    # designate only 250 of 1000 units => 99% of (5/unit * 250) = 1237.50
    d = Designation(
        entry_number="E-1", import_line_number=1,
        export=ExportLine(export_id="X1", hts_code="8471.30.0100",
                          quantity=Decimal("250"), unit_of_measure="EA"),
        quantity=Decimal("250"), drawback_type=DrawbackType.UNUSED_DIRECT,
    )
    lc = calculate_line(e, d)
    assert lc.duties_taxes_fees_per_unit == Decimal("5.00")
    assert lc.refund == Decimal("1237.50")


def test_substitution_cap_binds_when_export_basis_lower():
    e = _entry()
    # imported basis is $5/unit; exported article basis only $3/unit.
    # cap = 99% * 3 * 1000 = 2970, which is below 99% * 5 * 1000 = 4950.
    d = Designation(
        entry_number="E-1", import_line_number=1,
        export=ExportLine(export_id="X1", hts_code="8471.30.0100",
                          quantity=Decimal("1000"), unit_of_measure="EA",
                          exported_article_duty_per_unit=Decimal("3.00")),
        quantity=Decimal("1000"), drawback_type=DrawbackType.UNUSED_SUBSTITUTION,
    )
    lc = calculate_line(e, d)
    assert lc.cap_applied is True
    assert lc.refund == Decimal("2970.00")
    assert lc.refund_before_cap == Decimal("4950.00")


def test_substitution_cap_does_not_bind_when_export_basis_higher():
    e = _entry()
    # exported basis $8/unit > imported $5/unit, so the import basis governs;
    # cap does not reduce the refund.
    d = Designation(
        entry_number="E-1", import_line_number=1,
        export=ExportLine(export_id="X1", hts_code="8471.30.0100",
                          quantity=Decimal("1000"), unit_of_measure="EA",
                          exported_article_duty_per_unit=Decimal("8.00")),
        quantity=Decimal("1000"), drawback_type=DrawbackType.UNUSED_SUBSTITUTION,
    )
    lc = calculate_line(e, d)
    assert lc.cap_applied is False
    assert lc.refund == Decimal("4950.00")


def test_substitution_without_basis_refuses():
    e = _entry()
    d = Designation(
        entry_number="E-1", import_line_number=1,
        export=ExportLine(export_id="X1", hts_code="8471.30.0100",
                          quantity=Decimal("1000"), unit_of_measure="EA",
                          exported_article_duty_per_unit=None),  # missing
        quantity=Decimal("1000"), drawback_type=DrawbackType.UNUSED_SUBSTITUTION,
    )
    with pytest.raises(ValueError, match="lesser-of cap"):
        calculate_line(e, d)


def test_overclaim_rejected():
    e = _entry()
    d = Designation(
        entry_number="E-1", import_line_number=1,
        export=ExportLine(export_id="X1", hts_code="8471.30.0100",
                          quantity=Decimal("2000"), unit_of_measure="EA"),
        quantity=Decimal("2000"),  # more than the 1000 on the line
        drawback_type=DrawbackType.UNUSED_DIRECT,
    )
    with pytest.raises(ValueError, match="exceeds line quantity"):
        calculate_line(e, d)


def test_full_claim_sums():
    e = _entry()
    entries = {"E-1": e}
    designations = [
        Designation(
            entry_number="E-1", import_line_number=1,
            export=ExportLine(export_id="X1", hts_code="8471.30.0100",
                              quantity=Decimal("400"), unit_of_measure="EA"),
            quantity=Decimal("400"), drawback_type=DrawbackType.UNUSED_DIRECT,
        ),
        Designation(
            entry_number="E-1", import_line_number=1,
            export=ExportLine(export_id="X2", hts_code="8471.30.0100",
                              quantity=Decimal("100"), unit_of_measure="EA"),
            quantity=Decimal("100"), drawback_type=DrawbackType.UNUSED_DIRECT,
        ),
    ]
    claim = calculate_claim(entries, designations)
    # 99% * 5 * (400 + 100) = 2475
    assert claim.total_refund == Decimal("2475.00")
    assert len(claim.lines) == 2


if __name__ == "__main__":
    import traceback
    tests = [v for k, v in sorted(globals().items())
             if k.startswith("test_") and callable(v)]
    passed = 0
    for t in tests:
        try:
            t()
            print(f"PASS  {t.__name__}")
            passed += 1
        except Exception as exc:  # noqa: BLE001
            print(f"FAIL  {t.__name__}: {exc}")
            traceback.print_exc()
    print(f"\n{passed}/{len(tests)} passed")
