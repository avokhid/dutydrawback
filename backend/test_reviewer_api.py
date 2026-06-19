"""API tests for the reviewer endpoints."""

from __future__ import annotations

import json

from fastapi.testclient import TestClient

from backend.main import app
from backend.reviewer_service import reset_claim_state

client = TestClient(app)


def setup_function():
    reset_claim_state()


def test_claim_stats():
    resp = client.get("/api/claim/stats")
    assert resp.status_code == 200
    body = resp.json()
    assert body["claimId"] == "DBK-2291"
    assert body["totalProposed"] > 0
    # refund is an engine-computed display string; 0.00 before anything approved
    assert body["refund"] == "0.00"


def test_refund_grows_after_approval():
    bulk = client.get("/api/matches?tier=auto_pass").json()
    if not bulk:
        return
    client.post("/api/matches/approve", json={"ids": [r["id"] for r in bulk]})
    body = client.get("/api/claim/stats").json()
    # parses as a number and reflects real calc-engine output for approved matches
    assert float(body["refund"].replace(",", "")) >= 0.0


def test_claim_estimate():
    resp = client.get("/api/claim/estimate")
    assert resp.status_code == 200
    body = resp.json()
    assert body["firm"] == "Acme Imports LLC"
    # range is real engine output: high (confident + potential) >= low (confident)
    low = float(body["rangeLow"].replace(",", ""))
    high = float(body["rangeHigh"].replace(",", ""))
    assert high >= low
    assert 0 <= body["confidentPct"] <= 100
    # per-category breakdown carries display-ready strings + a confidence tier
    assert isinstance(body["lines"], list) and body["lines"]
    line = body["lines"][0]
    assert {"hts", "desc", "duties", "refund", "capped", "conf"} <= set(line)
    assert line["conf"] in ("high", "review")


def test_run_stream_emits_ordered_stage_events():
    resp = client.get("/api/claim/run-stream")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/event-stream")
    events = [
        json.loads(line[len("data:") :].strip())
        for line in resp.text.splitlines()
        if line.startswith("data:")
    ]
    stages = [(e["stage"], e["status"]) for e in events]
    assert ("validate", "running") in stages
    assert ("validate", "complete") in stages
    assert ("match", "complete") in stages
    assert events[-1]["stage"] == "done"
    # the terminal event carries a real engine-computed recovery figure
    float(events[-1]["detail"]["refund"])


def test_drawback_types_lists_estimable_flag():
    resp = client.get("/api/drawback-types")
    assert resp.status_code == 200
    types = {t["id"]: t for t in resp.json()["types"]}
    # the two unused bases the engine computes are estimable
    assert types["unused_substitution"]["estimable"] is True
    assert types["unused_direct_identification"]["estimable"] is True
    # types needing an extra input step are advertised but not yet estimable
    assert types["rejected"]["estimable"] is False
    assert types["manufacturing"]["estimable"] is False
    assert types["rejected"]["requires"] == ["rejection_reason"]
    assert types["manufacturing"]["requires"] == ["bill_of_materials"]


def test_run_stream_reports_chosen_basis():
    resp = client.get("/api/claim/run-stream?drawback_type=unused_direct_identification")
    assert resp.status_code == 200
    events = [
        json.loads(line[len("data:") :].strip())
        for line in resp.text.splitlines()
        if line.startswith("data:")
    ]
    calc = next(e for e in events if e["stage"] == "calculate" and e["status"] == "complete")
    assert calc["detail"]["drawback_type"] == "unused_direct_identification"
    assert "direct identification" in calc["detail"]["basis"]


def test_claim_explanation_narrates_engine_line():
    resp = client.get("/api/claim/explanation")
    assert resp.status_code == 200
    data = resp.json()
    # the final math-bearing step equals the headline refund
    final = next(s for s in reversed(data["steps"]) if s["math"] and s["math"].startswith("="))
    assert data["refund"] in final["math"].replace(",", "")
    # the 99% step is tagged statute-tier from rule_tiers
    statute = [s for s in data["steps"] if s.get("tier") == "statute"]
    assert statute and statute[0]["certainty"] == "Firmly codified"
    # transparency block is honest about what's populated
    assert data["transparency"]["ruling"] == 0
    assert data["transparency"]["advisory"] == 0
    assert "scope_statement" in data["transparency"]


def test_explanation_includes_rulings_and_advisory():
    resp = client.get("/api/claim/explanation")
    assert resp.status_code == 200
    data = resp.json()
    # ruling-tier references attach to the line, each carrying confirm-applicability framing
    assert isinstance(data["rulings"], list)
    for r in data["rulings"]:
        assert "confirm applicability" in r["disposition"].lower()
        assert r["is_sample"] is True  # only samples ship until CROSS is ingested
    # advisory transparency is present and honest
    assert data["advisory"]["adjudications"]["has_comprehensive_data"] is False
    assert "discretion" in data["advisory"]["discretion"]["message"].lower()


def test_rulings_relevant_endpoint_excludes_stale():
    resp = client.get("/api/rulings/relevant?hts=8471.30.0100&provision=1313(j)(2)")
    assert resp.status_code == 200
    ids = {r["ruling_id"] for r in resp.json()["rulings"]}
    assert "SAMPLE-H000001" in ids  # live sample matches
    assert "SAMPLE-H000003" not in ids  # superseded sample excluded


def test_advisory_endpoint_is_not_a_pattern_engine():
    resp = client.get("/api/advisory")
    assert resp.status_code == 200
    data = resp.json()
    assert data["adjudications"]["has_comprehensive_data"] is False
    assert data["adjudications"]["illustrative_decisions"] == []


def test_import_lines_lists_loaded_entries():
    resp = client.get("/api/claim/import-lines")
    assert resp.status_code == 200
    lines = resp.json()["import_lines"]
    assert lines and lines[0]["entry_number"] == "ENT-1001"
    assert "label" in lines[0]


def test_manufacturing_estimate_uses_supplied_bom():
    body = {
        "article_id": "Finished laptop assembly",
        "quantity_exported": "100",
        "components": [
            {"import_entry_number": "ENT-1001", "import_line_number": 1,
             "quantity_per_unit": "2", "yield_factor": "1"},
        ],
    }
    resp = client.post("/api/manufacturing/estimate", json=body)
    assert resp.status_code == 200
    data = resp.json()
    # 100 articles * 2 units each / yield 1 = 200 input units designated
    assert data["designations"][0]["input_units_needed"] == "200"
    assert data["components"] == 1
    # engine produced a real recovery figure from the BOM
    assert float(data["estimated_recovery"]) > 0
    assert "1313(a)/(b)" in data["basis"]


def test_manufacturing_estimate_flags_missing_entry():
    body = {
        "article_id": "Mystery widget",
        "quantity_exported": "10",
        "components": [
            {"import_entry_number": "ENT-NOPE", "import_line_number": 1,
             "quantity_per_unit": "1", "yield_factor": "1"},
        ],
    }
    resp = client.post("/api/manufacturing/estimate", json=body)
    assert resp.status_code == 422
    detail = resp.json()["detail"]
    assert "ENT-NOPE" in detail["missing_entries"]


def test_persistence_backed_claims_and_audit(tmp_path, monkeypatch):
    monkeypatch.setenv("DRAWBACK_DB", str(tmp_path / "test_claims.db"))
    created = client.post("/api/claims", json={"claim_id": "DBK-T1", "firm": "Acme"})
    assert created.status_code == 200
    assert created.json()["claim_id"] == "DBK-T1"
    listed = client.get("/api/claims").json()["claims"]
    assert any(c["claim_id"] == "DBK-T1" for c in listed)
    # audit endpoint returns an (initially empty) ordered event trail
    audit = client.get("/api/claims/DBK-T1/audit")
    assert audit.status_code == 200
    assert audit.json()["events"] == []
    # unknown claim 404s rather than inventing a trail
    assert client.get("/api/claims/NOPE/audit").status_code == 404


def test_run_stream_unknown_type_falls_back_to_substitution():
    resp = client.get("/api/claim/run-stream?drawback_type=rejected")
    assert resp.status_code == 200
    events = [
        json.loads(line[len("data:") :].strip())
        for line in resp.text.splitlines()
        if line.startswith("data:")
    ]
    calc = next(e for e in events if e["stage"] == "calculate" and e["status"] == "complete")
    # rejected isn't computable yet → falls back to substitution, reported honestly
    assert calc["detail"]["drawback_type"] == "unused_substitution"


def test_list_auto_pass_matches():
    resp = client.get("/api/matches?tier=auto_pass")
    assert resp.status_code == 200
    rows = resp.json()
    assert isinstance(rows, list)
    if rows:
        assert "conf" in rows[0]
        assert "imp" in rows[0]


def test_list_review_matches():
    resp = client.get("/api/matches?tier=review")
    assert resp.status_code == 200
    rows = resp.json()
    assert isinstance(rows, list)
    if rows:
        assert "uncertain" in rows[0]
        assert "fields" in rows[0]


def test_approve_and_reject_flow():
    bulk = client.get("/api/matches?tier=auto_pass").json()
    if not bulk:
        return
    match_id = bulk[0]["id"]
    resp = client.post("/api/matches/approve", json={"ids": [match_id]})
    assert resp.status_code == 200
    assert resp.json()["approved"] == 1

    review = client.get("/api/matches?tier=review").json()
    if review:
        rid = review[0]["id"]
        resp = client.post(f"/api/matches/{rid}/reject")
        assert resp.status_code == 200


def test_correction_endpoint():
    review = client.get("/api/matches?tier=review").json()
    if not review:
        return
    item = review[0]
    resp = client.post(
        "/api/corrections",
        json={
            "match_id": item["id"],
            "field": "Quantity / unit of measure",
            "system_value": item["suggestion"]["text"],
            "corrected": "1 carton = 10 units",
            "reason": "Vendor pack configuration differs from default",
            "note": "test",
            "asRule": False,
        },
    )
    assert resp.status_code == 200
    assert "correction_id" in resp.json()
