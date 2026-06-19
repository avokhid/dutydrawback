"""
Rule tiers — how settled is each rule the engine applies.

The engine's calculation rests on rules of genuinely different certainty, and
presenting them as equally authoritative would be a quiet misrepresentation in a
compliance tool. This module gives each rule a tier so the "how it's calculated"
panel can show not just WHAT the rule is and WHERE it's from, but HOW SETTLED it
is — the truthful answer to "is the engine limited to certain sources?"

Three tiers, in descending certainty:

  STATUTE  — codified in 19 U.S.C. 1313 or 19 CFR Part 190. The calculation
             rests on these; they are as settled as drawback law gets.

  RULING   — grounded in a published CBP ruling / directive / CROSS decision.
             Citable and concrete, but narrower and fact-sensitive; which
             rulings apply is a curation judgment for a specialist. The engine
             ships with NONE of these populated — the tier exists as the scaffold
             that curation would fill. We do not invent rulings.

  ADVISORY — not a calculation rule at all. A pattern from how CBP has
             adjudicated similar claims in practice ("this kind of substitution
             has drawn scrutiny"). It flags risk; it never changes the math.
             Also unpopulated by default — populated only by a specialist.

Outside all three sits DISCRETION: case-by-case CBP judgment that by its nature
cannot be encoded. It is not a tier because there is no rule to tag — it is
handled only by the transparency disclosure and specialist review. We name it
here so the boundary is explicit, not hidden.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class RuleTier(str, Enum):
    STATUTE = "statute"
    RULING = "ruling"
    ADVISORY = "advisory"


# Plain-language framing per tier, for the UI. Kept here so the wording is
# consistent everywhere a tier is shown and reviewed in one place.
TIER_META = {
    RuleTier.STATUTE: {
        "label": "Statute / regulation",
        "certainty": "Firmly codified",
        "plain": "Written directly into drawback law. The calculation rests on this.",
    },
    RuleTier.RULING: {
        "label": "CBP ruling",
        "certainty": "Codified but narrower",
        "plain": "Based on a published CBP ruling. Concrete and citable, but "
                 "fact-sensitive — whether it applies to your case is confirmed "
                 "by a specialist.",
    },
    RuleTier.ADVISORY: {
        "label": "Practice pattern",
        "certainty": "Advisory, not a rule",
        "plain": "Reflects how CBP has handled similar claims in practice. This "
                 "flags risk for review; it does not change the calculation.",
    },
}

# The explicit out-of-scope boundary. Surfaced in the transparency disclosure.
DISCRETION_NOTICE = (
    "Some outcomes depend on case-by-case discretion exercised by CBP that cannot "
    "be predicted by any rule. Those determinations are outside this estimate and "
    "are why a licensed drawback specialist — and ultimately CBP — make the final call."
)


@dataclass(frozen=True)
class TaggedRule:
    """
    A rule the engine can apply, with its tier and source. The engine's core
    calculation rules are STATUTE-tier; the RULING and ADVISORY registries start
    empty and are populated only by a specialist (never fabricated here).
    """

    rule_id: str
    tier: RuleTier
    statement: str          # what the rule says, plain
    source: str             # citation: statute section, CFR part, or ruling no.

    def to_json(self) -> dict:
        meta = TIER_META[self.tier]
        return {
            "rule_id": self.rule_id,
            "tier": self.tier.value,
            "tier_label": meta["label"],
            "certainty": meta["certainty"],
            "statement": self.statement,
            "source": self.source,
        }


# --- The engine's codified rules, all STATUTE tier ---------------------------
# These are the rules the calculation actually applies today. Every one is
# statute/CFR grounded — which is the honest current state: the engine is
# limited to codified sources, and tagging makes that visible rather than hidden.

STATUTE_RULES: dict[str, TaggedRule] = {
    "rate_99": TaggedRule(
        rule_id="rate_99", tier=RuleTier.STATUTE,
        statement="Drawback refunds 99% of duties, taxes, and fees paid.",
        source="19 U.S.C. 1313",
    ),
    "window_5yr": TaggedRule(
        rule_id="window_5yr", tier=RuleTier.STATUTE,
        statement="A claim must be filed within 5 years of importation.",
        source="19 U.S.C. 1313; 19 CFR 190",
    ),
    "lesser_of": TaggedRule(
        rule_id="lesser_of", tier=RuleTier.STATUTE,
        statement="Substitution refund is limited to the lesser of the imported "
                  "or exported article's duty.",
        source="19 U.S.C. 1313(j)(2)",
    ),
    "direct_no_cap": TaggedRule(
        rule_id="direct_no_cap", tier=RuleTier.STATUTE,
        statement="Direct identification has no substitution cap.",
        source="19 U.S.C. 1313(j)(1)",
    ),
    "rejected_reason": TaggedRule(
        rule_id="rejected_reason", tier=RuleTier.STATUTE,
        statement="Rejected-merchandise drawback requires a qualifying reason "
                  "(defective, non-conforming, or shipped without consent).",
        source="19 U.S.C. 1313(c)",
    ),
}

# Populated ONLY by a specialist. Empty by default — the scaffold, not invented
# content. Code that reads these must handle emptiness as the normal state.
RULING_RULES: dict[str, TaggedRule] = {}
ADVISORY_RULES: dict[str, TaggedRule] = {}


def get_rule(rule_id: str) -> TaggedRule | None:
    return (STATUTE_RULES.get(rule_id)
            or RULING_RULES.get(rule_id)
            or ADVISORY_RULES.get(rule_id))


def tier_summary() -> dict:
    """
    What the engine currently rests on, by tier — for the transparency panel.
    Tells the user, truthfully, that today everything is statute-tier and the
    ruling/advisory layers are not yet populated.
    """
    return {
        "statute": len(STATUTE_RULES),
        "ruling": len(RULING_RULES),
        "advisory": len(ADVISORY_RULES),
        "discretion_notice": DISCRETION_NOTICE,
        "scope_statement": (
            "This estimate applies drawback rules as written in statute and "
            "regulation. It does not yet incorporate CBP rulings or practice "
            "patterns, and it cannot account for case-by-case CBP discretion. "
            "Eligibility is confirmed by a licensed drawback specialist before filing."
        ),
    }
