from __future__ import annotations

import asyncio

import pytest

from core.clearance import ClearanceProvider


@pytest.mark.asyncio
async def test_clearance_provider_persists_minted_pair(tmp_path) -> None:
    calls: list[tuple[str, str]] = []

    async def fake_minter(url: str, host: str) -> dict:
        calls.append((url, host))
        return {
            "cf_clearance": "clearance-value",
            "user_agent": "Mozilla/5.0 Chrome/141.0.0.0",
            "host": host,
        }

    store = tmp_path / "clearance.json"
    provider = ClearanceProvider(store, minter=fake_minter)

    pair = await provider.mint("https://animepahe.pw/api", "animepahe.pw")

    assert pair["cf_clearance"] == "clearance-value"
    assert calls == [("https://animepahe.pw/api", "animepahe.pw")]

    reloaded = ClearanceProvider(store, minter=fake_minter)
    assert reloaded.get("animepahe.pw")["user_agent"] == "Mozilla/5.0 Chrome/141.0.0.0"


@pytest.mark.asyncio
async def test_clearance_provider_serializes_concurrent_mints(tmp_path) -> None:
    calls = 0

    async def fake_minter(url: str, host: str) -> dict:
        nonlocal calls
        calls += 1
        await asyncio.sleep(0.01)
        return {
            "cf_clearance": "shared-clearance",
            "user_agent": "Mozilla/5.0 Chrome/141.0.0.0",
            "host": host,
        }

    provider = ClearanceProvider(tmp_path / "clearance.json", minter=fake_minter)

    first, second = await asyncio.gather(
        provider.mint("https://animepahe.pw/api", "animepahe.pw"),
        provider.mint("https://animepahe.pw/api", "animepahe.pw"),
    )

    assert first["cf_clearance"] == second["cf_clearance"] == "shared-clearance"
    assert calls == 1


@pytest.mark.asyncio
async def test_clearance_provider_reuses_pahe_win_family(tmp_path) -> None:
    async def fake_minter(url: str, host: str) -> dict:
        return {
            "cf_clearance": "pahe-clearance",
            "user_agent": "Mozilla/5.0 Chrome/141.0.0.0",
            "host": host,
        }

    provider = ClearanceProvider(tmp_path / "clearance.json", minter=fake_minter)

    await provider.mint("https://pahe.win/e/example", "pahe.win")

    assert provider.get_compatible("www.pahe.win")["cf_clearance"] == "pahe-clearance"
