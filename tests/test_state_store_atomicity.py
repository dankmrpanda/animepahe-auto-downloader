from __future__ import annotations


import sqlite3


import pytest


from core import state_store


def _rec(task_id: str, **over) -> dict:
    """Build a valid download_tasks record for persistence tests."""
    rec = {
        "id": task_id,
        "url": f"https://cdn.example/{task_id}.mp4",
        "filename": f"{task_id}.mp4",
        "anime_title": "Example",
        "anime_session": "anime-1",
        "episode_session": f"ep-{task_id}",
        "download_options": None,
        "episode": 1.0,
        "resolution": 720,
        "status": "completed",
        "progress": 100.0,
        "downloaded_bytes": 10,
        "total_bytes": 10,
        "speed": 0.0,
        "error": None,
        "failure_reason": None,
        "failure_detail": None,
        "retry_count": 0,
        "max_retries": 3,
        "terminal": 0,
        "created_at": "2026-01-01T00:00:00",
        "started_at": None,
        "completed_at": "2026-01-01T00:00:01",
        "updated_at": "2026-01-01T00:00:02",
    }
    rec.update(over)
    return rec


def test_replace_download_tasks_replaces_contents(tmp_path) -> None:
    db = tmp_path / "state.sqlite3"
    state_store.upsert_download_tasks([_rec("a"), _rec("b")], db_path=db)

    state_store.replace_download_tasks([_rec("c")], db_path=db)

    rows = {row["id"] for row in state_store.load_download_tasks(db_path=db)}
    assert rows == {"c"}


def test_replace_download_tasks_is_atomic_on_failure(tmp_path) -> None:
    """A failed replace must not wipe the existing rows (single transaction)."""
    db = tmp_path / "state.sqlite3"
    state_store.upsert_download_tasks([_rec("keep-1"), _rec("keep-2")], db_path=db)

    # Second record is missing required bind params -> INSERT raises.
    bad = {"id": "bad"}
    with pytest.raises((sqlite3.Error, KeyError, ValueError, TypeError)):
        state_store.replace_download_tasks([_rec("new"), bad], db_path=db)

    surviving = {row["id"] for row in state_store.load_download_tasks(db_path=db)}
    assert surviving == {"keep-1", "keep-2"}


def test_replace_settings_is_atomic_on_failure(tmp_path) -> None:
    db = tmp_path / "state.sqlite3"
    state_store.save_settings(
        {"download_path": "/tmp/keep", "max_workers": 4}, db_path=db
    )

    # A non-JSON-serializable value makes json.dumps raise mid-transaction,
    # after the DELETE. The whole transaction must roll back.
    with pytest.raises(TypeError):
        state_store.replace_settings(
            {"download_path": "/tmp/new", "bad": {1, 2, 3}},
            db_path=db,
        )

    settings = state_store.load_settings(db_path=db)
    assert settings.get("download_path") == "/tmp/keep"


def test_init_db_runs_once_when_guarded(tmp_path, monkeypatch) -> None:
    """init_db should be cheap to call repeatedly (guarded against re-running full schema)."""
    db = tmp_path / "state.sqlite3"
    state_store.init_db(db)

    calls = {"n": 0}
    real_connect = state_store._connect

    def counting_connect(db_path=state_store.STATE_DB_PATH):
        calls["n"] += 1
        return real_connect(db_path)

    monkeypatch.setattr(state_store, "_connect", counting_connect)
    # A pure write should not re-run schema creation / PRAGMA introspection.
    state_store.upsert_download_task(_rec("x"), db_path=db)
    assert calls["n"] <= 1
