from __future__ import annotations


import pytest


from core import state_store
from core.downloader import DownloadManager


def stub_state_store(monkeypatch: pytest.MonkeyPatch) -> list[dict]:
    records: list[dict] = []
    monkeypatch.setattr(state_store, "init_db", lambda: None)
    monkeypatch.setattr(
        state_store, "upsert_download_task", lambda task: records.append(dict(task))
    )
    monkeypatch.setattr(
        state_store,
        "upsert_download_tasks",
        lambda tasks: records.extend(dict(task) for task in tasks),
    )
    monkeypatch.setattr(state_store, "prune_terminal_history", lambda cap: None)
    return records


@pytest.mark.asyncio
async def test_unresolved_task_uses_resolver_and_updates_resolution(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    records = stub_state_store(monkeypatch)
    manager = DownloadManager(str(tmp_path), max_workers=1)

    async def resolver(task):
        assert task.anime_session == "anime-1"
        assert task.episode_session == "ep-1"
        assert task.download_options == [
            {
                "pahe_link": "https://pahe.win/e1",
                "quality": "720p",
                "resolution": 720,
                "audio": "jpn",
                "size": "",
            }
        ]
        return {"url": "https://cdn.example/e1.mp4", "resolution": 720}

    manager.set_link_resolver(resolver)
    task = await manager.add_task(
        url="",
        anime_title="Example",
        episode=1.0,
        resolution=0,
        anime_session="anime-1",
        episode_session="ep-1",
        download_options=[
            {"pahe_link": "https://pahe.win/e1", "quality": "720p", "resolution": 720}
        ],
    )

    assert task is not None
    assert task.filename == "EP01_best.mp4"
    duplicate = await manager.add_task(
        url="",
        anime_title="Example",
        episode=1.0,
        resolution=0,
        anime_session="anime-1",
        episode_session="ep-1",
    )
    assert duplicate is None

    await manager._resolve_task_link(task)

    assert task.url == "https://cdn.example/e1.mp4"
    assert task.resolution == 720
    assert task.filename == "EP01_720p.mp4"
    assert records[-1]["url"] == "https://cdn.example/e1.mp4"


def test_link_expired_failure_can_retry_with_fresh_resolve(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stub_state_store(monkeypatch)
    manager = DownloadManager(str(tmp_path), max_workers=1)
    manager.set_link_resolver(
        lambda task: {"url": "https://cdn.example/e1.mp4", "resolution": 720}
    )

    task = manager._record_to_task(
        {
            "id": "task-1",
            "url": "https://cdn.example/old.mp4",
            "filename": "EP01_720p.mp4",
            "anime_title": "Example",
            "anime_session": "anime-1",
            "episode_session": "ep-1",
            "download_options": None,
            "episode": 1.0,
            "resolution": 720,
            "status": "downloading",
            "progress": 0,
            "downloaded_bytes": 0,
            "total_bytes": 0,
            "speed": 0,
            "error": None,
            "failure_reason": None,
            "failure_detail": None,
            "retry_count": 0,
            "max_retries": 1,
            "terminal": 0,
            "created_at": None,
            "started_at": None,
            "completed_at": None,
        }
    )

    assert manager._should_retry_with_fresh_link(
        task, RuntimeError("Kwik returned HTTP 403")
    )
    assert manager._should_retry_with_fresh_link(
        task,
        RuntimeError("Failed to fetch https://pahe.win/e after 3 attempts: HTTP 429"),
    )
    assert not manager._should_retry_with_fresh_link(
        task, RuntimeError("Kwik still returned HTTP 403")
    )
    task.retry_count = 1
    assert not manager._should_retry_with_fresh_link(
        task, RuntimeError("Kwik returned HTTP 403")
    )
