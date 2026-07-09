"""Guard tests for the backup/import route (must never wipe on empty payload)."""

from __future__ import annotations


from types import SimpleNamespace


import pytest

httpx = pytest.importorskip("httpx")
pytest.importorskip("fastapi")


from fastapi import FastAPI


from api import routes


class FakeManager:
    def __init__(self) -> None:
        self.active_tasks: dict = {}
        self.is_paused = False

    def add_progress_callback(self, callback) -> None:  # noqa: D401 - test stub
        self.callback = callback

    def set_link_resolver(self, resolver) -> None:  # noqa: D401 - test stub
        self.resolver = resolver


def make_app() -> FastAPI:
    app = FastAPI()
    app.include_router(routes.router)
    routes.init_clients(
        SimpleNamespace(base_url="https://animepahe.test"),
        FakeManager(),
        SimpleNamespace(default_resolution=0),
    )
    return app


@pytest.mark.asyncio
async def test_backup_import_empty_payload_is_rejected() -> None:
    app = make_app()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/api/backup/import", json={})

    # An empty body must be rejected before any destructive state_store call.
    assert response.status_code == 400
    detail = response.json()["detail"].lower()
    assert "settings" in detail or "tasks" in detail
