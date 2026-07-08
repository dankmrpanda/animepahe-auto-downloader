from __future__ import annotations

import pytest

from core.animepahe import AnimePaheClient, AnimePaheError
from core.clearance import ClearanceProvider


class FakeCookies:
    def __init__(self) -> None:
        self.set_calls: list[tuple[str, str, str, str]] = []

    def set(self, name: str, value: str, domain: str, path: str = "/") -> None:
        self.set_calls.append((name, value, domain, path))


class FakeResponse:
    def __init__(
        self,
        status_code: int,
        url: str,
        *,
        text: str = "",
        headers: dict | None = None,
        payload: dict | None = None,
    ) -> None:
        self.status_code = status_code
        self.url = url
        self.text = text
        self.headers = headers or {}
        self._payload = payload

    def json(self):
        if self._payload is None:
            raise ValueError("not json")
        return self._payload


class FakeSession:
    def __init__(self, responses: list[FakeResponse]) -> None:
        self.responses = responses
        self.requests: list[tuple[str, dict]] = []
        self.cookies = FakeCookies()

    async def get(self, url: str, **kwargs):
        self.requests.append((url, kwargs))
        if not self.responses:
            raise AssertionError("Unexpected request")
        return self.responses.pop(0)


def make_client(session: FakeSession, provider: ClearanceProvider | None, mode: str) -> AnimePaheClient:
    client = AnimePaheClient()
    client.base_url = "https://animepahe.pw"
    client._base_url_locked = True
    client._base_url_resolved = True
    client._session_ready = True
    client._client = session  # type: ignore[assignment]
    client._client_closed = False
    client.clearance_mode = mode
    client.clearance_provider = provider
    client.kwik.clearance_provider = provider
    return client


@pytest.mark.asyncio
async def test_browser_mode_mints_once_and_retries_challenge(tmp_path) -> None:
    mint_calls: list[tuple[str, str]] = []

    async def fake_minter(url: str, host: str) -> dict:
        mint_calls.append((url, host))
        return {
            "cf_clearance": "new-clearance",
            "user_agent": "Mozilla/5.0 Chrome/141.0.0.0",
            "host": "animepahe.pw",
        }

    provider = ClearanceProvider(tmp_path / "clearance.json", minter=fake_minter)
    session = FakeSession(
        [
            FakeResponse(
                403,
                "https://animepahe.pw/api?m=search&l=8&q=naruto",
                text="<title>Just a moment...</title>",
                headers={"cf-mitigated": "challenge"},
            ),
            FakeResponse(
                200,
                "https://animepahe.pw/api?m=search&l=8&q=naruto",
                text='{"data":[]}',
                payload={
                    "data": [
                        {
                            "session": "anime-session",
                            "title": "Naruto",
                            "type": "TV",
                            "episodes": 220,
                            "status": "Completed",
                            "season": "Spring",
                            "year": 2002,
                            "score": 8.0,
                            "poster": "/poster.jpg",
                        }
                    ]
                },
            ),
        ]
    )
    client = make_client(session, provider, "browser")

    results = await client.search("naruto")

    assert [result.title for result in results] == ["Naruto"]
    assert mint_calls == [("https://animepahe.pw/api?m=search&l=8&q=naruto", "animepahe.pw")]
    assert session.cookies.set_calls == [
        ("cf_clearance", "new-clearance", "animepahe.pw", "/")
    ]
    assert session.requests[1][1]["headers"]["user-agent"] == "Mozilla/5.0 Chrome/141.0.0.0"


@pytest.mark.asyncio
async def test_cookie_mode_challenge_raises_actionable_error() -> None:
    session = FakeSession(
        [
            FakeResponse(
                403,
                "https://animepahe.pw/api?m=search&l=8&q=naruto",
                text="<title>Just a moment...</title>",
                headers={"cf-mitigated": "challenge"},
            )
        ]
    )
    client = make_client(session, None, "cookie")

    with pytest.raises(AnimePaheError, match="Refresh ANIMEPAHE_COOKIE_FILE"):
        await client.search("naruto")
