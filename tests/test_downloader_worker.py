"""Safety-net tests for the web download worker/queue lifecycle.


Locks the sacred path: resolve link -> stream bytes -> integrity -> complete,
plus pause gating and cancellation. The transport session and (optionally)
file IO are faked; the DownloadManager logic runs for real.


Skipped automatically when aiofiles / curl_cffi are unavailable.
"""

from __future__ import annotations


import asyncio
import os


import pytest

pytest.importorskip("aiofiles")
pytest.importorskip("curl_cffi")


import time


from core import state_store
from core import downloader as downloader_module
from core.downloader import DownloadManager, DownloadTask


def _stub_store(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(state_store, "init_db", lambda *a, **k: None)
    monkeypatch.setattr(state_store, "upsert_download_task", lambda *a, **k: None)
    monkeypatch.setattr(state_store, "upsert_download_tasks", lambda *a, **k: None)
    monkeypatch.setattr(state_store, "prune_terminal_history", lambda *a, **k: None)
    monkeypatch.setattr(
        state_store, "mark_recoverable_tasks_pending", lambda *a, **k: 0
    )
    monkeypatch.setattr(state_store, "load_download_tasks", lambda *a, **k: [])
    monkeypatch.setattr(state_store, "delete_download_task", lambda *a, **k: None)
    monkeypatch.setattr(state_store, "delete_download_tasks", lambda *a, **k: None)


class FakeStreamResponse:
    def __init__(self, body: bytes, status: int = 200):
        self._body = body
        self.status_code = status
        self.headers = {"content-length": str(len(body))}

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def aiter_content(self, chunk_size: int = 8192):
        for i in range(0, len(self._body), chunk_size):
            yield self._body[i : i + chunk_size]


class FakeSession:
    def __init__(self, body: bytes):
        self._body = body

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    def stream(self, method: str, url: str, headers=None, allow_redirects=True):
        return FakeStreamResponse(self._body)


@pytest.mark.asyncio
async def test_worker_completes_download(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _stub_store(monkeypatch)
    body = b"BINARYCONTENT" * 200
    monkeypatch.setattr(
        downloader_module, "make_async_session", lambda **kw: FakeSession(body)
    )

    manager = DownloadManager(str(tmp_path), max_workers=1)

    async def resolver(task):
        return {"url": "https://cdn.example/e1.bin", "resolution": 720}

    manager.set_link_resolver(resolver)
    task = await manager.add_task(
        url="",
        anime_title="Example",
        episode=1.0,
        resolution=0,
        anime_session="anime-1",
        episode_session="ep-1",
        filename="EP01_720p.bin",  # non-mp4 skips container validation
    )
    assert task is not None

    await manager._download_file(task)

    assert task.status == "completed"
    assert task.progress == 100.0
    folder = manager._get_anime_folder("Example")
    final_path = os.path.join(folder, "EP01_720p.bin")
    assert os.path.exists(final_path)
    with open(final_path, "rb") as fh:
        assert fh.read() == body
    assert any(t.id == task.id for t in manager.completed_tasks)
    assert task.id not in manager.active_tasks


def test_episode_token_distinguishes_specials() -> None:
    from core.downloader import _default_filename

    assert _default_filename(1.0, 720) == "EP01_720p.mp4"
    assert _default_filename(1.5, 720) == "EP01.5_720p.mp4"
    assert _default_filename(1.0, 720) != _default_filename(1.5, 720)


@pytest.mark.asyncio
async def test_existing_valid_file_is_not_redownloaded(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A resolved target that already exists must not be re-downloaded/overwritten."""
    _stub_store(monkeypatch)

    class BoomSession:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

        def stream(self, *args, **kwargs):
            raise AssertionError("download must not start when the file already exists")

    monkeypatch.setattr(
        downloader_module, "make_async_session", lambda **kw: BoomSession()
    )
    manager = DownloadManager(str(tmp_path), max_workers=1)
    manager.set_link_resolver(
        lambda task: {"url": "https://cdn.example/e.bin", "resolution": 720}
    )

    folder = manager._get_anime_folder("Example")
    with open(os.path.join(folder, "EP01_720p.bin"), "wb") as fh:
        fh.write(b"already downloaded")

    task = await manager.add_task(
        url="",
        anime_title="Example",
        episode=1.0,
        resolution=0,
        anime_session="anime-1",
        episode_session="ep-1",
        filename="EP01_720p.bin",
    )
    await manager._download_file(task)

    assert task.status == "completed"
    assert any(t.id == task.id for t in manager.completed_tasks)
    with open(os.path.join(folder, "EP01_720p.bin"), "rb") as fh:
        assert fh.read() == b"already downloaded"  # untouched


@pytest.mark.asyncio
async def test_cancel_pending_task_removes_from_queue(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _stub_store(monkeypatch)
    manager = DownloadManager(str(tmp_path), max_workers=1)
    manager.set_link_resolver(
        lambda task: {"url": "https://cdn.example/e.bin", "resolution": 720}
    )

    task = await manager.add_task(
        url="",
        anime_title="Example",
        episode=1.0,
        resolution=0,
        anime_session="anime-1",
        episode_session="ep-1",
    )
    assert task is not None

    cancelled = await manager.cancel_task(task.id)

    assert cancelled is True
    assert task.id not in {t.id for t in manager._pending_tasks_snapshot()}
    assert any(t.id == task.id for t in manager.failed_tasks)


@pytest.mark.asyncio
async def test_paused_queue_does_not_start_downloads(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _stub_store(monkeypatch)
    body = b"data" * 10
    monkeypatch.setattr(
        downloader_module, "make_async_session", lambda **kw: FakeSession(body)
    )

    manager = DownloadManager(str(tmp_path), max_workers=1)
    resolver_started = asyncio.Event()

    async def resolver(task):
        resolver_started.set()
        return {"url": "https://cdn.example/e.bin", "resolution": 720}

    manager.set_link_resolver(resolver)

    await manager.start()
    try:
        manager.pause()
        await manager.add_task(
            url="",
            anime_title="Example",
            episode=1.0,
            resolution=0,
            anime_session="anime-1",
            episode_session="ep-1",
            filename="EP01.bin",
        )
        await asyncio.sleep(0.2)
        assert not resolver_started.is_set()  # paused: worker must not pick it up

        manager.resume()
        await asyncio.wait_for(resolver_started.wait(), timeout=2.0)
    finally:
        await manager.stop()


@pytest.mark.asyncio
async def test_queue_retry_does_not_block_worker(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Retry backoff must be scheduled in the background, not slept inline."""
    _stub_store(monkeypatch)
    manager = DownloadManager(str(tmp_path), max_workers=1)
    manager._running = True

    task = DownloadTask(
        id="t1",
        url="https://cdn.example/e.bin",
        filename="EP01_720p.bin",
        anime_title="Example",
        episode=1.0,
        resolution=720,
        anime_session="anime-1",
        episode_session="ep-1",
        max_retries=3,
    )

    start = time.monotonic()
    await manager._queue_retry(
        task, RuntimeError("HTTP 500"), backoff=1, fresh_link=False
    )
    elapsed = time.monotonic() - start

    # _queue_retry returned immediately (did not sleep the full backoff inline).
    assert elapsed < 0.5
    assert task.status == "pending"
    assert task.retry_count == 1
    assert task.id not in {t.id for t in manager._pending_tasks_snapshot()}

    # During backoff the task is tracked (visible/cancellable), not lost.
    assert "t1" in manager._retrying_tasks
    assert any(t["id"] == "t1" for t in manager.get_status()["pending"])

    # The background task re-enqueues after the backoff elapses.
    await asyncio.sleep(1.2)
    assert task.id in {t.id for t in manager._pending_tasks_snapshot()}

    manager._shutdown_requested = True
    manager._running = False
    await manager._cancel_retry_tasks()


@pytest.mark.asyncio
async def test_cancel_all_stops_a_retrying_task(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Stop All must stop a task waiting out a retry backoff (not let it re-download)."""
    _stub_store(monkeypatch)
    manager = DownloadManager(str(tmp_path), max_workers=1)
    manager._running = True

    task = DownloadTask(
        id="t1",
        url="https://cdn.example/e.bin",
        filename="EP01_720p.bin",
        anime_title="Example",
        episode=1.0,
        resolution=720,
        anime_session="anime-1",
        episode_session="ep-1",
        max_retries=3,
    )
    await manager._queue_retry(
        task, RuntimeError("HTTP 500"), backoff=30, fresh_link=False
    )
    assert "t1" in manager._retrying_tasks

    count = await manager.cancel_all_tasks()

    assert count >= 1
    assert "t1" not in manager._retrying_tasks
    assert task.status == "stopped"
    # The retry timer was cancelled, so it must NOT re-enqueue.
    await asyncio.sleep(0.1)
    assert "t1" not in {t.id for t in manager._pending_tasks_snapshot()}
    manager._running = False
    await manager._cancel_retry_tasks()


@pytest.mark.asyncio
async def test_adjust_workers_scales_up_to_target(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _stub_store(monkeypatch)
    manager = DownloadManager(str(tmp_path), max_workers=2)
    await manager.start()
    try:
        await manager.adjust_workers(4)
        live = sum(1 for t in manager._workers.values() if not t.done())
        assert live == 4
        assert manager.max_workers == 4
    finally:
        await manager.stop()


@pytest.mark.asyncio
async def test_adjust_workers_recovers_after_scale_down_then_up(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _stub_store(monkeypatch)
    manager = DownloadManager(str(tmp_path), max_workers=4)
    await manager.start()
    try:
        await manager.adjust_workers(1)
        # Let workers with id >= 1 self-exit before scaling back up.
        for _ in range(40):
            await asyncio.sleep(0.1)
            if sum(1 for t in manager._workers.values() if not t.done()) <= 1:
                break
        await manager.adjust_workers(4)
        await asyncio.sleep(0.05)
        live = sum(1 for t in manager._workers.values() if not t.done())
        assert live == 4
    finally:
        await manager.stop()


@pytest.mark.asyncio
async def test_pause_and_drain_returns_true_when_idle(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _stub_store(monkeypatch)
    manager = DownloadManager(str(tmp_path), max_workers=1)
    drained = await manager.pause_and_drain(timeout=1.0)
    assert drained is True
    assert manager.is_paused is True
