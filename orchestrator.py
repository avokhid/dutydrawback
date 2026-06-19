"""
Pipeline orchestrator with observability and pause/resume hooks.

Runs the existing engine stages one at a time and emits a structured event
after each, so a UI can show the pipeline working live (the observability the
estimator wants). The stages themselves are unchanged — this is a thin
conductor over them.

Two capabilities, built to different depths on purpose:

  OBSERVABILITY (fully built here): each stage emits a StageEvent with status,
  a human summary, and the structured artifacts it produced (findings, matches).
  Drive it with the sample data; no API key or real documents needed.

  PAUSE / RESUME (hooks in place, not yet active): the orchestrator is written
  as a resumable state machine. On a GATE-severity anomaly it CAN halt and wait
  for a correction, then resume from that stage. That halt-and-resume needs the
  paused state to be persisted somewhere durable — which doesn't exist yet
  (everything is in-memory). So the hook is here and exercised in tests, but
  turning it on in production is gated on the persistence work. The design
  point: the engine stages are pure functions, so resuming is just re-running
  the affected stage with corrected data — the hard part is durably storing the
  paused state, not the re-run.

Interruption is exception-driven by design: the pipeline runs fast and
autonomously; it only PAUSES on a GATE finding. WARN findings flow through to
the post-run review queue. This keeps the "watch it work" benefit without
making the user babysit every run.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from decimal import Decimal
from datetime import date, datetime
from enum import Enum
from typing import Any, Callable, Iterator, Optional

from schema import Entry7501
from export_schema import ExportRecord
from validation import validate_entry, ValidationResult, Severity
from export_validation import validate_export
from matching import MatchingEngine, MatchConfig, CandidateMatch, MatchTier
from calculation import calculate_claim, DrawbackType
from matching import to_designations


# Human-readable basis labels, keyed by the engine's computable drawback types.
DRAWBACK_BASIS_LABELS = {
    DrawbackType.UNUSED_SUBSTITUTION: "unused-merchandise substitution",
    DrawbackType.UNUSED_DIRECT: "unused-merchandise direct identification",
}


class Stage(str, Enum):
    PARSE = "parse"            # (extraction happens upstream; here we accept parsed objects)
    VALIDATE = "validate"
    MATCH = "match"
    CALCULATE = "calculate"
    DONE = "done"


class StageStatus(str, Enum):
    RUNNING = "running"
    COMPLETE = "complete"
    PAUSED = "paused"          # halted on a GATE anomaly, awaiting correction
    ERROR = "error"


@dataclass
class StageEvent:
    """One observable step. Streamed to the UI as the pipeline runs."""

    stage: Stage
    status: StageStatus
    summary: str                          # human-readable, for the activity feed
    detail: dict[str, Any] = field(default_factory=dict)  # structured artifacts
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_json(self) -> dict:
        d = {
            "stage": self.stage.value,
            "status": self.status.value,
            "summary": self.summary,
            "detail": _jsonable(self.detail),
            "timestamp": self.timestamp,
        }
        return d


def _jsonable(obj: Any) -> Any:
    if isinstance(obj, Decimal):
        return str(obj)
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    if isinstance(obj, Enum):
        return obj.value
    if isinstance(obj, dict):
        return {k: _jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_jsonable(v) for v in obj]
    return obj


@dataclass
class PipelineState:
    """
    The resumable state. When persistence lands, THIS is what gets written to
    the database on pause and re-loaded on resume. Today it lives in memory.
    """

    entries: dict[str, Entry7501]
    records: list[ExportRecord]
    claim_date: Optional[date] = None
    current_stage: Stage = Stage.VALIDATE
    matches: list[CandidateMatch] = field(default_factory=list)
    refund: Optional[Decimal] = None
    paused_on: Optional[StageEvent] = None
    # corrections applied while paused: stage -> list of applied fixes (audit)
    corrections: list[dict] = field(default_factory=list)
    # the drawback basis the USER chose up front (not auto-optimized). Drives how
    # the calculate stage computes recovery; defaults to the simplest type. Note
    # the engine computes the two unused bases; types needing extra inputs
    # (rejected reason, manufacturing BOM) fall back to this default until those
    # input steps are wired, and the calculate event reports the basis actually used.
    drawback_type: DrawbackType = DrawbackType.UNUSED_SUBSTITUTION
    # extra inputs some types require (e.g. rejection_reason); carried for audit
    type_inputs: dict = field(default_factory=dict)


class PipelineOrchestrator:
    """
    Runs the stages as a generator of StageEvents. The caller (an API endpoint)
    iterates and streams each event to the UI. `pause_on_gate=True` makes the
    pipeline yield a PAUSED event and stop when a GATE anomaly appears; the
    caller can then apply a correction and call resume().
    """

    def __init__(self, state: PipelineState, config: Optional[MatchConfig] = None,
                 pause_on_gate: bool = False):
        self.state = state
        self.config = config or MatchConfig()
        self.pause_on_gate = pause_on_gate

    def source_documents(self) -> list[dict]:
        """
        The list of source documents being processed, for the UI to show up
        front ("Source documents: entry_summary.pdf, import_records.xlsx") so the
        reviewer confirms these are their files before the run.
        """
        docs = []
        for e in self.state.entries.values():
            docs.append({"id": e.entry_number, "kind": "import",
                         "document": e.source_document or e.entry_number})
        for r in self.state.records:
            docs.append({"id": r.export_id, "kind": "export",
                         "document": r.source_document or r.export_id})
        return docs

    def run(self) -> Iterator[StageEvent]:
        """Run from the current stage to completion (or until a pause)."""
        order = [Stage.VALIDATE, Stage.MATCH, Stage.CALCULATE]
        start = order.index(self.state.current_stage) if self.state.current_stage in order else 0
        for stage in order[start:]:
            self.state.current_stage = stage
            if stage is Stage.VALIDATE:
                yield from self._run_validate()
                if self.state.paused_on is not None:
                    return
            elif stage is Stage.MATCH:
                yield from self._run_match()
            elif stage is Stage.CALCULATE:
                yield from self._run_calculate()
        self.state.current_stage = Stage.DONE
        yield StageEvent(Stage.DONE, StageStatus.COMPLETE,
                         f"All done. Estimated recovery: about ${self.state.refund}.",
                         {"refund": self.state.refund})

    def _run_validate(self) -> Iterator[StageEvent]:
        doc_names = [e.source_document or e.entry_number for e in self.state.entries.values()]
        doc_names += [r.source_document or r.export_id for r in self.state.records]
        listed = ", ".join(doc_names)
        yield StageEvent(Stage.VALIDATE, StageStatus.RUNNING,
                         f"Checking your documents: {listed}")
        all_findings = []
        gate_hit = None
        for e in self.state.entries.values():
            doc = e.source_document or e.entry_number
            res = validate_entry(e, claim_date=self.state.claim_date)
            for f in res.findings:
                all_findings.append({"source": e.entry_number, "document": doc, **_finding_json(f)})
                if f.severity is Severity.GATE and gate_hit is None:
                    gate_hit = (e.entry_number, f)
        for r in self.state.records:
            doc = r.source_document or r.export_id
            res = validate_export(r)
            for f in res.findings:
                all_findings.append({"source": r.export_id, "document": doc, **_finding_json(f)})
                if f.severity is Severity.GATE and gate_hit is None:
                    gate_hit = (r.export_id, f)

        gates = [f for f in all_findings if f["severity"] == "gate"]
        warns = [f for f in all_findings if f["severity"] == "warn"]

        if gate_hit is not None and self.pause_on_gate:
            ev = StageEvent(Stage.VALIDATE, StageStatus.PAUSED,
                            f"Paused: {len(gates)} problem(s) need a fix before we can "
                            f"pair your shipments.",
                            {"gates": gates, "warnings": warns})
            self.state.paused_on = ev
            yield ev
            return

        if not gates and not warns:
            msg = "No problems found — your documents are clean."
        else:
            msg = (f"Found {len(gates)} problem(s) to fix and {len(warns)} thing(s) "
                   f"to double-check.")
        yield StageEvent(Stage.VALIDATE, StageStatus.COMPLETE, msg,
                         {"gates": gates, "warnings": warns})

    def _run_match(self) -> Iterator[StageEvent]:
        yield StageEvent(Stage.MATCH, StageStatus.RUNNING,
                         "Pairing your imports to the exports you can claim against…")
        engine = MatchingEngine(self.config)
        matches = engine.match(list(self.state.entries.values()), self.state.records)
        self.state.matches = matches
        auto = sum(1 for m in matches if m.tier is MatchTier.AUTO_PASS)
        review = sum(1 for m in matches if m.tier is MatchTier.REVIEW)
        if review:
            msg = (f"Paired {len(matches)} shipment(s). {auto} are a clear match; "
                   f"{review} need your confirmation before they count.")
        else:
            msg = f"Paired {len(matches)} shipment(s), all clear matches."
        yield StageEvent(Stage.MATCH, StageStatus.COMPLETE, msg,
                         {"matched": len(matches), "auto_pass": auto, "review": review,
                          "matches": [_match_json(m) for m in matches]})

    def _run_calculate(self) -> Iterator[StageEvent]:
        basis = DRAWBACK_BASIS_LABELS.get(
            self.state.drawback_type, self.state.drawback_type.value)
        yield StageEvent(Stage.CALCULATE, StageStatus.RUNNING,
                         "Working out how much you could recover…")
        designations = to_designations(self.state.matches, self.state.records,
                                       drawback_type=self.state.drawback_type,
                                       include_review_tier=True)
        try:
            claim = calculate_claim(self.state.entries, designations)
            self.state.refund = claim.total_refund
            yield StageEvent(Stage.CALCULATE, StageStatus.COMPLETE,
                             f"You could recover about ${claim.total_refund} "
                             f"(on a {basis} basis).",
                             {"refund": claim.total_refund, "lines": len(claim.lines),
                              "drawback_type": self.state.drawback_type.value,
                              "basis": basis})
        except Exception as exc:  # noqa: BLE001
            yield StageEvent(Stage.CALCULATE, StageStatus.ERROR,
                             f"Couldn't finish the estimate: {exc}", {"error": str(exc)})

    def resume(self, correction: Optional[dict] = None) -> Iterator[StageEvent]:
        """
        Resume after a pause. `correction` records what the user fixed (audit
        trail). The actual data fix is applied by the caller to state.entries
        before calling resume — the orchestrator just re-runs from the paused
        stage. Because stages are pure, re-running is safe and deterministic.

        NOTE: in production the paused PipelineState must have been persisted;
        here it's the in-memory object. That persistence is the remaining gate.
        """
        if correction is not None:
            self.state.corrections.append(correction)
        self.state.paused_on = None
        # re-run from the stage we paused on (validate), now that the fix applied
        yield from self.run()


def _finding_json(f) -> dict:
    return {
        "code": f.code,
        "severity": f.severity.value,
        "message": f.message,
        "line": f.line_number,
        "field": f.field,
        "discrepancy": str(f.discrepancy) if f.discrepancy is not None else None,
    }


def _match_json(m: CandidateMatch) -> dict:
    return {
        "entry_number": m.entry_number,
        "import_line": m.import_line_number,
        "export_id": m.export_id,
        "confidence": str(m.confidence),
        "tier": m.tier.value,
        "matched_quantity": str(m.matched_quantity),
    }
