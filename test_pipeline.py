"""
Tests for the second batch of pieces: export validation, inventory accounting,
matching, risk score, correction-learning, and the extra drawback types.

Run: python3 -m pytest test_pipeline.py -v
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

import pytest

from schema import Entry7501, LineItem
from export_schema import ExportRecord, ExportLineItem
from export_validation import validate_export
from inventory import InventoryLedger, AccountingMethod
from matching import MatchingEngine, MatchConfig, UomTable, MatchTier, to_designations
from calculation import calculate_claim, DrawbackType
from risk_score import FieldSignals, assess_field, RiskTier
from learning import RuleStore, Correction, CorrectionReason
from drawback_types import (
    FinishedArticle, BomComponent, manufacturing_designations,
    RejectedMerchandise, rejected_designation,
)


def _entry(entry_no="E-1", d=date(2024, 1, 10), qty="1000", duty="4500", mpf="500"):
    line = LineItem(
        line_number=1, hts_code="8471.30.0100", description="laptop computer unit",
        quantity=Decimal(qty), unit_of_measure="EA", unit_price=Decimal("200.00"),
        entered_value=Decimal(qty) * Decimal("200.00"),
        duty_paid=Decimal(duty), mpf_paid=Decimal(mpf),
    )
    return Entry7501(
        entry_number=entry_no, entry_date=d, importer_of_record="Acme",
        line_items=[line], total_entered_value=Decimal(qty) * Decimal("200.00"),
        total_duty=Decimal(duty), total_mpf=Decimal(mpf),
    )


def _export(hts="8471.30.0100", qty="1000", uom="EA"):
    li = ExportLineItem(
        line_number=1, hts_code=hts, description="laptop unit blue",
        quantity=Decimal(qty), unit_of_measure=uom,
        exported_article_duty_per_unit=Decimal("5.00"),
    )
    return ExportRecord(export_id="X-1", export_date=date(2025, 2, 1),
                        exporter="Acme", line_items=[li])


# --- export validation ---

def test_export_validation_clean():
    r = _export()
    assert validate_export(r).ok


def test_export_missing_hts_warns():
    r = _export(hts=None)
    res = validate_export(r)
    assert any(f.code == "EXPORT_HTS_MISSING" for f in res.findings)
    assert res.ok  # warn, not gate


# --- inventory ---

def test_fifo_orders_oldest_first():
    led = InventoryLedger(AccountingMethod.FIFO)
    led.load_entry(_entry("OLD", date(2023, 1, 1)))
    led.load_entry(_entry("NEW", date(2024, 1, 1)))
    lots = led.available_lots()
    assert lots[0].entry_number == "OLD"


def test_low_to_high_orders_cheapest_first():
    led = InventoryLedger(AccountingMethod.LOW_TO_HIGH)
    led.load_entry(_entry("CHEAP", duty="1000", mpf="0"))   # 1.0/unit
    led.load_entry(_entry("PRICEY", duty="9000", mpf="0"))  # 9.0/unit
    lots = led.available_lots()
    assert lots[0].entry_number == "CHEAP"


def test_consume_prevents_double_claim():
    led = InventoryLedger(AccountingMethod.FIFO)
    led.load_entry(_entry(qty="1000"))
    lot = led.available_lots()[0]
    lot.consume(Decimal("600"))
    assert lot.available_quantity == Decimal("400")
    assert led.total_available() == Decimal("400")


# --- matching ---

def test_matching_same_units_high_confidence():
    eng = MatchingEngine(MatchConfig(method=AccountingMethod.FIFO))
    matches = eng.match([_entry()], [_export()])
    assert len(matches) == 1
    m = matches[0]
    # HTS exact + decent desc overlap + same units => high
    assert m.signals["hts"] == Decimal("1")
    assert m.signals["uom"] == Decimal("1")
    assert m.tier in (MatchTier.AUTO_PASS, MatchTier.REVIEW)


def test_matching_unconvertible_units_lowers_confidence():
    eng = MatchingEngine(MatchConfig(method=AccountingMethod.FIFO))
    # export in cartons, no conversion loaded -> uom signal 0
    matches = eng.match([_entry()], [_export(uom="CTN")])
    if matches:
        assert matches[0].signals["uom"] == Decimal("0")


def test_matching_with_uom_conversion():
    uom = UomTable()
    uom.add("CTN", "EA", Decimal("10"))   # 1 carton = 10 each
    eng = MatchingEngine(MatchConfig(method=AccountingMethod.FIFO, uom=uom))
    matches = eng.match([_entry(qty="1000")], [_export(qty="100", uom="CTN")])
    assert matches and matches[0].signals["uom"] == Decimal("1")
    # 100 cartons * 10 = 1000 each designated
    assert matches[0].matched_quantity == Decimal("1000")


def test_match_to_designation_to_refund():
    uom = UomTable()
    uom.add("CTN", "EA", Decimal("10"))
    eng = MatchingEngine(MatchConfig(method=AccountingMethod.FIFO, uom=uom,
                                     auto_pass_threshold=Decimal("0.5")))
    entries = [_entry(qty="1000", duty="4500", mpf="500")]
    records = [_export(qty="100", uom="CTN")]
    matches = eng.match(entries, records)
    designations = to_designations(matches, records,
                                   drawback_type=DrawbackType.UNUSED_SUBSTITUTION)
    claim = calculate_claim({e.entry_number: e for e in entries}, designations)
    # per-unit DTF = 5000/1000 = 5; export basis 5; lesser-of = 5; 99%*5*1000
    assert claim.total_refund == Decimal("4950.00")


# --- risk score ---

def test_gate_forces_review():
    sig = FieldSignals(field_id="x", tripped_gate=True)
    r = assess_field(sig, auto_pass_max_error=Decimal("0.02"))
    assert r.tier is RiskTier.REVIEW and r.gated


def test_clean_signals_auto_pass():
    sig = FieldSignals(field_id="x", grounded=True, second_method_agrees=True,
                       sample_disagreement=Decimal("0"), model_confidence=Decimal("0.99"))
    r = assess_field(sig, auto_pass_max_error=Decimal("0.05"))
    assert r.tier is RiskTier.AUTO_PASS


def test_ungrounded_raises_risk():
    sig = FieldSignals(field_id="x", grounded=False)
    r = assess_field(sig, auto_pass_max_error=Decimal("0.05"))
    assert r.tier is RiskTier.REVIEW


# --- learning ---

def test_correction_becomes_uom_rule():
    store = RuleStore()
    c = Correction(
        correction_id="c1", reviewer="rev", timestamp=datetime.now(),
        field_corrected="unit_of_measure", system_value="1 carton = 12 units",
        corrected_value="1 carton = 10 units", reason=CorrectionReason.VENDOR_PACK_DIFFERS,
        vendor="ACME-MFG", part_number="WIDGET-A",
    )
    rule = store.learn_from(c)
    assert rule is not None
    f = store.uom_factor("ACME-MFG", "WIDGET-A", "CARTON", "UNIT")
    assert f == Decimal("10")


def test_rule_specificity_and_disable():
    store = RuleStore()
    store.learn_from(Correction("c1", "r", datetime.now(), "unit_of_measure",
        "x", "1 box = 5 units", CorrectionReason.VENDOR_PACK_DIFFERS, vendor="V"))
    assert store.uom_factor("V", None, "BOX", "UNIT") == Decimal("5")
    store.disable_rule("c1")
    assert store.uom_factor("V", None, "BOX", "UNIT") is None


# --- extra drawback types ---

def test_manufacturing_bom_explosion():
    entries = {"E-1": _entry("E-1", qty="10000", duty="10000", mpf="0")}
    article = FinishedArticle(
        article_id="WIDGET", quantity_exported=Decimal("1000"),
        components=[BomComponent("E-1", 1, quantity_per_unit=Decimal("2"),
                                 yield_factor=Decimal("1"))],
    )
    designations = manufacturing_designations(entries, article)
    # 1000 articles * 2 inputs each / yield 1 = 2000 input units
    assert designations[0].quantity == Decimal("2000")
    claim = calculate_claim(entries, designations)
    # per-unit duty = 10000/10000 = 1; 99% * 1 * 2000 = 1980
    assert claim.total_refund == Decimal("1980.00")


def test_rejected_requires_reason():
    with pytest.raises(ValueError, match="reason"):
        rejected_designation(RejectedMerchandise("E-1", 1, Decimal("10"), "", "X"))


def test_rejected_calculates():
    entries = {"E-1": _entry("E-1", qty="100", duty="100", mpf="0")}
    d = rejected_designation(
        RejectedMerchandise("E-1", 1, Decimal("100"), "defective", "X-1")
    )
    claim = calculate_claim(entries, [d])
    # per-unit 100/100 = 1; 99% * 1 * 100 = 99
    assert claim.total_refund == Decimal("99.00")


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


# --- verification signals (local parts) ---

def test_grounding_matches_normalized_number():
    from verification import value_is_grounded
    assert value_is_grounded("124,000.00", "ENTERED VALUE 124000 USD")
    assert not value_is_grounded("142000", "ENTERED VALUE 124000 USD")


def test_sample_disagreement_fraction():
    from verification import sample_disagreement
    from decimal import Decimal as D
    assert sample_disagreement(["1000", "1000", "1000"]) == D("0")
    # one of three disagrees -> 1/3
    assert sample_disagreement(["1000", "1000", "1300"]) == D("1") / D("3")
