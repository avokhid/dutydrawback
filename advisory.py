"""
Advisory layer — adjudications and discretion, handled as transparency, not data.

Two things deliberately NOT built as engines, because accessible public data
can't support them honestly:

  ADJUDICATIONS — how CBP actually decided real filed claims (what got
  challenged, what got paid) is mostly not published as a searchable dataset.
  The only public slice is litigated court decisions (CIT / Federal Circuit) and
  the Customs Bulletin — a small, biased sample of disputes serious enough to
  reach publication, not the broad base of routine claim outcomes. A reliable
  "this resembles a pattern CBP scrutinized" signal needs a specialist's
  judgment or proprietary filing-outcome data. So we surface, at most, a few
  illustrative published court decisions clearly labeled as illustrative — and
  otherwise say plainly that this layer is not a comprehensive pattern engine.

  DISCRETION — case-by-case CBP judgment. Not encodable by nature. Pure
  transparency: name it, scope it out, point to the specialist and CBP.

This module returns the plain messages the UI shows so the limits are stated up
front, in the user's view, rather than buried. For an expert-facing tool this is
the right contract: lift the search-and-assemble burden, be explicit about where
machine help stops and professional judgment begins.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class IllustrativeDecision:
    """
    A published court/bulletin decision shown ONLY as an illustrative caution,
    never as a comprehensive pattern. Clearly labeled as such in the UI.
    """

    citation: str               # e.g. a CIT slip opinion or Customs Bulletin cite
    summary: str                # plain, paraphrased — not verbatim
    note: str = "Illustrative published decision — not a comprehensive pattern."


ADJUDICATION_MESSAGE = (
    "How CBP adjudicates real claims — what gets accepted, challenged, or paid — "
    "is largely not available as public data. We can point to a few published "
    "court decisions as cautionary examples, but this is not a comprehensive view "
    "of CBP practice. Assessing how your specific claim is likely to fare is a "
    "judgment your drawback specialist makes, drawing on experience this tool "
    "cannot substitute for."
)

DISCRETION_MESSAGE = (
    "Some outcomes turn on case-by-case discretion exercised by CBP officers and "
    "cannot be predicted by any rule or dataset. These determinations are outside "
    "this estimate entirely. A licensed drawback specialist — and ultimately CBP — "
    "make the final call."
)

# Optional, sparse, clearly-illustrative. Empty by default; a specialist or a
# curated reading of public court decisions may add a few. We seed none, to
# avoid implying a pattern set exists.
ILLUSTRATIVE_DECISIONS: list[IllustrativeDecision] = []


@dataclass
class AdvisoryLayer:
    illustrative: list[IllustrativeDecision] = field(default_factory=lambda: list(ILLUSTRATIVE_DECISIONS))

    def to_json(self) -> dict:
        return {
            "adjudications": {
                "status": "not_a_pattern_engine",
                "message": ADJUDICATION_MESSAGE,
                "illustrative_decisions": [
                    {"citation": d.citation, "summary": d.summary, "note": d.note}
                    for d in self.illustrative
                ],
                "has_comprehensive_data": False,
            },
            "discretion": {
                "status": "out_of_scope_by_nature",
                "message": DISCRETION_MESSAGE,
            },
        }
