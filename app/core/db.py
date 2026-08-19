import json
import sqlite3
from pathlib import Path
from typing import Any

from core.settings import ROOT

DATA_DIR = ROOT / "data"
DB_PATH = DATA_DIR / "agent.db"


def get_db_path() -> Path:
    return DB_PATH


def connect_db() -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def init_db() -> None:
    with connect_db() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS tasks (
                task_file TEXT PRIMARY KEY,
                task_id TEXT NOT NULL,
                title TEXT NOT NULL,
                priority TEXT NOT NULL,
                project TEXT NOT NULL,
                kind TEXT NOT NULL,
                status TEXT NOT NULL,
                owner TEXT NOT NULL,
                attempts INTEGER NOT NULL DEFAULT 0,
                max_attempts INTEGER NOT NULL DEFAULT 0,
                blocked_by TEXT NOT NULL DEFAULT '',
                needs_human_reason TEXT NOT NULL DEFAULT '',
                last_run_id TEXT NOT NULL DEFAULT '',
                body_text TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS runs (
                run_id TEXT PRIMARY KEY,
                task_file TEXT NOT NULL DEFAULT '',
                task_text TEXT NOT NULL,
                status TEXT NOT NULL,
                attempt_count INTEGER NOT NULL,
                max_attempts INTEGER NOT NULL,
                current_subtask_id TEXT,
                current_prompt TEXT NOT NULL,
                next_capability TEXT NOT NULL,
                plan_summary TEXT NOT NULL DEFAULT '',
                human_summary TEXT NOT NULL DEFAULT '',
                last_test_output TEXT NOT NULL DEFAULT '',
                last_review TEXT NOT NULL DEFAULT '',
                artifacts_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS subtasks (
                run_id TEXT NOT NULL,
                subtask_id TEXT NOT NULL,
                title TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL,
                attempts INTEGER NOT NULL DEFAULT 0,
                acceptance_criteria_json TEXT NOT NULL DEFAULT '[]',
                sort_order INTEGER NOT NULL,
                PRIMARY KEY (run_id, subtask_id),
                FOREIGN KEY (run_id) REFERENCES runs(run_id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,
                role TEXT NOT NULL,
                type TEXT NOT NULL,
                message TEXT NOT NULL DEFAULT '',
                payload_json TEXT NOT NULL DEFAULT '{}',
                status TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
            CREATE INDEX IF NOT EXISTS idx_runs_status ON runs(status);
            CREATE INDEX IF NOT EXISTS idx_events_run_id ON events(run_id, id);
            """
        )


def reset_tasks_table() -> None:
    init_db()
    with connect_db() as conn:
        conn.execute("DELETE FROM tasks")


def reset_runs_table() -> None:
    init_db()
    with connect_db() as conn:
        conn.execute("DELETE FROM events")
        conn.execute("DELETE FROM subtasks")
        conn.execute("DELETE FROM runs")


def upsert_task_record(record: dict[str, Any]) -> None:
    init_db()
    with connect_db() as conn:
        conn.execute(
            """
            INSERT INTO tasks (
                task_file, task_id, title, priority, project, kind, status, owner,
                attempts, max_attempts, blocked_by, needs_human_reason, last_run_id, body_text,
                created_at, updated_at
            ) VALUES (
                :task_file, :task_id, :title, :priority, :project, :kind, :status, :owner,
                :attempts, :max_attempts, :blocked_by, :needs_human_reason, :last_run_id, :body_text,
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            )
            ON CONFLICT(task_file) DO UPDATE SET
                task_id = excluded.task_id,
                title = excluded.title,
                priority = excluded.priority,
                project = excluded.project,
                kind = excluded.kind,
                status = excluded.status,
                owner = excluded.owner,
                attempts = excluded.attempts,
                max_attempts = excluded.max_attempts,
                blocked_by = excluded.blocked_by,
                needs_human_reason = excluded.needs_human_reason,
                last_run_id = excluded.last_run_id,
                body_text = excluded.body_text,
                updated_at = CURRENT_TIMESTAMP
            """,
            record,
        )


def delete_task_record(task_file: str) -> None:
    init_db()
    with connect_db() as conn:
        conn.execute("DELETE FROM tasks WHERE task_file = ?", (task_file,))


def list_task_records(status: str | None = None) -> list[dict[str, Any]]:
    init_db()
    with connect_db() as conn:
        if status is None:
            rows = conn.execute("SELECT * FROM tasks ORDER BY updated_at DESC, task_id ASC").fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM tasks WHERE status = ? ORDER BY updated_at DESC, task_id ASC",
                (status,),
            ).fetchall()
    return [dict(row) for row in rows]


def get_task_record(task_file: str) -> dict[str, Any] | None:
    init_db()
    with connect_db() as conn:
        row = conn.execute("SELECT * FROM tasks WHERE task_file = ?", (task_file,)).fetchone()
    return dict(row) if row is not None else None


def upsert_run_record(record: dict[str, Any], subtasks: list[dict[str, Any]]) -> None:
    init_db()
    with connect_db() as conn:
        conn.execute(
            """
            INSERT INTO runs (
                run_id, task_file, task_text, status, attempt_count, max_attempts,
                current_subtask_id, current_prompt, next_capability, plan_summary,
                human_summary, last_test_output, last_review, artifacts_json,
                created_at, updated_at
            ) VALUES (
                :run_id, :task_file, :task_text, :status, :attempt_count, :max_attempts,
                :current_subtask_id, :current_prompt, :next_capability, :plan_summary,
                :human_summary, :last_test_output, :last_review, :artifacts_json,
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            )
            ON CONFLICT(run_id) DO UPDATE SET
                task_file = excluded.task_file,
                task_text = excluded.task_text,
                status = excluded.status,
                attempt_count = excluded.attempt_count,
                max_attempts = excluded.max_attempts,
                current_subtask_id = excluded.current_subtask_id,
                current_prompt = excluded.current_prompt,
                next_capability = excluded.next_capability,
                plan_summary = excluded.plan_summary,
                human_summary = excluded.human_summary,
                last_test_output = excluded.last_test_output,
                last_review = excluded.last_review,
                artifacts_json = excluded.artifacts_json,
                updated_at = CURRENT_TIMESTAMP
            """,
            record,
        )
        conn.execute("DELETE FROM subtasks WHERE run_id = ?", (record["run_id"],))
        conn.executemany(
            """
            INSERT INTO subtasks (
                run_id, subtask_id, title, description, status, attempts,
                acceptance_criteria_json, sort_order
            ) VALUES (
                :run_id, :subtask_id, :title, :description, :status, :attempts,
                :acceptance_criteria_json, :sort_order
            )
            """,
            subtasks,
        )


def list_run_records() -> list[dict[str, Any]]:
    init_db()
    with connect_db() as conn:
        rows = conn.execute("SELECT * FROM runs ORDER BY run_id DESC").fetchall()
    return [dict(row) for row in rows]


def get_run_record(run_id: str) -> dict[str, Any] | None:
    init_db()
    with connect_db() as conn:
        row = conn.execute("SELECT * FROM runs WHERE run_id = ?", (run_id,)).fetchone()
    return dict(row) if row is not None else None


def update_run_task_file(run_id: str, task_file: str) -> None:
    init_db()
    with connect_db() as conn:
        conn.execute(
            """
            UPDATE runs
            SET task_file = ?, updated_at = CURRENT_TIMESTAMP
            WHERE run_id = ?
            """,
            (task_file, run_id),
        )


def get_run_subtasks(run_id: str) -> list[dict[str, Any]]:
    init_db()
    with connect_db() as conn:
        rows = conn.execute(
            "SELECT * FROM subtasks WHERE run_id = ? ORDER BY sort_order ASC",
            (run_id,),
        ).fetchall()
    return [dict(row) for row in rows]


def find_latest_resumable_run_record() -> dict[str, Any] | None:
    init_db()
    with connect_db() as conn:
        row = conn.execute(
            """
            SELECT * FROM runs
            WHERE status NOT IN ('done', 'blocked', 'needs_human')
            ORDER BY run_id DESC
            LIMIT 1
            """
        ).fetchone()
    return dict(row) if row is not None else None


def insert_event_record(record: dict[str, Any]) -> None:
    init_db()
    with connect_db() as conn:
        conn.execute(
            """
            INSERT INTO events (run_id, role, type, message, payload_json, status, created_at)
            VALUES (:run_id, :role, :type, :message, :payload_json, :status, :created_at)
            """,
            record,
        )


def list_event_records(run_id: str, limit: int = 10) -> list[dict[str, Any]]:
    init_db()
    with connect_db() as conn:
        rows = conn.execute(
            """
            SELECT role, type, message, payload_json, status, created_at
            FROM events
            WHERE run_id = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (run_id, limit),
        ).fetchall()
    results = [dict(row) for row in reversed(rows)]
    for item in results:
        item["payload"] = json.loads(item.pop("payload_json") or "{}")
    return results
