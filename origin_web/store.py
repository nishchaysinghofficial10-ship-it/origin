"""Durable SQLite queue, rate limits, and audit records for the beta."""
from __future__ import annotations

import json
import secrets
import shutil
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any


ACTIVE = ("queued", "running", "pause_requested", "cancel_requested")
TERMINAL = ("completed", "cancelled", "failed")
ALL_STATUSES = ACTIVE + ("paused",) + TERMINAL


class StoreError(RuntimeError):
    pass


class Conflict(StoreError):
    pass


class NotFound(StoreError):
    pass


class IntakeClosed(StoreError):
    pass


class QuotaExceeded(StoreError):
    pass


class Store:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._local = threading.local()
        self._migrate()
        try:
            self.path.chmod(0o600)
        except OSError:
            pass

    def _connection(self) -> sqlite3.Connection:
        connection = getattr(self._local, "connection", None)
        if connection is None:
            connection = sqlite3.connect(self.path, timeout=10,
                                         isolation_level=None)
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA foreign_keys=ON")
            connection.execute("PRAGMA busy_timeout=10000")
            self._local.connection = connection
        return connection

    def close(self) -> None:
        connection = getattr(self._local, "connection", None)
        if connection is not None:
            connection.close()
            self._local.connection = None

    def _migrate(self) -> None:
        connection = sqlite3.connect(self.path)
        try:
            connection.executescript("""
                PRAGMA journal_mode=WAL;
                PRAGMA synchronous=FULL;
                CREATE TABLE IF NOT EXISTS missions (
                    id TEXT PRIMARY KEY,
                    owner_hash TEXT NOT NULL,
                    question TEXT NOT NULL,
                    domain TEXT NOT NULL,
                    profile TEXT NOT NULL,
                    status TEXT NOT NULL CHECK(status IN (
                        'queued','running','pause_requested','paused',
                        'cancel_requested','cancelled','completed','failed')),
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL,
                    started_at REAL,
                    completed_at REAL,
                    worker_id TEXT,
                    step INTEGER NOT NULL DEFAULT 0,
                    phase TEXT NOT NULL DEFAULT 'queued',
                    stop_reason TEXT NOT NULL DEFAULT '',
                    experiments_used INTEGER NOT NULL DEFAULT 0,
                    error TEXT NOT NULL DEFAULT ''
                );
                CREATE INDEX IF NOT EXISTS idx_missions_queue
                    ON missions(status, created_at);
                CREATE INDEX IF NOT EXISTS idx_missions_owner
                    ON missions(owner_hash, created_at DESC);
                CREATE TABLE IF NOT EXISTS audit (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts REAL NOT NULL,
                    principal_hash TEXT NOT NULL,
                    action TEXT NOT NULL,
                    mission_id TEXT NOT NULL DEFAULT '',
                    outcome TEXT NOT NULL,
                    detail TEXT NOT NULL DEFAULT ''
                );
                CREATE INDEX IF NOT EXISTS idx_audit_ts ON audit(ts);
                CREATE TABLE IF NOT EXISTS rate_limits (
                    principal_hash TEXT NOT NULL,
                    minute_bucket INTEGER NOT NULL,
                    count INTEGER NOT NULL,
                    PRIMARY KEY(principal_hash, minute_bucket)
                );
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at REAL NOT NULL
                );
                INSERT OR IGNORE INTO settings(key, value, updated_at)
                    VALUES ('accepting_jobs', '1', 0);
            """)
            connection.commit()
        finally:
            connection.close()

    @staticmethod
    def _public(row: sqlite3.Row | None) -> dict[str, Any] | None:
        if row is None:
            return None
        data = dict(row)
        data.pop("owner_hash", None)
        data.pop("worker_id", None)
        data["links"] = {
            "self": f"/api/v1/missions/{data['id']}",
            "dossier": f"/api/v1/missions/{data['id']}/dossier",
        }
        return data

    def audit(self, principal_hash: str, action: str, outcome: str,
              mission_id: str = "", detail: str = "") -> None:
        clean_detail = detail.replace("\n", " ")[:500]
        self._connection().execute(
            "INSERT INTO audit(ts,principal_hash,action,mission_id,outcome,detail) "
            "VALUES(?,?,?,?,?,?)",
            (time.time(), principal_hash, action[:80], mission_id[:40],
             outcome[:40], clean_detail))

    def rate_allowed(self, principal_hash: str, limit: int,
                     now: float | None = None) -> tuple[bool, int]:
        current = time.time() if now is None else now
        bucket = int(current // 60)
        connection = self._connection()
        connection.execute("BEGIN IMMEDIATE")
        try:
            connection.execute(
                "INSERT INTO rate_limits(principal_hash,minute_bucket,count) "
                "VALUES(?,?,1) ON CONFLICT(principal_hash,minute_bucket) "
                "DO UPDATE SET count=count+1", (principal_hash, bucket))
            count = connection.execute(
                "SELECT count FROM rate_limits WHERE principal_hash=? AND "
                "minute_bucket=?", (principal_hash, bucket)).fetchone()[0]
            connection.execute(
                "DELETE FROM rate_limits WHERE minute_bucket < ?", (bucket - 2,))
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        return count <= limit, max(0, limit - count)

    def accepting_jobs(self) -> bool:
        row = self._connection().execute(
            "SELECT value FROM settings WHERE key='accepting_jobs'").fetchone()
        return bool(row and row[0] == "1")

    def set_accepting_jobs(self, accepting: bool) -> None:
        self._connection().execute(
            "UPDATE settings SET value=?,updated_at=? WHERE key='accepting_jobs'",
            ("1" if accepting else "0", time.time()))

    def can_create(self, owner_hash: str, active_limit: int,
                   daily_limit: int, now: float | None = None) -> tuple[bool, str]:
        current = time.time() if now is None else now
        connection = self._connection()
        placeholders = ",".join("?" for _ in ACTIVE)
        active = connection.execute(
            f"SELECT count(*) FROM missions WHERE owner_hash=? AND status IN "
            f"({placeholders})", (owner_hash, *ACTIVE)).fetchone()[0]
        if active >= active_limit:
            return False, "active mission limit reached"
        daily = connection.execute(
            "SELECT count(*) FROM missions WHERE owner_hash=? AND created_at>=?",
            (owner_hash, current - 86_400)).fetchone()[0]
        if daily >= daily_limit:
            return False, "daily mission limit reached"
        return True, ""

    def create_mission(self, owner_hash: str, question: str, domain: str,
                       profile: str) -> dict[str, Any]:
        mission_id = "msn_" + secrets.token_hex(8)
        now = time.time()
        self._connection().execute(
            "INSERT INTO missions(id,owner_hash,question,domain,profile,status,"
            "created_at,updated_at) VALUES(?,?,?,?,?,'queued',?,?)",
            (mission_id, owner_hash, question, domain, profile, now, now))
        return self.get_mission(mission_id, owner_hash)

    def create_mission_limited(self, owner_hash: str, question: str,
                               domain: str, profile: str, *,
                               active_limit: int, daily_limit: int) -> dict[str, Any]:
        """Atomically enforce intake and quota limits while enqueueing."""
        mission_id = "msn_" + secrets.token_hex(8)
        now = time.time()
        connection = self._connection()
        connection.execute("BEGIN IMMEDIATE")
        try:
            accepting = connection.execute(
                "SELECT value FROM settings WHERE key='accepting_jobs'").fetchone()
            if accepting is None or accepting[0] != "1":
                raise IntakeClosed("new mission intake is temporarily disabled")
            placeholders = ",".join("?" for _ in ACTIVE)
            active = connection.execute(
                f"SELECT count(*) FROM missions WHERE owner_hash=? AND status IN "
                f"({placeholders})", (owner_hash, *ACTIVE)).fetchone()[0]
            if active >= active_limit:
                raise QuotaExceeded("active mission limit reached")
            daily = connection.execute(
                "SELECT count(*) FROM missions WHERE owner_hash=? AND created_at>=?",
                (owner_hash, now - 86_400)).fetchone()[0]
            if daily >= daily_limit:
                raise QuotaExceeded("daily mission limit reached")
            connection.execute(
                "INSERT INTO missions(id,owner_hash,question,domain,profile,status,"
                "created_at,updated_at) VALUES(?,?,?,?,?,'queued',?,?)",
                (mission_id, owner_hash, question, domain, profile, now, now))
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        return self.get_mission(mission_id, owner_hash)

    def get_mission(self, mission_id: str, owner_hash: str | None = None,
                    *, internal: bool = False) -> dict[str, Any]:
        if owner_hash is None:
            row = self._connection().execute(
                "SELECT * FROM missions WHERE id=?", (mission_id,)).fetchone()
        else:
            row = self._connection().execute(
                "SELECT * FROM missions WHERE id=? AND owner_hash=?",
                (mission_id, owner_hash)).fetchone()
        if row is None:
            raise NotFound("mission not found")
        return dict(row) if internal else self._public(row)

    def list_missions(self, owner_hash: str, limit: int = 20) -> list[dict[str, Any]]:
        rows = self._connection().execute(
            "SELECT * FROM missions WHERE owner_hash=? ORDER BY created_at DESC "
            "LIMIT ?", (owner_hash, min(max(1, limit), 50))).fetchall()
        return [self._public(row) for row in rows]

    def claim_next(self, worker_id: str) -> dict[str, Any] | None:
        connection = self._connection()
        connection.execute("BEGIN IMMEDIATE")
        try:
            row = connection.execute(
                "SELECT * FROM missions WHERE status='queued' "
                "ORDER BY created_at LIMIT 1").fetchone()
            if row is None:
                connection.commit()
                return None
            now = time.time()
            changed = connection.execute(
                "UPDATE missions SET status='running',worker_id=?,updated_at=?,"
                "started_at=COALESCE(started_at,?) WHERE id=? AND status='queued'",
                (worker_id, now, now, row["id"])).rowcount
            if changed != 1:
                connection.rollback()
                return None
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        return self.get_mission(row["id"], internal=True)

    def request_pause(self, mission_id: str, owner_hash: str) -> dict[str, Any]:
        connection = self._connection()
        connection.execute("BEGIN IMMEDIATE")
        try:
            current = connection.execute(
                "SELECT status FROM missions WHERE id=? AND owner_hash=?",
                (mission_id, owner_hash)).fetchone()
            if current is None:
                raise NotFound("mission not found")
            if current["status"] == "queued":
                target = "paused"
            elif current["status"] == "running":
                target = "pause_requested"
            elif current["status"] in ("paused", "pause_requested"):
                connection.commit()
                return self.get_mission(mission_id, owner_hash)
            else:
                raise Conflict(f"cannot pause a {current['status']} mission")
            connection.execute(
                "UPDATE missions SET status=?,updated_at=? WHERE id=? AND owner_hash=?",
                (target, time.time(), mission_id, owner_hash))
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        return self.get_mission(mission_id, owner_hash)

    def request_resume(self, mission_id: str, owner_hash: str, *,
                       active_limit: int | None = None) -> dict[str, Any]:
        connection = self._connection()
        connection.execute("BEGIN IMMEDIATE")
        try:
            current = connection.execute(
                "SELECT status FROM missions WHERE id=? AND owner_hash=?",
                (mission_id, owner_hash)).fetchone()
            if current is None:
                raise NotFound("mission not found")
            if current["status"] == "queued":
                connection.commit()
                return self.get_mission(mission_id, owner_hash)
            if current["status"] != "paused":
                raise Conflict(f"cannot resume a {current['status']} mission")
            if active_limit is not None:
                placeholders = ",".join("?" for _ in ACTIVE)
                active = connection.execute(
                    f"SELECT count(*) FROM missions WHERE owner_hash=? AND status IN "
                    f"({placeholders})", (owner_hash, *ACTIVE)).fetchone()[0]
                if active >= active_limit:
                    raise QuotaExceeded("active mission limit reached")
            connection.execute(
                "UPDATE missions SET status='queued',worker_id=NULL,updated_at=? "
                "WHERE id=? AND owner_hash=?", (time.time(), mission_id, owner_hash))
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        return self.get_mission(mission_id, owner_hash)

    def request_cancel(self, mission_id: str, owner_hash: str) -> dict[str, Any]:
        connection = self._connection()
        connection.execute("BEGIN IMMEDIATE")
        try:
            current = connection.execute(
                "SELECT status FROM missions WHERE id=? AND owner_hash=?",
                (mission_id, owner_hash)).fetchone()
            if current is None:
                raise NotFound("mission not found")
            if current["status"] in ("queued", "paused"):
                target = "cancelled"
            elif current["status"] in ("running", "pause_requested"):
                target = "cancel_requested"
            elif current["status"] in ("cancelled", "cancel_requested"):
                connection.commit()
                return self.get_mission(mission_id, owner_hash)
            else:
                raise Conflict(f"cannot cancel a {current['status']} mission")
            now = time.time()
            connection.execute(
                "UPDATE missions SET status=?,updated_at=?,completed_at=? "
                "WHERE id=? AND owner_hash=?",
                (target, now, now if target == "cancelled" else None,
                 mission_id, owner_hash))
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        return self.get_mission(mission_id, owner_hash)

    def worker_control(self, mission_id: str) -> str:
        return self.get_mission(mission_id, internal=True)["status"]

    def update_progress(self, mission_id: str, state: dict[str, Any]) -> None:
        meta = state.get("meta", {})
        budget = state.get("budget", {})
        phase = str(meta.get("phase", "unknown"))[:80]
        self._connection().execute(
            "UPDATE missions SET step=?,phase=?,stop_reason=?,"
            "experiments_used=?,updated_at=? WHERE id=?",
            (int(state.get("step", 0)), phase,
             str(meta.get("stop_reason", ""))[:500],
             int(budget.get("experiments_used", 0)), time.time(), mission_id))

    def worker_pause(self, mission_id: str) -> None:
        self._connection().execute(
            "UPDATE missions SET status='paused',worker_id=NULL,updated_at=? "
            "WHERE id=? AND status='pause_requested'", (time.time(), mission_id))

    def finish(self, mission_id: str, status: str, *, error: str = "",
               stop_reason: str = "") -> None:
        if status not in TERMINAL:
            raise ValueError("worker finish status must be terminal")
        now = time.time()
        self._connection().execute(
            "UPDATE missions SET status=?,phase=?,error=?,stop_reason=?,"
            "completed_at=?,updated_at=?,worker_id=NULL WHERE id=?",
            (status, status, error.replace("\n", " ")[:500], stop_reason[:500],
             now, now, mission_id))

    def recover_running(self, detail: str = "worker restarted") -> int:
        """Return abandoned work to the durable queue on worker startup."""
        now = time.time()
        rows = self._connection().execute(
            "SELECT id,owner_hash FROM missions WHERE status='running'").fetchall()
        for row in rows:
            self._connection().execute(
                "UPDATE missions SET status='queued',worker_id=NULL,error=?,"
                "updated_at=? WHERE id=?", (detail[:500], now, row["id"]))
            self.audit(row["owner_hash"], "worker_recovery", "requeued",
                       row["id"], detail)
        return len(rows)

    def pending_control(self, status: str) -> list[dict[str, Any]]:
        if status not in ("pause_requested", "cancel_requested"):
            raise ValueError("unsupported pending control status")
        rows = self._connection().execute(
            "SELECT * FROM missions WHERE status=? ORDER BY updated_at",
            (status,)).fetchall()
        return [dict(row) for row in rows]

    def audit_rows(self, limit: int = 100) -> list[dict[str, Any]]:
        rows = self._connection().execute(
            "SELECT * FROM audit ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        return [dict(row) for row in rows]

    def dump_health(self, now: float | None = None) -> dict[str, Any]:
        connection = self._connection()
        counts = {row["status"]: row["n"] for row in connection.execute(
            "SELECT status,count(*) AS n FROM missions GROUP BY status")}
        oldest = connection.execute(
            "SELECT MIN(updated_at) FROM missions WHERE status='queued'").fetchone()[0]
        current = time.time() if now is None else now
        oldest_queued_seconds = (0 if oldest is None else
                                 max(0, int(current - float(oldest))))
        storage = shutil.disk_usage(self.path.parent)
        return {"database": "ok", "queue": counts,
                "accepting_jobs": self.accepting_jobs(),
                "failed_missions": counts.get("failed", 0),
                "oldest_queued_seconds": oldest_queued_seconds,
                "storage": {
                    "free_bytes": storage.free,
                    "total_bytes": storage.total,
                }}
