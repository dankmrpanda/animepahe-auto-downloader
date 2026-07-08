from __future__ import annotations

import asyncio
from types import SimpleNamespace

import httpx
import pytest
from fastapi import FastAPI

from api import routes
from api.models import DownloadOption


class FakeAnimePaheClient:
    def __init__(self, *, fail_direct: bool = False):
        self.base_url = "https://animepahe.test"
        self.fail_direct = fail_direct
        self.episodes = [
            SimpleNamespace(episode=2.0, session="ep-2", title="Two"),
            SimpleNamespace(episode=1.0, session="ep-1", title="One"),
        ]

    async def get_all_episodes(self, anime_session: str):
        return self.episodes

    async def get_episode_download_options(self, anime_session: str, episode_session: str):
        episode_no = 2 if episode_session == "ep-2" else 1
        return [
            DownloadOption(
                pahe_link=f"https://pahe.win/e{episode_no}",
                quality="720p",
                resolution=720,
            )
        ]

    async def get_direct_download_link(self, pahe_link: str) -> str:
        if self.fail_direct:
            raise RuntimeError("Kwik still returned HTTP 403")
        return f"https://cdn.example/{pahe_link.rsplit('/', 1)[-1]}.mp4"


class FakeDownloadManager:
    def __init__(self):
        self.added: list[dict] = []
        self.is_paused = False

    def add_progress_callback(self, callback) -> None:
        self.callback = callback

    async def add_task(self, **kwargs):
        self.added.append(kwargs)
        return SimpleNamespace(id=f"task-{len(self.added)}")

    def get_status(self):
        return {"added": len(self.added)}


def make_app(client: FakeAnimePaheClient, manager: FakeDownloadManager) -> FastAPI:
    app = FastAPI()
    app.include_router(routes.router)
    routes.init_clients(client, manager, SimpleNamespace(default_resolution=0))
    return app


async def wait_for(predicate) -> None:
    for _ in range(50):
        if predicate():
            return
        await asyncio.sleep(0.01)
    raise AssertionError("Timed out waiting for background route task")


@pytest.mark.asyncio
async def test_download_route_enqueues_in_episode_order() -> None:
    manager = FakeDownloadManager()
    app = make_app(FakeAnimePaheClient(), manager)
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/download",
            json={
                "anime_session": "anime-1",
                "anime_title": "Example",
                "episodes": ["ep-2", "ep-1"],
                "resolution": 720,
            },
        )

    assert response.status_code == 200
    await wait_for(lambda: len(manager.added) == 2)
    assert [item["episode"] for item in manager.added] == [1.0, 2.0]
    assert [item["episode_session"] for item in manager.added] == ["ep-1", "ep-2"]


@pytest.mark.asyncio
async def test_manual_import_route_enqueues_in_episode_order() -> None:
    manager = FakeDownloadManager()
    app = make_app(FakeAnimePaheClient(), manager)
    transport = httpx.ASGITransport(app=app)

    payload = {
        "anime_session": "anime-1",
        "anime_title": "Example",
        "resolution": 720,
        "episodes": [
            {
                "episode": 2,
                "session": "ep-2",
                "anime_session": "anime-1",
                "options": [
                    {
                        "pahe_link": "https://pahe.win/e2",
                        "quality": "720p",
                        "resolution": 720,
                    }
                ],
            },
            {
                "episode": 1,
                "session": "ep-1",
                "anime_session": "anime-1",
                "options": [
                    {
                        "pahe_link": "https://pahe.win/e1",
                        "quality": "720p",
                        "resolution": 720,
                    }
                ],
            },
        ],
    }

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/api/download/manual-import", json=payload)

    assert response.status_code == 200
    await wait_for(lambda: len(manager.added) == 2)
    assert [item["episode"] for item in manager.added] == [1.0, 2.0]


@pytest.mark.asyncio
async def test_kwik_403_broadcasts_link_expired(monkeypatch: pytest.MonkeyPatch) -> None:
    manager = FakeDownloadManager()
    app = make_app(FakeAnimePaheClient(fail_direct=True), manager)
    transport = httpx.ASGITransport(app=app)
    broadcasts: list[tuple[str, str]] = []

    async def fake_broadcast_link_error(error_msg: str, anime_title: str) -> None:
        broadcasts.append((error_msg, anime_title))

    monkeypatch.setattr(routes, "broadcast_link_error", fake_broadcast_link_error)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/download",
            json={
                "anime_session": "anime-1",
                "anime_title": "Example",
                "episodes": ["ep-1"],
                "resolution": 720,
            },
        )

    assert response.status_code == 200
    await wait_for(lambda: bool(broadcasts))
    assert "link_expired" in broadcasts[0][0]
    assert broadcasts[0][1] == "Example"
    assert manager.added == []
