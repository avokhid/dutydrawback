"""
Tests for the pipeline orchestrator.

Proves two things:
  1. Observability — running a clean pipeline emits the expected ordered events
     (validate -> match -> calculate -> done) with structured artifacts.
  2. Pause/resume — a GATE anomaly with pause_on_gate=True halts the pipeline at
     validation; applying a correction and resuming completes it. This proves
     the mid-flow-editing foundation works; only durable persistence of the
     paused state is left (and that's a storage swap, not engine work).

Run: python3 -m pytest test_orchestrator.py -v
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from schema import Entry7501, LineItem
from export_schema import ExportRecord, ExportLineItem
from matching import MatchConfig, UomTable
from inventory import AccountingMethod
from orchestrator import (
    PipelineOrchestrator, PipelineState, Stage, StageStatus,
)


def _clean_entry(value="124000.00"):
    line = LineItem(
        line_number=1, hts_code="8471.30.0100", description="laptop computer unit",
        quantity=Decimal("500"), unit_of_measure="EA", unit_price=Decimal("248.00"),
        entered_value=Decimal(value), duty_paid=Decimal("0"), mpf_paid=Decimal("442.40"),
    )
    return Entry7501(
        entry_number="ENT-1", entry_date=date(2024, 3, 11), importer_of_record="Acme",
        line_items=[line], total_entered_value=Decimal(value),
        total_duty=Decimal("0"), total_mpf=Decimal("442.40"),
    )


def _export(qty="50", uom="CTN"):
    li = ExportLineItem(
        line_number=1, hts_code="8471.30.0100", description="laptop unit",
        quantity=Decimal(qty), unit_of_measure=uom,
        exported_article_duty_per_unit=Decimal("0.88"),
    )
    return ExportRecord(export_id="BOL-1", export_date=date(2025, 2, 1),
                        exporter="Acme", line_items=[li])


def _config():
    uom = UomTable()
    uom.add("CTN", "EA", Decimal("10"))
    return MatchConfig(method=AccountingMethod.FIFO, uom=uom,
                       auto_pass_threshold=Decimal("0.5"), review_threshold=Decimal("0.3"))


def test_clean_pipeline_event_sequence():
    state = PipelineState(entries={"ENT-1": _clean_entry()}, records=[_export()],
                          claim_date=date(2025, 9, 2))
    orch = PipelineOrchestrator(state, config=_config())
    events = list(orch.run())
    stages = [(e.stage, e.status) for e in events]
    # expect: validate running+complete, match running+complete, calc running+complete, done
    assert (Stage.VALIDATE, StageStatus.RUNNING) in stages
    assert (Stage.VALIDATE, StageStatus.COMPLETE) in stages
    assert (Stage.MATCH, StageStatus.COMPLETE) in stages
    assert (Stage.CALCULATE, StageStatus.COMPLETE) in stages
    assert events[-1].stage is Stage.DONE
    # observability: the match event carries structured artifacts
    match_complete = next(e for e in events if e.stage is Stage.MATCH and e.status is StageStatus.COMPLETE)
    assert "matches" in match_complete.detail
    assert match_complete.detail["matched"] >= 1


def test_refund_reaches_done_event():
    state = PipelineState(entries={"ENT-1": _clean_entry()}, records=[_export()],
                          claim_date=date(2025, 9, 2))
    orch = PipelineOrchestrator(state, config=_config())
    events = list(orch.run())
    done = events[-1]
    assert done.stage is Stage.DONE
    assert state.refund is not None and state.refund > 0


def test_pause_on_gate_halts_before_match():
    # corrupt the entry so line math fails -> GATE finding
    bad = _clean_entry(value="142000.00")  # 500*248=124000, not 142000
    state = PipelineState(entries={"ENT-1": bad}, records=[_export()],
                          claim_date=date(2025, 9, 2))
    orch = PipelineOrchestrator(state, config=_config(), pause_on_gate=True)
    events = list(orch.run())
    # should pause at validate, never reach match
    assert events[-1].status is StageStatus.PAUSED
    assert events[-1].stage is Stage.VALIDATE
    assert not any(e.stage is Stage.MATCH for e in events)
    assert state.paused_on is not None
    # the pause event surfaces the blocking gate for the UI
    assert len(events[-1].detail["gates"]) >= 1


def test_resume_after_correction_completes():
    bad = _clean_entry(value="142000.00")
    state = PipelineState(entries={"ENT-1": bad}, records=[_export()],
                          claim_date=date(2025, 9, 2))
    orch = PipelineOrchestrator(state, config=_config(), pause_on_gate=True)
    list(orch.run())
    assert state.paused_on is not None

    # apply the correction (what a reviewer would do mid-flow), then resume
    state.entries["ENT-1"].line_items[0].entered_value = Decimal("124000.00")
    state.entries["ENT-1"].total_entered_value = Decimal("124000.00")
    state.current_stage = Stage.VALIDATE  # rewind to the paused stage
    resume_events = list(orch.resume(correction={
        "stage": "validate", "field": "entered_value",
        "from": "142000.00", "to": "124000.00", "reason": "re-measured",
    }))
    # now it should run through to done
    assert resume_events[-1].stage is Stage.DONE
    assert state.refund is not None
    # the correction is recorded for audit
    assert len(state.corrections) == 1
    assert state.corrections[0]["field"] == "entered_value"


def test_warn_does_not_pause():
    # a WARN (e.g. short HTS) should flow through, not halt
    e = _clean_entry()
    e.line_items[0].hts_code = "84713001"  # 8 digits -> WARN, not GATE
    state = PipelineState(entries={"ENT-1": e}, records=[_export()],
                          claim_date=date(2025, 9, 2))
    orch = PipelineOrchestrator(state, config=_config(), pause_on_gate=True)
    events = list(orch.run())
    assert events[-1].stage is Stage.DONE  # completed despite the warning
    assert not any(e.status is StageStatus.PAUSED for e in events)


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
