"""
Per-field risk score.

Combines the independent signals we discussed into a single per-field decision:
auto-pass, or route to a reviewer. The design principle, made concrete:

  - GATE findings act as hard gates. A field that trips one routes to review
    regardless of any other signal — it cannot be outvoted. (Failed line math,
    totals that don't reconcile, claim outside the 5-year window.)

  - The softer signals combine into a graded score for fields that pass the
    gates: WARN findings, plus the external verification signals (grounding,
    sampling stability, second-method agreement), plus — weighted lowest — the
    model's own self-reported confidence.

  - A field auto-passes only when the combined evidence clears a threshold that
    is set against a labeled test set, not guessed. This module computes the
    score and tier; the threshold is policy passed in.

This is intentionally a transparent weighted model (v1), not a learned one. As
the discussion noted: ship the interpretable version, move to a calibrated
learned model once labeled data exists. The signal interface is built so that
swap doesn't change callers — `score_field` takes a FieldSignals and returns a
calibrated-ish probability-of-error in [0,1]; replace its body with a trained
model later and everything downstream still works.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
from typing import Optional

from validation import Finding, Severity


class RiskTier(str, Enum):
    AUTO_PASS = "auto_pass"
    REVIEW = "review"


@dataclass
class FieldSignals:
    """
    All signals known about one extracted field. Any may be None if that check
    didn't run (e.g. sampling is reserved for high-risk docs). Higher = riskier
    for the *_risk fields; higher = safer for *_agreement / grounded.
    """

    field_id: str                              # e.g. "entry.line[1].entered_value"
    tripped_gate: bool = False                 # any GATE finding on this field
    warn_count: int = 0                        # number of WARN findings
    grounded: Optional[bool] = None            # did value tie to its cited source?
    sample_disagreement: Optional[Decimal] = None  # 0..1, fraction of runs differing
    second_method_agrees: Optional[bool] = None
    structural_risk: Optional[Decimal] = None  # 0..1, e.g. scan quality / table edge
    model_confidence: Optional[Decimal] = None # 0..1 self-reported, weak


@dataclass
class FieldRisk:
    field_id: str
    error_probability: Decimal     # 0..1
    tier: RiskTier
    gated: bool                    # True if a hard gate forced review
    explanation: list[str] = field(default_factory=list)


# Weights for the soft blend. Self-reported model confidence is deliberately
# the smallest contributor. These are starting points to be tuned on labeled
# data; they are not measured.
W_WARN = Decimal("0.25")
W_GROUNDING = Decimal("0.30")
W_SAMPLING = Decimal("0.20")
W_SECOND_METHOD = Decimal("0.15")
W_STRUCTURAL = Decimal("0.07")
W_MODEL_CONF = Decimal("0.03")


def _clamp01(x: Decimal) -> Decimal:
    return max(Decimal("0"), min(Decimal("1"), x))


def score_field(sig: FieldSignals) -> Decimal:
    """
    Return an estimated probability that the field is wrong, in [0,1].

    Gates are handled by the caller (they force review regardless); this
    function scores the *soft* evidence. Replace the body with a trained,
    calibrated model when labeled data exists — keep the signature.
    """
    risk = Decimal("0")
    total_w = Decimal("0")

    # WARN findings: each adds risk, saturating.
    if sig.warn_count:
        warn_risk = _clamp01(Decimal(sig.warn_count) * Decimal("0.5"))
        risk += W_WARN * warn_risk
    total_w += W_WARN

    # Grounding: not grounded => high risk; grounded => low.
    if sig.grounded is not None:
        risk += W_GROUNDING * (Decimal("0") if sig.grounded else Decimal("1"))
        total_w += W_GROUNDING

    # Sampling disagreement: directly a risk fraction.
    if sig.sample_disagreement is not None:
        risk += W_SAMPLING * _clamp01(sig.sample_disagreement)
        total_w += W_SAMPLING

    # Second-method agreement: disagreement => risk.
    if sig.second_method_agrees is not None:
        risk += W_SECOND_METHOD * (Decimal("0") if sig.second_method_agrees else Decimal("1"))
        total_w += W_SECOND_METHOD

    # Structural risk (scan quality, table boundary, etc.).
    if sig.structural_risk is not None:
        risk += W_STRUCTURAL * _clamp01(sig.structural_risk)
        total_w += W_STRUCTURAL

    # Model self-confidence: low confidence => risk. Weak weight.
    if sig.model_confidence is not None:
        risk += W_MODEL_CONF * (Decimal("1") - _clamp01(sig.model_confidence))
        total_w += W_MODEL_CONF

    # Normalize by the weights of signals that were actually present, so a field
    # with only some checks run isn't artificially low-risk.
    if total_w == 0:
        return Decimal("0.5")  # no evidence either way -> neutral
    return _clamp01(risk / total_w)


def assess_field(sig: FieldSignals, auto_pass_max_error: Decimal) -> FieldRisk:
    """
    Decide the tier for one field.

    `auto_pass_max_error` is the policy threshold: the maximum estimated error
    probability allowed in the auto-passed pile (e.g. 0.02 = "no more than ~2%
    of auto-passed fields may be wrong"). Set this from a labeled test set.
    """
    explanation: list[str] = []

    if sig.tripped_gate:
        explanation.append("hard gate tripped (e.g. arithmetic/eligibility); forced review")
        return FieldRisk(
            field_id=sig.field_id,
            error_probability=Decimal("1"),
            tier=RiskTier.REVIEW,
            gated=True,
            explanation=explanation,
        )

    p = score_field(sig)
    tier = RiskTier.AUTO_PASS if p <= auto_pass_max_error else RiskTier.REVIEW
    explanation.append(f"soft error probability {p} vs threshold {auto_pass_max_error}")
    if sig.grounded is False:
        explanation.append("value could not be grounded to its cited source")
    if sig.sample_disagreement and sig.sample_disagreement > Decimal("0"):
        explanation.append(f"unstable across samples ({sig.sample_disagreement})")
    return FieldRisk(
        field_id=sig.field_id,
        error_probability=p,
        tier=tier,
        gated=False,
        explanation=explanation,
    )


def gate_findings_to_field_ids(findings: list[Finding]) -> set[str]:
    """
    Helper: collect the field identifiers that have a GATE finding, so callers
    can set tripped_gate on the right FieldSignals. Field id convention is the
    caller's; here we just key on (line_number, field).
    """
    ids: set[str] = set()
    for f in findings:
        if f.severity is Severity.GATE and f.field:
            key = f"line[{f.line_number}].{f.field}" if f.line_number else f.field
            ids.add(key)
    return ids
