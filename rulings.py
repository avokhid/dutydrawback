"""
CBP rulings retrieval layer.

Surfaces relevant published CBP rulings (from CROSS) alongside a calculation,
as Ruling-tier *references* — "here are rulings that may bear on this claim,
confirm applicability" — never as rules that change the math. This is the
division of labor for an expert-facing tool: the system does the search-and-
assemble grind; the specialist decides whether a ruling controls.

What this layer does (buildable without a domain expert):
  - hold ingested rulings with their citation, issue, holding summary, and the
    HTS codes / provisions they touch
  - track the modified/revoked/superseded chain so a stale ruling is never
    surfaced as live
  - match rulings to a calculation line by HTS code and drawback provision
  - return them ranked, each clearly marked "relevant — confirm applicability"

What it deliberately does NOT do:
  - decide whether a ruling controls a specific claim (interpretation = the
    specialist's job)
  - change the calculated number (rulings are references, not math)
  - ship with fabricated content. The samples below are clearly flagged as
    samples; real content is ingested from CROSS in the deploying environment.

ACCESS NOTE: CROSS lives at rulings.cbp.gov (also a data.gov dataset). This
module is source-agnostic: `ingest()` takes already-fetched ruling records, so
you point it at CROSS via the permitted bulk dataset or fetch in your own
environment. Nothing here scrapes; it stores what you give it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class RulingStatus(str, Enum):
    ACTIVE = "active"
    MODIFIED = "modified"
    REVOKED = "revoked"
    SUPERSEDED = "superseded"


@dataclass
class Ruling:
    """One CBP ruling as ingested from CROSS."""

    ruling_id: str              # e.g. "H123456"
    date: str                   # ISO date as published
    issue: str                  # one-line subject
    holding: str                # plain summary of what CBP held
    hts_codes: list[str] = field(default_factory=list)   # codes the ruling touches
    provisions: list[str] = field(default_factory=list)  # e.g. "1313(j)(2)"
    status: RulingStatus = RulingStatus.ACTIVE
    superseded_by: Optional[str] = None                  # ruling_id that replaced it
    url: Optional[str] = None
    is_sample: bool = False     # True for the seeded examples; never for real ingests

    def to_json(self) -> dict:
        return {
            "ruling_id": self.ruling_id,
            "date": self.date,
            "issue": self.issue,
            "holding": self.holding,
            "hts_codes": self.hts_codes,
            "provisions": self.provisions,
            "status": self.status.value,
            "superseded_by": self.superseded_by,
            "url": self.url,
            "is_sample": self.is_sample,
            # the honest framing travels WITH every ruling so the UI can't drop it
            "disposition": "Relevant reference — confirm applicability to this claim.",
        }


class RulingsStore:
    """
    Holds ingested rulings and retrieves the ones relevant to a calculation.
    In production back this with a database; the interface stays the same.
    """

    def __init__(self) -> None:
        self._rulings: dict[str, Ruling] = {}

    def ingest(self, rulings: list[Ruling]) -> int:
        """
        Add rulings (already fetched from CROSS). Returns count ingested.
        Re-ingesting the same id updates it (CROSS rulings get modified/revoked).
        """
        for r in rulings:
            self._rulings[r.ruling_id] = r
        return len(rulings)

    def get(self, ruling_id: str) -> Optional[Ruling]:
        return self._rulings.get(ruling_id)

    def _is_live(self, r: Ruling) -> bool:
        """A ruling is live unless it's been revoked or superseded."""
        return r.status in (RulingStatus.ACTIVE, RulingStatus.MODIFIED)

    def relevant_to(
        self, hts_code: Optional[str], provision: Optional[str],
        include_stale: bool = False,
    ) -> list[Ruling]:
        """
        Rulings touching this HTS code and/or provision. Stale (revoked/
        superseded) rulings are excluded by default — surfacing a dead ruling as
        live would be worse than surfacing none. Ranked: exact HTS match first,
        then provision-only matches.
        """
        out: list[tuple[int, Ruling]] = []
        for r in self._rulings.values():
            if not include_stale and not self._is_live(r):
                continue
            score = 0
            if hts_code and hts_code in r.hts_codes:
                score += 2
            if provision and provision in r.provisions:
                score += 1
            if score > 0:
                out.append((score, r))
        out.sort(key=lambda sr: sr[0], reverse=True)
        return [r for _, r in out]

    def all(self) -> list[Ruling]:
        return list(self._rulings.values())


# --- Seeded SAMPLE rulings ---------------------------------------------------
# Clearly flagged is_sample=True. These illustrate the shape and let the layer
# be tested; they are NOT a curated authoritative set and must be replaced by
# real CROSS ingests. The holdings are paraphrased illustrations, not verbatim
# CBP text, and should not be relied on.

SAMPLE_RULINGS = [
    Ruling(
        ruling_id="SAMPLE-H000001", date="2021-05-12",
        issue="Substitution unused merchandise drawback — commercial interchangeability",
        holding="Illustrative sample: goods sharing the same 10-digit HTS and "
                "meeting interchangeability criteria may be substituted. Confirm "
                "against the actual ruling before relying.",
        hts_codes=["8471.30.0100"], provisions=["1313(j)(2)"],
        status=RulingStatus.ACTIVE, url="https://rulings.cbp.gov/ruling/SAMPLE",
        is_sample=True,
    ),
    Ruling(
        ruling_id="SAMPLE-H000002", date="2019-02-01",
        issue="Unit of measure selection for drawback claims",
        holding="Illustrative sample: a consistent unit of measure must be used "
                "across the claim. Sample only.",
        hts_codes=["8544.42.9090"], provisions=["1313(j)(1)", "1313(j)(2)"],
        status=RulingStatus.ACTIVE, is_sample=True,
    ),
    Ruling(
        ruling_id="SAMPLE-H000003", date="2015-08-20",
        issue="Older substitution standard (illustrative, superseded by TFTEA)",
        holding="Illustrative sample of a pre-TFTEA holding, marked superseded to "
                "demonstrate stale-ruling handling.",
        hts_codes=["8471.30.0100"], provisions=["1313(j)(2)"],
        status=RulingStatus.SUPERSEDED, superseded_by="SAMPLE-H000001",
        is_sample=True,
    ),
]


def seeded_store() -> RulingsStore:
    """A store preloaded with the clearly-marked sample rulings, for dev/demo."""
    s = RulingsStore()
    s.ingest(SAMPLE_RULINGS)
    return s
