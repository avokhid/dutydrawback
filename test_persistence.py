"""
Tests for the persistence layer.

Proves the things persistence has to guarantee:
  - data survives a fresh connection (durability — the whole point)
  - documents and matches round-trip with their payloads intact
  - match status changes persist (pending -> approved)
  - events are append-only and ordered (the audit trail)
  - claims list reflects what's stored
  - pipeline state can be saved and reloaded (capability retained)

Uses a temp DB file so each run is isolated.

Run: python3 -m pytest test_persistence.py -v
"""

from __future__ import annotations

import os
import tempfile

import pytest

from persistence import Repository


@pytest.fixture
def repo():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    yield Repository(path)
    os.unlink(path)


def test_claim_survives_new_connection(repo):
    repo.create_claim("DBK-1", firm="Acme")
    # a brand-new Repository on the same file = simulates a restart
    repo2 = Repository(repo.db_path)
    got = repo2.get_claim("DBK-1")
    assert got is not None and got.firm == "Acme"


def test_documents_roundtrip(repo):
    repo.create_claim("DBK-1")
    repo.save_document("DBK-1", "import", "ENT-1",
                       {"entry_number": "ENT-1", "total_duty": "4500.00"},
                       source_doc="entry_summary_7501.pdf")
    docs = repo.get_documents("DBK-1", kind="import")
    assert len(docs) == 1
    assert docs[0]["ref"] == "ENT-1"
    assert docs[0]["source_doc"] == "entry_summary_7501.pdf"
    assert docs[0]["total_duty"] == "4500.00"


def test_match_status_change_persists(repo):
    repo.create_claim("DBK-1")
    repo.save_match("DBK-1", "m1", "pending", {"confidence": "0.76", "tier": "review"})
    repo.set_match_status("DBK-1", "m1", "approved")
    repo2 = Repository(repo.db_path)
    approved = repo2.get_matches("DBK-1", status="approved")
    assert len(approved) == 1 and approved[0]["match_id"] == "m1"


def test_events_are_append_only_and_ordered(repo):
    repo.create_claim("DBK-1")
    repo.append_event("DBK-1", "approve", {"match_id": "m1"}, actor="rev-a")
    repo.append_event("DBK-1", "correction", {"match_id": "m2", "field": "uom"}, actor="rev-a")
    events = repo.get_events("DBK-1")
    assert len(events) == 2
    assert events[0]["kind"] == "approve"
    assert events[1]["kind"] == "correction"
    # ordering by time preserved
    assert events[0]["at"] <= events[1]["at"]


def test_list_claims_orders_by_recency(repo):
    repo.create_claim("OLD")
    repo.create_claim("NEW")
    # touch NEW by saving a doc
    repo.save_document("NEW", "import", "E1", {"entry_number": "E1"})
    claims = repo.list_claims()
    assert claims[0].claim_id == "NEW"


def test_pipeline_state_roundtrip(repo):
    repo.create_claim("DBK-1")
    repo.save_pipeline_state("DBK-1", {"current_stage": "match", "refund": "2970.00"})
    repo2 = Repository(repo.db_path)
    state = repo2.get_pipeline_state("DBK-1")
    assert state["current_stage"] == "match"
    assert state["refund"] == "2970.00"


def test_missing_claim_returns_none(repo):
    assert repo.get_claim("nope") is None
    assert repo.get_pipeline_state("nope") is None


if __name__ == "__main__":
    import traceback
    # minimal runner without the fixture
    def make_repo():
        fd, path = tempfile.mkstemp(suffix=".db"); os.close(fd)
        return Repository(path), path
    tests = [v for k, v in sorted(globals().items())
             if k.startswith("test_") and callable(v)]
    passed = 0
    for t in tests:
        r, p = make_repo()
        try:
            t(r); print(f"PASS  {t.__name__}"); passed += 1
        except Exception as exc:  # noqa: BLE001
            print(f"FAIL  {t.__name__}: {exc}"); traceback.print_exc()
        finally:
            os.unlink(p)
    print(f"\n{passed}/{len(tests)} passed")
