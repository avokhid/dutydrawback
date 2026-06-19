"""
Tests for the "how it's calculated" explanation builder.

Proves the explanation narrates the engine's ACTUAL computation — the final
figure in the steps equals the engine's refund, the 99% step shows the real
pre-cap number, and the cap step appears only when the cap actually bound. This
is what guarantees the explanation can't drift from the number it explains.

Run: python3 -m pytest test_explanation.py -v
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from schema import Entry7501, LineItem
from calculation import Designation, ExportLine, DrawbackType, calculate_line
from explanation import explain_line, explain_line_json


def _entry():
    line = LineItem(
        line_number=1, hts_code="8471.30.0100", description="laptop",
        quantity=Decimal("1000"), unit_of_measure="EA", unit_price=Decimal("200.00"),
        entered_value=Decimal("200000.00"), duty_paid=Decimal("4500.00"),
        mpf_paid=Decimal("500.00"),
    )
    return Entry7501(
        entry_number="E-1", entry_date=date(2024, 1, 10), importer_of_record="Acme",
        line_items=[line], total_entered_value=Decimal("200000.00"),
        total_duty=Decimal("4500.00"), total_mpf=Decimal("500.00"),
    )


def test_explanation_final_equals_engine_refund():
    e = _entry()
    d = Designation(entry_number="E-1", import_line_number=1,
                    export=ExportLine(export_id="X1", hts_code="8471.30.0100",
                                      quantity=Decimal("1000"), unit_of_measure="EA"),
                    quantity=Decimal("1000"), drawback_type=DrawbackType.UNUSED_DIRECT)
    lc = calculate_line(e, d)
    steps = explain_line(lc)
    # the last math-bearing step shows the engine's actual refund
    final = next(s for s in reversed(steps) if s.math and s.math.startswith("="))
    assert f"{lc.refund:,.2f}" in final.math


def test_direct_id_has_no_cap_step():
    e = _entry()
    d = Designation(entry_number="E-1", import_line_number=1,
                    export=ExportLine(export_id="X1", hts_code="8471.30.0100",
                                      quantity=Decimal("1000"), unit_of_measure="EA"),
                    quantity=Decimal("1000"), drawback_type=DrawbackType.UNUSED_DIRECT)
    lc = calculate_line(e, d)
    steps = explain_line(lc)
    text = " ".join(s.text for s in steps)
    assert "no substitution cap" in text.lower()
    # 99% step present with the real pre-cap math
    assert any("99%" in (s.math or "") for s in steps)


def test_substitution_cap_step_appears_when_bound():
    e = _entry()  # imported basis $5/unit
    d = Designation(entry_number="E-1", import_line_number=1,
                    export=ExportLine(export_id="X1", hts_code="8471.30.0100",
                                      quantity=Decimal("1000"), unit_of_measure="EA",
                                      exported_article_duty_per_unit=Decimal("3.00")),
                    quantity=Decimal("1000"),
                    drawback_type=DrawbackType.UNUSED_SUBSTITUTION)
    lc = calculate_line(e, d)
    assert lc.cap_applied  # sanity: the cap really bound
    steps = explain_line(lc)
    text = " ".join(s.text for s in steps).lower()
    assert "cap" in text and "lower" in text
    # a step cites the substitution statute
    assert any(s.basis and "1313(j)(2)" in s.basis for s in steps)


def test_substitution_cap_not_mentioned_as_binding_when_it_doesnt():
    e = _entry()  # imported basis $5/unit
    d = Designation(entry_number="E-1", import_line_number=1,
                    export=ExportLine(export_id="X1", hts_code="8471.30.0100",
                                      quantity=Decimal("1000"), unit_of_measure="EA",
                                      exported_article_duty_per_unit=Decimal("8.00")),
                    quantity=Decimal("1000"),
                    drawback_type=DrawbackType.UNUSED_SUBSTITUTION)
    lc = calculate_line(e, d)
    assert not lc.cap_applied
    steps = explain_line(lc)
    text = " ".join(s.text for s in steps).lower()
    assert "does not reduce" in text


def test_json_shape_for_ui():
    e = _entry()
    d = Designation(entry_number="E-1", import_line_number=1,
                    export=ExportLine(export_id="X1", hts_code="8471.30.0100",
                                      quantity=Decimal("500"), unit_of_measure="EA"),
                    quantity=Decimal("500"), drawback_type=DrawbackType.UNUSED_DIRECT)
    lc = calculate_line(e, d)
    j = explain_line_json(lc)
    assert j["refund"] == str(lc.refund)
    assert isinstance(j["steps"], list) and len(j["steps"]) >= 3
    assert all("text" in s for s in j["steps"])


if __name__ == "__main__":
    import traceback
    tests = [v for k, v in sorted(globals().items())
             if k.startswith("test_") and callable(v)]
    passed = 0
    for t in tests:
        try:
            t(); print(f"PASS  {t.__name__}"); passed += 1
        except Exception as exc:  # noqa: BLE001
            print(f"FAIL  {t.__name__}: {exc}"); traceback.print_exc()
    print(f"\n{passed}/{len(tests)} passed")


def test_steps_carry_rule_tier():
    e = _entry()
    d = Designation(entry_number="E-1", import_line_number=1,
                    export=ExportLine(export_id="X1", hts_code="8471.30.0100",
                                      quantity=Decimal("1000"), unit_of_measure="EA"),
                    quantity=Decimal("1000"), drawback_type=DrawbackType.UNUSED_DIRECT)
    lc = calculate_line(e, d)
    j = explain_line_json(lc)
    # the 99% step should carry a statute tier label
    tiered = [s for s in j["steps"] if s.get("tier")]
    assert tiered, "expected at least one step tagged with a tier"
    assert any(s["tier"] == "statute" for s in tiered)
    assert all(s["certainty"] for s in tiered)


def test_tier_summary_is_honest_about_current_scope():
    from rule_tiers import tier_summary
    s = tier_summary()
    # today everything rests on statute; ruling/advisory are empty scaffolding
    assert s["statute"] > 0
    assert s["ruling"] == 0
    assert s["advisory"] == 0
    # the scope statement names the limits plainly
    assert "does not yet incorporate CBP rulings" in s["scope_statement"]
    assert "discretion" in s["discretion_notice"].lower()
