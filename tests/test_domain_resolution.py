from __future__ import annotations

from dataclasses import dataclass

import pytest

from core.animepahe import AnimePaheClient


@dataclass
class FakeResponse:
    status_code: int
    url: str
    payload: dict | None = None

    def json(self):
        if self.payload is None:
            raise ValueError("not json")
        return self.payload


class FakeSession:
    def __init__(self, responses: list[FakeResponse]):
        self.responses = responses
        self.urls: list[str] = []

    async def get(self, url: str, **kwargs):
        self.urls.append(url)
        if not self.responses:
            raise AssertionError("Unexpected request")
        return self.responses.pop(0)


@pytest.mark.asyncio
async def test_ensure_base_url_picks_first_200_candidate() -> None:
    client = AnimePaheClient()
    client._base_url_locked = False
    client._base_url_resolved = False
    client.base_url = "https://animepahe.com"
    session = FakeSession(
        [
            FakeResponse(403, "https://animepahe.com/"),
            FakeResponse(200, "https://animepahe.ru/api?m=search&l=1&q=naruto", {"data": []}),
        ]
    )

    await client.ensure_base_url(session)  # type: ignore[arg-type]

    assert client.base_url == "https://animepahe.ru"
    assert session.urls[:2] == [
        "https://animepahe.com/api?m=search&l=1&q=naruto",
        "https://animepahe.ru/api?m=search&l=1&q=naruto",
    ]


@pytest.mark.asyncio
async def test_ensure_base_url_respects_explicit_override() -> None:
    client = AnimePaheClient()
    client._base_url_locked = True
    client._base_url_resolved = False
    client.base_url = "https://pinned.example"
    session = FakeSession([])

    await client.ensure_base_url(session)  # type: ignore[arg-type]

    assert client.base_url == "https://pinned.example"
    assert session.urls == []
