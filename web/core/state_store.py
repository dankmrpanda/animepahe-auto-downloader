"""
SQLite persistence for settings and download queue/history state.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

STATE_DB_PATH = Path(__file__).resolve().parents[2] / "app_state.sqlite3"


def _connect(db_path: Path = STATE_DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path), timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    return conn


def _ensure_column(conn: sqlite3.Connection, table: str, column: str, definition: str) -> None:
    cols = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
    if column in cols:
        return
    conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def init_db(db_path: Path = STATE_DB_PATH) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with _connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS download_tasks (
                id TEXT PRIMARY KEY,
                url TEXT NOT NULL,
                filename TEXT NOT NULL,
                anime_title TEXT NOT NULL,
                anime_session TEXT,
                episode_session TEXT,
                download_options TEXT,
                episode REAL NOT NULL,
                resolution INTEGER NOT NULL,
                status TEXT NOT NULL,
                progress REAL NOT NULL DEFAULT 0,
                downloaded_bytes INTEGER NOT NULL DEFAULT 0,
                total_bytes INTEGER NOT NULL DEFAULT 0,
                speed REAL NOT NULL DEFAULT 0,
                error TEXT,
                failure_reason TEXT,
                failure_detail TEXT,
                retry_count INTEGER NOT NULL DEFAULT 0,
                max_retries INTEGER NOT NULL DEFAULT 3,
                terminal INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                started_at TEXT,
                completed_at TEXT,
                updated_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_download_tasks_status_updated
            ON download_tasks(status, updated_at DESC)
            """
        )

        # Lightweight migrations for existing databases.
        _ensure_column(conn, "download_tasks", "anime_session", "TEXT")
        _ensure_column(conn, "download_tasks", "episode_session", "TEXT")
        _ensure_column(conn, "download_tasks", "download_options", "TEXT")
        _ensure_column(conn, "download_tasks", "failure_reason", "TEXT")
        _ensure_column(conn, "download_tasks", "failure_detail", "TEXT")


def load_settings(db_path: Path = STATE_DB_PATH) -> dict[str, Any]:
    init_db(db_path)
    with _connect(db_path) as conn:
        rows = conn.execute("SELECT key, value FROM settings").fetchall()
    result: dict[str, Any] = {}
    for row in rows:
        try:
            result[row["key"]] = json.loads(row["value"])
        except json.JSONDecodeError:
            result[row["key"]] = row["value"]
    return result


def save_settings(values: dict[str, Any], db_path: Path = STATE_DB_PATH) -> None:
    init_db(db_path)
    with _connect(db_path) as conn:
        for key, value in values.items():
            conn.execute(
                """
                INSERT INTO settings(key, value)
                VALUES (?, ?)
                ON CONFLICT(key) DO UPDATE SET value=excluded.value
                """,
                (key, json.dumps(value)),
            )


def replace_settings(values: dict[str, Any], db_path: Path = STATE_DB_PATH) -> None:
    init_db(db_path)
    with _connect(db_path) as conn:
        conn.execute("DELETE FROM settings")
    save_settings(values, db_path=db_path)


def mark_recoverable_tasks_pending(db_path: Path = STATE_DB_PATH) -> int:
    """
    Convert in-flight tasks from a previous process into pending tasks.
    """
    init_db(db_path)
    now = datetime.now().isoformat()
    with _connect(db_path) as conn:
        cur = conn.execute(
            """
            UPDATE download_tasks
            SET status = 'pending',
                error = 'Recovered after restart',
                speed = 0,
                terminal = 0,
                updated_at = ?
            WHERE status IN ('downloading', 'stopping', 'pausing')
            """,
            (now,),
        )
        return cur.rowcount


def upsert_download_task(task: dict[str, Any], db_path: Path = STATE_DB_PATH) -> None:
    task = dict(task)
    task.setdefault("download_options", None)
    init_db(db_path)
    with _connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO download_tasks (
                id, url, filename, anime_title, anime_session, episode_session, download_options,
                episode, resolution, status,
                progress, downloaded_bytes, total_bytes, speed, error,
                failure_reason, failure_detail,
                retry_count, max_retries, terminal, created_at,
                started_at, completed_at, updated_at
            ) VALUES (
                :id, :url, :filename, :anime_title, :anime_session, :episode_session, :download_options,
                :episode, :resolution, :status,
                :progress, :downloaded_bytes, :total_bytes, :speed, :error,
                :failure_reason, :failure_detail,
                :retry_count, :max_retries, :terminal, :created_at,
                :started_at, :completed_at, :updated_at
            )
            ON CONFLICT(id) DO UPDATE SET
                url=excluded.url,
                filename=excluded.filename,
                anime_title=excluded.anime_title,
                anime_session=excluded.anime_session,
                episode_session=excluded.episode_session,
                download_options=excluded.download_options,
                episode=excluded.episode,
                resolution=excluded.resolution,
                status=excluded.status,
                progress=excluded.progress,
                downloaded_bytes=excluded.downloaded_bytes,
                total_bytes=excluded.total_bytes,
                speed=excluded.speed,
                error=excluded.error,
                failure_reason=excluded.failure_reason,
                failure_detail=excluded.failure_detail,
                retry_count=excluded.retry_count,
                max_retries=excluded.max_retries,
                terminal=excluded.terminal,
                created_at=excluded.created_at,
                started_at=excluded.started_at,
                completed_at=excluded.completed_at,
                updated_at=excluded.updated_at
            """,
            task,
        )


def upsert_download_tasks(tasks: list[dict[str, Any]], db_path: Path = STATE_DB_PATH) -> None:
    if not tasks:
        return
    tasks = [dict(task, download_options=task.get("download_options")) for task in tasks]
    init_db(db_path)
    with _connect(db_path) as conn:
        conn.executemany(
            """
            INSERT INTO download_tasks (
                id, url, filename, anime_title, anime_session, episode_session, download_options,
                episode, resolution, status,
                progress, downloaded_bytes, total_bytes, speed, error,
                failure_reason, failure_detail,
                retry_count, max_retries, terminal, created_at,
                started_at, completed_at, updated_at
            ) VALUES (
                :id, :url, :filename, :anime_title, :anime_session, :episode_session, :download_options,
                :episode, :resolution, :status,
                :progress, :downloaded_bytes, :total_bytes, :speed, :error,
                :failure_reason, :failure_detail,
                :retry_count, :max_retries, :terminal, :created_at,
                :started_at, :completed_at, :updated_at
            )
            ON CONFLICT(id) DO UPDATE SET
                url=excluded.url,
                filename=excluded.filename,
                anime_title=excluded.anime_title,
                anime_session=excluded.anime_session,
                episode_session=excluded.episode_session,
                download_options=excluded.download_options,
                episode=excluded.episode,
                resolution=excluded.resolution,
                status=excluded.status,
                progress=excluded.progress,
                downloaded_bytes=excluded.downloaded_bytes,
                total_bytes=excluded.total_bytes,
                speed=excluded.speed,
                error=excluded.error,
                failure_reason=excluded.failure_reason,
                failure_detail=excluded.failure_detail,
                retry_count=excluded.retry_count,
                max_retries=excluded.max_retries,
                terminal=excluded.terminal,
                created_at=excluded.created_at,
                started_at=excluded.started_at,
                completed_at=excluded.completed_at,
                updated_at=excluded.updated_at
            """,
            tasks,
        )


def load_download_tasks(db_path: Path = STATE_DB_PATH) -> list[dict[str, Any]]:
    init_db(db_path)
    with _connect(db_path) as conn:
        rows = conn.execute(
            """
            SELECT id, url, filename, anime_title, anime_session, episode_session, download_options,
                   episode, resolution, status,
                   progress, downloaded_bytes, total_bytes, speed, error,
                   failure_reason, failure_detail,
                   retry_count, max_retries, terminal, created_at,
                   started_at, completed_at, updated_at
            FROM download_tasks
            ORDER BY datetime(updated_at) DESC, datetime(created_at) DESC
            """
        ).fetchall()
    return [dict(row) for row in rows]


def delete_download_task(task_id: str, db_path: Path = STATE_DB_PATH) -> None:
    init_db(db_path)
    with _connect(db_path) as conn:
        conn.execute("DELETE FROM download_tasks WHERE id = ?", (task_id,))


def delete_download_tasks(task_ids: list[str], db_path: Path = STATE_DB_PATH) -> None:
    if not task_ids:
        return
    init_db(db_path)
    with _connect(db_path) as conn:
        conn.executemany("DELETE FROM download_tasks WHERE id = ?", [(task_id,) for task_id in task_ids])


def replace_download_tasks(tasks: list[dict[str, Any]], db_path: Path = STATE_DB_PATH) -> None:
    init_db(db_path)
    with _connect(db_path) as conn:
        conn.execute("DELETE FROM download_tasks")
    upsert_download_tasks(tasks, db_path=db_path)


def prune_terminal_history(cap: int, db_path: Path = STATE_DB_PATH) -> None:
    """
    Keep only the most recent `cap` terminal tasks (completed/failed/stopped).
    """
    if cap <= 0:
        return
    init_db(db_path)
    terminal = ("completed", "failed", "stopped")
    with _connect(db_path) as conn:
        conn.execute(
            """
            DELETE FROM download_tasks
            WHERE status IN (?, ?, ?)
              AND id NOT IN (
                SELECT id
                FROM download_tasks
                WHERE status IN (?, ?, ?)
                ORDER BY datetime(updated_at) DESC
                LIMIT ?
              )
            """,
            (*terminal, *terminal, cap),
        )
