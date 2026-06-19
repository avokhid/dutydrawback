"""API tests for the FastAPI backend."""

from __future__ import annotations

import io

from fastapi.testclient import TestClient

from backend.main import app

client = TestClient(app)

FAKE_PDF = io.BytesIO(b"%PDF-1.4 fake content")


def _post_process(mock_mode: str = "clean", claim_date: str | None = "2025-09-02"):
    FAKE_PDF.seek(0)
    data = {"mock_mode": mock_mode}
    if claim_date is not None:
        data["claim_date"] = claim_date
    return client.post(
        "/api/process",
        files={"file": ("test.pdf", FAKE_PDF, "application/pdf")},
        data=data,
    )


def test_health():
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_process_clean():
    resp = _post_process(mock_mode="clean")
    assert resp.status_code == 200
    body = resp.json()
    assert body["validation"]["ok"] is True
    assert len(body["validation"]["gates"]) == 0
    assert body["entry"]["entry_number"] == "ABC-1234567"


def test_process_corrupt():
    resp = _post_process(mock_mode="corrupt")
    assert resp.status_code == 200
    body = resp.json()
    assert body["validation"]["ok"] is False
    gates = body["validation"]["gates"]
    assert len(gates) >= 1
    line_math = [g for g in gates if g["code"] == "LINE_MATH"]
    assert len(line_math) == 1
    assert line_math[0]["line_number"] == 1
    assert line_math[0]["field"] == "entered_value"
