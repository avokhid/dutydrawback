"""
"How it's calculated" — plain-language explanation of a refund line.

Turns a LineCalculation (what the engine actually computed) into an ordered
list of human-readable steps, each with the real numbers filled in and the
legal basis cited. Nothing here re-computes or invents; it narrates the values
the engine already produced. That's the point — the explanation is the
derivation, so it can't drift from the number it explains.

Three things each step carries:
  - text   : plain language anyone can grasp ("99% of the duties you paid")
  - math   : the arithmetic with actual numbers ("$880.00 × 99% = $871.20")
  - basis  : the statute/regulation citation, for a reviewer who wants to verify

Each cited step also links to a TaggedRule (rule_tiers.py), so the UI can show
how settled the rule is — today every applied rule is statute/regulation tier.
Citations are the well-grounded ones (rate, window, lesser-of). Where a figure
depends on an edge case a specialist should confirm, the step says so rather
than implying false precision.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

from calculation import LineCalculation, DrawbackType
from rule_tiers import get_rule, TIER_META


@dataclass
class ExplanationStep:
    text: str                    # plain language
    math: Optional[str] = None   # arithmetic with real numbers
    basis: Optional[str] = None  # statute / regulation citation
    rule_id: Optional[str] = None  # links to a TaggedRule, so the UI can show its tier

    def to_json(self) -> dict:
        d = {"text": self.text, "math": self.math, "basis": self.basis}
        rule = get_rule(self.rule_id) if self.rule_id else None
        if rule is not None:
            meta = TIER_META[rule.tier]
            d["tier"] = rule.tier.value
            d["tier_label"] = meta["label"]
            d["certainty"] = meta["certainty"]
        return d


# 99% is set by statute; the cite is stable.
RATE_CITE = "19 U.S.C. 1313 — drawback refunds 99% of duties, taxes, and fees"
SUBST_CITE = "19 U.S.C. 1313(j)(2) — substitution; refund limited to the lesser-of basis"
DIRECT_CITE = "19 U.S.C. 1313(j)(1) — direct identification; no substitution cap"


def explain_line(lc: LineCalculation) -> list[ExplanationStep]:
    """Build the ordered 'how it's calculated' steps for one refund line."""
    steps: list[ExplanationStep] = []
    qty = lc.quantity_designated
    per_unit = lc.duties_taxes_fees_per_unit
    line_dtf = (per_unit * qty)

    # Step 1 — what was paid, per unit, on the designated quantity
    steps.append(ExplanationStep(
        text=(f"You paid duties, taxes, and fees on the imported goods. "
              f"Spread across the {qty} unit(s) being claimed, that's "
              f"{_money(per_unit)} per unit."),
        math=f"{_money(per_unit)} per unit × {qty} unit(s) = {_money(line_dtf)} claimed",
        basis=None,
    ))

    # Step 2 — the 99% rule
    steps.append(ExplanationStep(
        text="Drawback refunds 99% of what you paid — 1% is retained.",
        math=f"{_money(line_dtf)} × 99% = {_money(lc.refund_before_cap)}",
        basis=RATE_CITE,
        rule_id="rate_99",
    ))

    # Step 3 — the lesser-of cap, only for substitution and only if it bound
    if lc.drawback_type is DrawbackType.UNUSED_SUBSTITUTION:
        if lc.cap_applied and lc.cap_amount is not None:
            steps.append(ExplanationStep(
                text=("Because this is a substitution claim, the refund is capped "
                      "at the lower of the imported or exported article's duty. "
                      "The exported article's duty was lower, so the cap applies "
                      "and reduces the refund."),
                math=f"capped at {_money(lc.cap_amount)} (below {_money(lc.refund_before_cap)})",
                basis=SUBST_CITE,
                rule_id="lesser_of",
            ))
        else:
            steps.append(ExplanationStep(
                text=("This is a substitution claim, so a lesser-of cap is checked. "
                      "Here the imported article's duty governs, so the cap does "
                      "not reduce the refund."),
                math=None,
                basis=SUBST_CITE,
                rule_id="lesser_of",
            ))
    else:
        steps.append(ExplanationStep(
            text=("This is a direct-identification claim — the actual imported goods "
                  "were exported — so no substitution cap applies."),
            math=None,
            basis=DIRECT_CITE,
            rule_id="direct_no_cap",
        ))

    # Step 4 — the final figure
    steps.append(ExplanationStep(
        text="Estimated recovery for this line:",
        math=f"= {_money(lc.refund)}",
        basis=None,
    ))

    # Carry any engine notes (e.g. why the cap bound) as-is for transparency
    for n in lc.notes:
        steps.append(ExplanationStep(text=n, math=None, basis=None))

    return steps


def explain_line_json(lc: LineCalculation) -> dict:
    """Serializable explanation for the API / UI."""
    return {
        "entry_number": lc.entry_number,
        "import_line": lc.import_line_number,
        "export_id": lc.export_id,
        "drawback_type": lc.drawback_type.value,
        "quantity": str(lc.quantity_designated),
        "refund": str(lc.refund),
        "capped": lc.cap_applied,
        "steps": [s.to_json() for s in explain_line(lc)],
    }


def _money(d: Decimal) -> str:
    return "$" + f"{d:,.2f}"
