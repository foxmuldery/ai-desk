"""Small SQLite store for the AI Desk dry-run MVP."""
from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class TaskStore:
    def __init__(self, db_path: str | Path):
        self.db_path = str(db_path)
        self._lock = threading.RLock()
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS tasks (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    instruction TEXT NOT NULL,
                    target_device_id TEXT NOT NULL,
                    adapter TEXT NOT NULL,
                    working_directory_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    summary TEXT,
                    error_code TEXT,
                    idempotency_key TEXT UNIQUE
                );
                CREATE TABLE IF NOT EXISTS task_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id TEXT NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
                    at TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    detail_json TEXT NOT NULL
                );
            """)

    def create_task(
        self, *, instruction: str, target_device_id: str, adapter: str,
        working_directory_id: str, idempotency_key: str
    ) -> tuple[dict[str, Any], bool]:
        now = utc_now()
        with self._lock, self._connect() as conn:
            existing = conn.execute(
                "SELECT * FROM tasks WHERE idempotency_key = ?",
                (idempotency_key,),
            ).fetchone()
            if existing:
                return dict(existing), False

            task_id = "task_" + uuid.uuid4().hex[:16]
            title = instruction.strip().splitlines()[0][:100]
            conn.execute(
                """INSERT INTO tasks
                   (id, title, instruction, target_device_id, adapter,
                    working_directory_id, status, created_at, updated_at,
                    idempotency_key)
                   VALUES (?, ?, ?, ?, ?, ?, 'queued', ?, ?, ?)""",
                (task_id, title, instruction, target_device_id, adapter,
                 working_directory_id, now, now, idempotency_key),
            )
            self._event(conn, task_id, "task.queued", {"status": "queued"})
            return self.get_task(task_id, conn=conn), True

    def _event(self, conn: sqlite3.Connection, task_id: str,
               event_type: str, detail: dict[str, Any]) -> None:
        conn.execute(
            "INSERT INTO task_events(task_id, at, event_type, detail_json) VALUES (?, ?, ?, ?)",
            (task_id, utc_now(), event_type, json.dumps(detail, ensure_ascii=False)),
        )

    def add_event(self, task_id: str, event_type: str, detail: dict[str, Any]) -> None:
        with self._lock, self._connect() as conn:
            if not conn.execute("SELECT 1 FROM tasks WHERE id = ?", (task_id,)).fetchone():
                raise KeyError(task_id)
            self._event(conn, task_id, event_type, detail)

    def set_status(self, task_id: str, status: str, *, summary: str | None = None,
                   error_code: str | None = None) -> dict[str, Any]:
        now = utc_now()
        with self._lock, self._connect() as conn:
            if not conn.execute("SELECT 1 FROM tasks WHERE id = ?", (task_id,)).fetchone():
                raise KeyError(task_id)
            conn.execute(
                "UPDATE tasks SET status=?, updated_at=?, summary=?, error_code=? WHERE id=?",
                (status, now, summary, error_code, task_id),
            )
            self._event(conn, task_id, "task." + status, {
                "status": status, "summary": summary, "error_code": error_code
            })
            return self.get_task(task_id, conn=conn)

    def get_task(self, task_id: str, conn: sqlite3.Connection | None = None) -> dict[str, Any]:
        if conn is not None:
            row = conn.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
            return dict(row) if row else {}
        with self._connect() as db:
            row = db.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
            return dict(row) if row else {}

    def list_tasks(self, limit: int = 50) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM tasks ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()
            return [dict(row) for row in rows]

    def list_events(self, task_id: str) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT id, at, event_type, detail_json FROM task_events WHERE task_id=? ORDER BY id",
                (task_id,),
            ).fetchall()
            return [{
                "id": row["id"], "at": row["at"], "event_type": row["event_type"],
                "detail": json.loads(row["detail_json"])
            } for row in rows]
