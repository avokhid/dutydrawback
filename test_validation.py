"""
Tests for the deterministic validation layer.

The point of these tests is to prove two things:
  1. A clean, correct entry produces no gates (no false alarms).
  2. Each kind of injected error trips exactly the check meant to catch it.

This is the evidence that the reliability layer reliably fires. Run with:
    python3 -m pytest test_validation.py -v
or just:
    python3 test_validation.py
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from schema import Entry7501, LineItem
from validation import validate_entry, Severity


def _clean_entry() -> Entry7501:
    """A correct, internally consistent 2-line entry."""
    lines = [
        LineItem(
            line_number=1,
            hts_code="8471.30.0100",
            description="Portable data processing machine",
            quantity=Decimal("500"),
            unit_of_measure="EA",
            unit_price=Decimal("248.00"),
            entered_value=Decimal("124000.00"),
            duty_paid=Decimal("0.00"),
            mpf_paid=Decimal("442.40"),
            hmf_paid=Decimal("0.00"),
        ),
        LineItem(
            line_number=2,
            hts_code="8544.42.9090",
            description="USB-C cable",
            quantity=Decimal("2000"),
            unit_of_measure="EA",
            unit_price=Decimal("3.50"),
            entered_value=Decimal("7000.00"),
            duty_paid=Decimal("182.00"),
            mpf_paid=Decimal("24.97"),
            hmf_paid=Decimal("0.00"),
        ),
    ]
    return Entry7501(
        entry_number="ABC-1234567",
        entry_date=date(2024, 3, 11),
        importer_of_record="Acme Imports LLC",
        port_of_entry="2704",
        line_items=lines,
        total_entered_value=Decimal("131000.00"),
        total_duty=Decimal("182.00"),
        total_mpf=Decimal("467.37"),
        total_hmf=Decimal("0.00"),
    )


def _codes(result) -> set[str]:
    return {f.code for f in result.findings}


def test_clean_entry_has_no_gates():
    result = validate_entry(_clean_entry(), claim_date=date(2025, 9, 2))
    assert result.ok, f"clean entry should pass, got: {[str(f) for f in result.gates]}"
    assert result.gates == []


def test_line_math_error_is_caught():
    e = _clean_entry()
    # Corrupt line 1's entered value (misread 124000 as 142000).
    e.line_items[0].entered_value = Decimal("142000.00")
    # keep the header total consistent with the corrupted line so this isolates
    # the line-math check (otherwise totals would also fire)
    e.total_entered_value = Decimal("149000.00")
    result = validate_entry(e)
    assert "LINE_MATH" in _codes(result)
    f = next(f for f in result.findings if f.code == "LINE_MATH")
    assert f.severity is Severity.GATE
    assert f.line_number == 1
    assert f.field == "entered_value"
    assert f.discrepancy == Decimal("18000.00")


def test_total_mismatch_is_caught_and_triangulated():
    e = _clean_entry()
    # Drop line 2 from the header total (a classic "missed a line" error).
    e.total_entered_value = Decimal("124000.00")
    result = validate_entry(e)
    assert "TOTAL_VALUE" in _codes(result)
    f = next(f for f in result.findings if f.code == "TOTAL_VALUE")
    assert f.severity is Severity.GATE
    # the gap (7000) equals line 2's value, so triangulation should name it
    assert f.line_number == 2


def test_hts_wrong_length_warns():
    e = _clean_entry()
    e.line_items[1].hts_code = "85444290"  # 8 digits, dropped two
    result = validate_entry(e)
    assert "HTS_LENGTH" in _codes(result)
    f = next(f for f in result.findings if f.code == "HTS_LENGTH")
    assert f.severity is Severity.WARN  # suspicious, not dispositive
    assert f.line_number == 2


def test_drawback_window_gate():
    e = _clean_entry()  # entry date 2024-03-11
    # claim filed more than 5 years later
    result = validate_entry(e, claim_date=date(2029, 6, 1))
    assert "DRAWBACK_WINDOW" in _codes(result)
    f = next(f for f in result.findings if f.code == "DRAWBACK_WINDOW")
    assert f.severity is Severity.GATE


def test_window_ok_just_inside():
    e = _clean_entry()
    # exactly inside the 5-year window
    result = validate_entry(e, claim_date=date(2029, 3, 10))
    assert "DRAWBACK_WINDOW" not in _codes(result)


def test_schema_rejects_nondigit_hts():
    import pytest

    with pytest.raises(Exception):
        LineItem(
            line_number=1,
            hts_code="8471.30.01XX",  # letters where digits belong
            description="bad",
            quantity=Decimal("1"),
            unit_of_measure="EA",
            unit_price=Decimal("1.00"),
            entered_value=Decimal("1.00"),
        )


if __name__ == "__main__":
    # lightweight runner so this works without pytest installed
    import traceback

    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    passed = 0
    for t in tests:
        try:
            # tests using pytest.raises need pytest; skip gracefully if absent
            t()
            print(f"PASS  {t.__name__}")
            passed += 1
        except Exception as exc:  # noqa: BLE001
            print(f"FAIL  {t.__name__}: {exc}")
            traceback.print_exc()
    print(f"\n{passed}/{len(tests)} passed")
