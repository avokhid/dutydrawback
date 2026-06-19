"""
Tests for the CBP rulings retrieval layer and the advisory layer.

Rulings: proves relevance matching by HTS/provision, that stale rulings are
excluded, that the revoked/modified chain is respected, and that every surfaced
ruling carries "confirm applicability" framing (never presented as a
determination). Advisory: proves the honest messaging is present and that no
fabricated adjudication pattern set is implied.

Run: python3 -m pytest test_rulings.py -v
"""

from __future__ import annotations

from rulings import (
    RulingsStore, Ruling, RulingStatus, seeded_store, SAMPLE_RULINGS,
)
from advisory import AdvisoryLayer


def test_relevant_by_hts_match_ranks_first():
    store = seeded_store()
    hits = store.relevant_to("8471.30.0100", "1313(j)(2)")
    assert hits, "expected at least one relevant ruling"
    # exact HTS + provision should rank above provision-only
    assert hits[0].hts_codes and "8471.30.0100" in hits[0].hts_codes


def test_stale_rulings_excluded_by_default():
    store = seeded_store()
    hits = store.relevant_to("8471.30.0100", "1313(j)(2)")
    ids = {r.ruling_id for r in hits}
    # SAMPLE-H000003 is SUPERSEDED — must not surface as live
    assert "SAMPLE-H000003" not in ids
    # but it's retrievable when explicitly including stale
    stale = store.relevant_to("8471.30.0100", "1313(j)(2)", include_stale=True)
    assert "SAMPLE-H000003" in {r.ruling_id for r in stale}


def test_every_ruling_carries_confirm_framing():
    store = seeded_store()
    for r in store.all():
        j = r.to_json()
        assert "confirm applicability" in j["disposition"].lower()


def test_samples_are_flagged_as_samples():
    # nothing seeded should masquerade as authoritative content
    store = seeded_store()
    assert all(r.is_sample for r in store.all())


def test_ingest_updates_existing_ruling():
    store = RulingsStore()
    store.ingest([Ruling(ruling_id="H1", date="2020-01-01", issue="x", holding="y",
                         hts_codes=["1234.56.7890"], provisions=["1313(j)(2)"])])
    # re-ingest same id as revoked -> should now be excluded from live results
    store.ingest([Ruling(ruling_id="H1", date="2020-01-01", issue="x", holding="y",
                         hts_codes=["1234.56.7890"], provisions=["1313(j)(2)"],
                         status=RulingStatus.REVOKED)])
    assert store.relevant_to("1234.56.7890", "1313(j)(2)") == []


def test_advisory_is_honest_not_a_pattern_engine():
    j = AdvisoryLayer().to_json()
    assert j["adjudications"]["has_comprehensive_data"] is False
    assert "not a comprehensive" in j["adjudications"]["message"].lower()
    assert "discretion" in j["discretion"]["message"].lower()
    # no fabricated pattern set seeded
    assert j["adjudications"]["illustrative_decisions"] == []


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
