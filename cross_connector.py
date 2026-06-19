"""
CROSS connector — populates the rulings store from CBP's CROSS.

Design constraint discovered up front: CROSS has NO clean, documented public
content API. Access is via (a) a data.gov bulk dataset (possibly a stale
snapshot), (b) the live site's search/recency feed at rulings.cbp.gov (closer to
scraping than an API), or (c) per-ruling fetch by stable URL. Which is best —
and whether bulk pulling is permitted — must be confirmed against CBP's current
terms at deploy time.

So this connector separates LOGIC from FETCH:

  - RulingSource: a swappable adapter that returns raw ruling records. Implement
    one per access method you confirm works. The connector doesn't care which.
  - Connector: owns the logic — parse raw records into Ruling objects, reconcile
    new / modified / revoked against the store, call ingest(). Fully testable
    with a mock source (the logic is verified here even though no live fetch is).

Two entry points, as specified:
  - bulk_ingest()  : one-off at setup; load the full corpus.
  - sync_recent()  : scheduled (e.g. weekly); pull only the recent/modified slice
                     using CROSS's own recency filters, and reconcile — crucially
                     including retiring rulings that have become revoked/superseded.

STATUS: the Connector logic is tested against MockRulingSource. A real source
adapter (e.g. Data.gov/live-site) is runnable-but-UNTESTED scaffolding — it needs
network access this environment doesn't have, and the exact response format must
be confirmed against the live source. Marked clearly below.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional, Protocol

from rulings import Ruling, RulingStatus, RulingsStore


# --- Source interface (swappable fetch adapter) ------------------------------

class RulingSource(Protocol):
    """Returns RAW ruling records (dicts). The connector parses them. Implement
    one of these per access method (data.gov bulk, live-site recency, per-URL)."""

    def fetch_all(self) -> Iterable[dict]:
        """All rulings — for the one-off bulk load."""
        ...

    def fetch_recent(self, days: int = 30) -> Iterable[dict]:
        """Rulings created or modified in the last `days` — for incremental sync.
        Maps onto CROSS's own 'modified in the last 30 days' filters."""
        ...


# --- Parsing raw -> Ruling ---------------------------------------------------

def parse_ruling(raw: dict) -> Ruling:
    """
    Turn one raw CROSS record into a Ruling. Field names here are the EXPECTED
    shape; confirm and adjust against the real source response — this is the
    most likely thing to need tweaking when wired to live data.

    Status mapping is the correctness-critical part: a record marked revoked or
    superseded MUST become a non-live status so the store stops surfacing it.
    """
    status_raw = (raw.get("status") or "active").lower()
    status = {
        "active": RulingStatus.ACTIVE,
        "modified": RulingStatus.MODIFIED,
        "revoked": RulingStatus.REVOKED,
        "superseded": RulingStatus.SUPERSEDED,
    }.get(status_raw, RulingStatus.ACTIVE)

    return Ruling(
        ruling_id=raw["ruling_id"],
        date=raw.get("date", ""),
        issue=raw.get("issue", ""),
        holding=raw.get("holding", ""),
        hts_codes=list(raw.get("hts_codes", [])),
        provisions=list(raw.get("provisions", [])),
        status=status,
        superseded_by=raw.get("superseded_by"),
        url=raw.get("url"),
        is_sample=False,  # real ingests are never samples
    )


# --- The connector (logic; fully tested with a mock source) ------------------

@dataclass
class SyncReport:
    added: int = 0
    updated: int = 0
    retired: int = 0   # flipped to revoked/superseded
    total_seen: int = 0

    def __str__(self) -> str:
        return (f"sync: {self.added} added, {self.updated} updated, "
                f"{self.retired} retired, {self.total_seen} seen")


class CrossConnector:
    def __init__(self, store: RulingsStore, source: RulingSource):
        self.store = store
        self.source = source

    def bulk_ingest(self) -> SyncReport:
        """One-off: load the full corpus. Idempotent — safe to re-run."""
        report = SyncReport()
        batch: list[Ruling] = []
        for raw in self.source.fetch_all():
            batch.append(parse_ruling(raw))
            report.total_seen += 1
        self._apply(batch, report)
        return report

    def sync_recent(self, days: int = 30) -> SyncReport:
        """
        Scheduled: pull only recent/modified rulings and reconcile. This is what
        keeps the layer from going stale. Because it pulls modified rulings too
        (not just new ones), it correctly retires rulings that have become
        revoked or superseded since the last sync.
        """
        report = SyncReport()
        batch: list[Ruling] = []
        for raw in self.source.fetch_recent(days=days):
            batch.append(parse_ruling(raw))
            report.total_seen += 1
        self._apply(batch, report)
        return report

    def _apply(self, rulings: list[Ruling], report: SyncReport) -> None:
        """
        Reconcile a batch into the store, classifying each as added / updated /
        retired so the sync is observable. ingest() itself is upsert, but we
        compare against the prior state to report what changed and to count
        retirements (the safety-critical transitions).
        """
        live_before = {RulingStatus.ACTIVE, RulingStatus.MODIFIED}
        for r in rulings:
            existing = self.store.get(r.ruling_id)
            if existing is None:
                report.added += 1
            else:
                report.updated += 1
                was_live = existing.status in live_before
                now_dead = r.status in (RulingStatus.REVOKED, RulingStatus.SUPERSEDED)
                if was_live and now_dead:
                    report.retired += 1
            self.store.ingest([r])


# --- Mock source for testing the logic without network -----------------------

class MockRulingSource:
    """An in-memory source so the connector logic is testable. `all_records` is
    the full corpus; `recent_records` is what a recency-filtered fetch returns."""

    def __init__(self, all_records: list[dict], recent_records: Optional[list[dict]] = None):
        self._all = all_records
        self._recent = recent_records if recent_records is not None else []

    def fetch_all(self) -> Iterable[dict]:
        return list(self._all)

    def fetch_recent(self, days: int = 30) -> Iterable[dict]:
        return list(self._recent)


# --- Real source adapter (UNTESTED scaffolding) ------------------------------

class LiveCrossSource:
    """
    UNTESTED. A real adapter against CROSS. Not runnable here (no network; format
    unconfirmed). Two honest unknowns you must resolve at deploy time:
      1. Access method: data.gov bulk dataset vs. live-site recency feed vs.
         per-ruling URL fetch. There is no documented content API, so confirm
         what CBP permits (and check terms re: automated access before pulling
         at scale).
      2. Response format: map the real fields into the dict shape parse_ruling()
         expects. The field names in parse_ruling are a best guess.
    """

    def __init__(self, base_url: str = "https://rulings.cbp.gov"):
        self.base_url = base_url

    def fetch_all(self) -> Iterable[dict]:
        raise NotImplementedError(
            "Implement against the confirmed CROSS bulk source (e.g. the data.gov "
            "dataset). Return dicts shaped for parse_ruling(). Confirm access is "
            "permitted before bulk pulling."
        )

    def fetch_recent(self, days: int = 30) -> Iterable[dict]:
        raise NotImplementedError(
            "Implement against CROSS's recency filter ('modified in last N days'). "
            "Return dicts shaped for parse_ruling()."
        )
