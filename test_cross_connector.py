"""
Tests for the CROSS connector logic, against a mock source.

The logic that matters and is fully verified here:
  - bulk_ingest loads the corpus and is idempotent (re-running doesn't duplicate)
  - sync_recent adds genuinely new rulings
  - sync_recent UPDATES a modified ruling in place
  - sync_recent RETIRES a ruling that has become revoked/superseded — the
    safety-critical transition — and the store then stops surfacing it as live
  - parse_ruling maps status strings correctly and never marks a real ingest as sample

The live fetch (LiveCrossSource) is untested by design — no network here.

Run: python3 -m pytest test_cross_connector.py -v
"""

from __future__ import annotations

from rulings import RulingsStore, RulingStatus
from cross_connector import (
    CrossConnector, MockRulingSource, parse_ruling,
)


def _raw(rid, status="active", hts=("8471.30.0100",), prov=("1313(j)(2)",), superseded_by=None):
    return {
        "ruling_id": rid, "date": "2024-01-01", "issue": f"issue {rid}",
        "holding": f"holding {rid}", "hts_codes": list(hts), "provisions": list(prov),
        "status": status, "superseded_by": superseded_by,
        "url": f"https://rulings.cbp.gov/ruling/{rid}",
    }


def test_bulk_ingest_loads_corpus():
    store = RulingsStore()
    src = MockRulingSource(all_records=[_raw("H1"), _raw("H2"), _raw("H3")])
    report = CrossConnector(store, src).bulk_ingest()
    assert report.added == 3 and report.total_seen == 3
    assert len(store.all()) == 3


def test_bulk_ingest_is_idempotent():
    store = RulingsStore()
    src = MockRulingSource(all_records=[_raw("H1"), _raw("H2")])
    conn = CrossConnector(store, src)
    conn.bulk_ingest()
    second = conn.bulk_ingest()
    # re-running updates in place, doesn't duplicate
    assert len(store.all()) == 2
    assert second.updated == 2 and second.added == 0


def test_parse_maps_status_and_not_sample():
    r = parse_ruling(_raw("H9", status="revoked"))
    assert r.status is RulingStatus.REVOKED
    assert r.is_sample is False


def test_sync_recent_adds_new():
    store = RulingsStore()
    # corpus already has H1
    CrossConnector(store, MockRulingSource(all_records=[_raw("H1")])).bulk_ingest()
    # a recency sync brings a brand-new H2
    src = MockRulingSource(all_records=[], recent_records=[_raw("H2")])
    report = CrossConnector(store, src).sync_recent()
    assert report.added == 1
    assert store.get("H2") is not None


def test_sync_recent_updates_modified():
    store = RulingsStore()
    CrossConnector(store, MockRulingSource(all_records=[_raw("H1")])).bulk_ingest()
    # H1 comes back modified with a new holding
    modified = _raw("H1", status="modified")
    modified["holding"] = "updated holding"
    report = CrossConnector(store, MockRulingSource([], [modified])).sync_recent()
    assert report.updated == 1
    assert store.get("H1").holding == "updated holding"
    assert store.get("H1").status is RulingStatus.MODIFIED


def test_sync_recent_retires_revoked_and_stops_surfacing():
    store = RulingsStore()
    # H1 starts live and is surfaced
    CrossConnector(store, MockRulingSource(all_records=[_raw("H1")])).bulk_ingest()
    assert store.relevant_to("8471.30.0100", "1313(j)(2)")  # surfaced while live

    # a later sync reports H1 as revoked
    report = CrossConnector(store, MockRulingSource([], [_raw("H1", status="revoked")])).sync_recent()
    assert report.retired == 1
    # it must no longer surface as a live, relevant ruling
    live = store.relevant_to("8471.30.0100", "1313(j)(2)")
    assert "H1" not in {r.ruling_id for r in live}


def test_sync_recent_handles_superseded():
    store = RulingsStore()
    CrossConnector(store, MockRulingSource(all_records=[_raw("OLD")])).bulk_ingest()
    sup = _raw("OLD", status="superseded", superseded_by="NEW")
    report = CrossConnector(store, MockRulingSource([], [sup])).sync_recent()
    assert report.retired == 1
    assert store.get("OLD").superseded_by == "NEW"


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
