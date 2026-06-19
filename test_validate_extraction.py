"""
Tests for the validation harness LOGIC — the parts that don't need the live API.

The live extraction (validate_one calling the real API) can't be tested here.
But the harness's own logic — null counting, verdict assignment, scorecard
aggregation — can and should be, so the scorecard you read in your environment
is trustworthy. We test those against synthetic DocResults and dicts.

Run: python3 -m pytest test_validate_extraction.py -v
"""

from __future__ import annotations

from validate_extraction import DocResult, scorecard, _count_nulls


def test_null_counting_walks_nested():
    obj = {
        "a": 1, "b": None,
        "lines": [{"x": 1, "y": None}, {"x": None, "y": 2}],
    }
    nulls, total = _count_nulls(obj)
    # leaves: a=1, b=None, x=1, y=None, x=None, y=2 -> 6 total, 3 null
    assert total == 6
    assert nulls == 3


def test_null_counting_skips_provenance_scaffolding():
    # provenance bbox/confidence are routinely null; they must not count as the
    # model being "unsure about a value", or a clean extraction reads as shaky.
    obj = {
        "entry_number": "ENT-1",
        "line_items": [
            {
                "hts_code": "8471300100",
                "quantity": "1000",
                "provenance": {
                    "hts_code": {"page": 1, "bbox": None, "confidence": None},
                    "quantity": {"page": 1, "bbox": None, "confidence": None},
                },
            }
        ],
    }
    nulls, total = _count_nulls(obj)
    # only the 3 real data leaves are counted (entry_number, hts_code, quantity),
    # none null — provenance's null bbox/confidence are ignored
    assert nulls == 0
    assert total == 3


def test_doc_result_null_rate():
    r = DocResult(filename="x.pdf", outcome="extracted", null_fields=2, total_fields=10)
    assert r.null_rate == 0.2


def test_scorecard_aggregates_verdicts():
    results = [
        DocResult("a.pdf", "extracted", verdict="pass", total_fields=10, null_fields=0, latency_s=2.0),
        DocResult("b.pdf", "extracted", verdict="needs_review", gate_findings=1, total_fields=10, null_fields=1, latency_s=3.0),
        DocResult("c.pdf", "schema_error", verdict="fail", error="bad shape", latency_s=1.0),
    ]
    card = scorecard(results)
    assert card["documents"] == 3
    assert card["verdicts"]["pass"] == 1
    assert card["verdicts"]["needs_review"] == 1
    assert card["verdicts"]["fail"] == 1
    # extraction success = 2 of 3 produced a parseable entry
    assert card["extraction_success_rate"] == round(2 / 3, 3)


def test_scorecard_empty():
    card = scorecard([])
    assert card["documents"] == 0
    assert card["extraction_success_rate"] == 0


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
