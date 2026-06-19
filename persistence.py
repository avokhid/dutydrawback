"""
Persistence layer.

Gives the system durable storage so claims, estimates, rulings, corrections, and
pipeline state survive restarts — the dependency under saved estimates, the
document repository, the audit trail, and (capability-only, not a user feature)
resumable pipeline state.

Design choices:
  - SQLite. Zero-config, ships with Python, real transactional semantics. The
    right first persistence layer; Cursor can swap the engine for Postgres later
    because everything goes through the Repository interface, not raw SQL in
    callers.
  - Store domain objects as JSON in rows, keyed by claim_id. The Pydantic
    schemas (Entry7501, ExportRecord) already serialize/validate cleanly, and
    the dataclasses have to_json-style shapes. This keeps the schema flexible
    while the model is still evolving — we're not freezing a wide relational
    schema prematurely.
  - The Repository is the single seam. The in-memory ClaimStore stays for tests
    and ephemeral use; this is the durable alternative behind the same concepts.

Audit note: corrections, approvals, and rejections are append-only events here —
they are the audit trail, so they are never updated in place or deleted.
"""

from __future__ import annotations

import json
import sqlite3
import time
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Optional


SCHEMA = """
CREATE TABLE IF NOT EXISTS claims (
    claim_id     TEXT PRIMARY KEY,
    firm         TEXT,
    created_at   REAL NOT NULL,
    updated_at   REAL NOT NULL,
    status       TEXT NOT NULL DEFAULT 'draft'
);

-- Documents/entries/exports stored as JSON blobs keyed by claim.
CREATE TABLE IF NOT EXISTS documents (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    claim_id    TEXT NOT NULL,
    kind        TEXT NOT NULL,           -- 'import' | 'export'
    ref         TEXT NOT NULL,           -- entry_number / export_id
    source_doc  TEXT,                    -- original filename
    payload     TEXT NOT NULL,           -- JSON of the schema object
    FOREIGN KEY (claim_id) REFERENCES claims(claim_id),
    UNIQUE (claim_id, kind, ref)
);

-- Matches with their mutable status. status changes are allowed (pending ->
-- approved/rejected); the WHY is captured as append-only events below.
CREATE TABLE IF NOT EXISTS matches (
    match_id    TEXT NOT NULL,
    claim_id    TEXT NOT NULL,
    status      TEXT NOT NULL DEFAULT 'pending',
    payload     TEXT NOT NULL,           -- JSON of the CandidateMatch
    PRIMARY KEY (claim_id, match_id),
    FOREIGN KEY (claim_id) REFERENCES claims(claim_id)
);

-- Append-only audit trail. Never updated, never deleted.
CREATE TABLE IF NOT EXISTS events (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    claim_id    TEXT NOT NULL,
    at          REAL NOT NULL,
    kind        TEXT NOT NULL,           -- 'approve' | 'reject' | 'correction' | 'run' ...
    actor       TEXT,                    -- reviewer id, when known
    payload     TEXT NOT NULL,           -- JSON detail
    FOREIGN KEY (claim_id) REFERENCES claims(claim_id)
);

-- Persisted pipeline state (capability retained even though mid-flow user edit
-- is dropped as a feature — useful for resuming interrupted runs and audit).
CREATE TABLE IF NOT EXISTS pipeline_state (
    claim_id    TEXT PRIMARY KEY,
    payload     TEXT NOT NULL,           -- JSON snapshot of PipelineState
    updated_at  REAL NOT NULL,
    FOREIGN KEY (claim_id) REFERENCES claims(claim_id)
);
"""


@dataclass
class ClaimRecord:
    claim_id: str
    firm: Optional[str]
    created_at: float
    updated_at: float
    status: str


class Repository:
    """
    Durable storage behind a small, intention-revealing interface. Callers use
    these methods, never raw SQL — so the storage engine can change without
    touching application code.
    """

    def __init__(self, db_path: str = "drawback.db"):
        self.db_path = db_path
        self._init()

    def _init(self) -> None:
        with self._conn() as c:
            c.executescript(SCHEMA)

    @contextmanager
    def _conn(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    # --- claims ---

    def create_claim(self, claim_id: str, firm: Optional[str] = None) -> ClaimRecord:
        now = time.time()
        with self._conn() as c:
            c.execute(
                "INSERT OR REPLACE INTO claims (claim_id, firm, created_at, updated_at, status) "
                "VALUES (?, ?, ?, ?, 'draft')",
                (claim_id, firm, now, now),
            )
        return ClaimRecord(claim_id, firm, now, now, "draft")

    def get_claim(self, claim_id: str) -> Optional[ClaimRecord]:
        with self._conn() as c:
            row = c.execute("SELECT * FROM claims WHERE claim_id=?", (claim_id,)).fetchone()
        return ClaimRecord(**row) if row else None

    def list_claims(self) -> list[ClaimRecord]:
        with self._conn() as c:
            rows = c.execute("SELECT * FROM claims ORDER BY updated_at DESC").fetchall()
        return [ClaimRecord(**r) for r in rows]

    def _touch(self, c, claim_id: str) -> None:
        c.execute("UPDATE claims SET updated_at=? WHERE claim_id=?", (time.time(), claim_id))

    # --- documents ---

    def save_document(self, claim_id: str, kind: str, ref: str,
                      payload: dict, source_doc: Optional[str] = None) -> None:
        with self._conn() as c:
            c.execute(
                "INSERT OR REPLACE INTO documents (claim_id, kind, ref, source_doc, payload) "
                "VALUES (?, ?, ?, ?, ?)",
                (claim_id, kind, ref, source_doc, json.dumps(payload)),
            )
            self._touch(c, claim_id)

    def get_documents(self, claim_id: str, kind: Optional[str] = None) -> list[dict]:
        q = "SELECT kind, ref, source_doc, payload FROM documents WHERE claim_id=?"
        args: list[Any] = [claim_id]
        if kind:
            q += " AND kind=?"; args.append(kind)
        with self._conn() as c:
            rows = c.execute(q, args).fetchall()
        return [{"kind": r["kind"], "ref": r["ref"], "source_doc": r["source_doc"],
                 **json.loads(r["payload"])} for r in rows]

    # --- matches ---

    def save_match(self, claim_id: str, match_id: str, status: str, payload: dict) -> None:
        with self._conn() as c:
            c.execute(
                "INSERT OR REPLACE INTO matches (claim_id, match_id, status, payload) "
                "VALUES (?, ?, ?, ?)",
                (claim_id, match_id, status, json.dumps(payload)),
            )
            self._touch(c, claim_id)

    def set_match_status(self, claim_id: str, match_id: str, status: str) -> None:
        with self._conn() as c:
            c.execute("UPDATE matches SET status=? WHERE claim_id=? AND match_id=?",
                      (status, claim_id, match_id))
            self._touch(c, claim_id)

    def get_matches(self, claim_id: str, status: Optional[str] = None) -> list[dict]:
        q = "SELECT match_id, status, payload FROM matches WHERE claim_id=?"
        args: list[Any] = [claim_id]
        if status:
            q += " AND status=?"; args.append(status)
        with self._conn() as c:
            rows = c.execute(q, args).fetchall()
        return [{"match_id": r["match_id"], "status": r["status"], **json.loads(r["payload"])}
                for r in rows]

    # --- events (append-only audit trail) ---

    def append_event(self, claim_id: str, kind: str, payload: dict,
                     actor: Optional[str] = None) -> None:
        with self._conn() as c:
            c.execute(
                "INSERT INTO events (claim_id, at, kind, actor, payload) VALUES (?, ?, ?, ?, ?)",
                (claim_id, time.time(), kind, actor, json.dumps(payload)),
            )
            self._touch(c, claim_id)

    def get_events(self, claim_id: str) -> list[dict]:
        with self._conn() as c:
            rows = c.execute(
                "SELECT at, kind, actor, payload FROM events WHERE claim_id=? ORDER BY at",
                (claim_id,),
            ).fetchall()
        return [{"at": r["at"], "kind": r["kind"], "actor": r["actor"],
                 **json.loads(r["payload"])} for r in rows]

    # --- pipeline state (capability retained; not a user edit feature) ---

    def save_pipeline_state(self, claim_id: str, payload: dict) -> None:
        with self._conn() as c:
            c.execute(
                "INSERT OR REPLACE INTO pipeline_state (claim_id, payload, updated_at) "
                "VALUES (?, ?, ?)",
                (claim_id, json.dumps(payload), time.time()),
            )

    def get_pipeline_state(self, claim_id: str) -> Optional[dict]:
        with self._conn() as c:
            row = c.execute("SELECT payload FROM pipeline_state WHERE claim_id=?",
                            (claim_id,)).fetchone()
        return json.loads(row["payload"]) if row else None
