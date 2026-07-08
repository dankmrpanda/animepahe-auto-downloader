"""Cloudflare clearance cache and browser minter helpers."""

from __future__ import annotations

import asyncio
import inspect
import json
import os
import re
import time
from http.cookiejar import LoadError, MozillaCookieJar
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any, Awaitable, Callable, Iterable, Optional
from urllib.parse import urlparse


class ClearanceError(Exception):
    """Raised when Cloudflare clearance cannot be minted or loaded."""


ClearanceMinter = Callable[[str, str], Awaitable[dict[str, Any]]]

DEFAULT_FRESH_SECONDS = 60 * 60
VALID_CLEARANCE_MODES = {"off", "cookie", "browser"}


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def default_store_path() -> Path:
    return Path(os.environ.get("ANIMEPAHE_CLEARANCE_STORE") or (_repo_root() / "clearance.json"))


def normalize_clearance_mode(value: str | None = None) -> str:
    mode = (value or os.environ.get("ANIMEPAHE_CLEARANCE_MODE") or "cookie").strip().lower()
    return mode if mode in VALID_CLEARANCE_MODES else "cookie"


def normalize_host(host_or_url: str) -> str:
    raw = (host_or_url or "").strip()
    if not raw:
        return ""
    parsed = urlparse(raw if "://" in raw else f"https://{raw}")
    return (parsed.hostname or raw).strip(".").lower()


def host_from_url(url: str) -> str:
    return normalize_host(url)


def origin_from_url(url: str) -> str:
    parsed = urlparse(url)
    if not parsed.scheme or not parsed.netloc:
        return ""
    return f"{parsed.scheme}://{parsed.netloc}"


def compatible_hosts(host: str) -> set[str]:
    host = normalize_host(host)
    hosts = {host} if host else set()
    if host.startswith("animepahe."):
        hosts.add("animepahe")
    if host.startswith("kwik."):
        hosts.add("kwik")
    if host == "pahe.win" or host.endswith(".pahe.win"):
        hosts.add("pahe")
    return hosts


def headers_get(headers: Any, name: str) -> str:
    if not headers:
        return ""
    try:
        value = headers.get(name)
        if value is not None:
            return str(value)
    except Exception:
        pass
    lower_name = name.lower()
    try:
        for key, value in headers.items():
            if str(key).lower() == lower_name:
                return str(value)
    except Exception:
        return ""
    return ""


def looks_like_cf_challenge(status_code: int, headers: Any, body: str = "") -> bool:
    if status_code != 403:
        return False
    if headers_get(headers, "cf-mitigated"):
        return True
    lowered = (body or "").lower()
    return any(
        marker in lowered
        for marker in (
            "just a moment",
            "challenge-platform",
            "__cf_chl",
            "cf-chl",
            "turnstile",
        )
    )


def cookie_file_summary(path: str | os.PathLike[str] | None, domain_prefixes: Iterable[str]) -> dict[str, Any]:
    summary = {
        "path": str(path) if path else None,
        "exists": False,
        "rows": 0,
        "has_cf_clearance": False,
        "has_kwik_session": False,
        "domains": {},
        "error": None,
    }
    if not path:
        return summary

    cookie_path = Path(path).expanduser()
    summary["path"] = str(cookie_path)
    summary["exists"] = cookie_path.exists()
    if not cookie_path.exists():
        return summary

    prefixes = tuple(prefix.lower().lstrip(".") for prefix in domain_prefixes)
    try:
        jar = MozillaCookieJar(str(cookie_path))
        jar.load(ignore_discard=True, ignore_expires=True)
    except (FileNotFoundError, LoadError, OSError) as exc:
        summary["error"] = str(exc)
        return summary

    names: set[str] = set()
    domains: dict[str, int] = {}
    rows = 0
    for cookie in jar:
        domain = (cookie.domain or "").lstrip(".").lower()
        if prefixes and not any(domain.startswith(prefix) for prefix in prefixes):
            continue
        rows += 1
        names.add(cookie.name)
        domains[domain] = domains.get(domain, 0) + 1

    summary.update(
        {
            "rows": rows,
            "has_cf_clearance": "cf_clearance" in names,
            "has_kwik_session": "kwik_session" in names,
            "domains": domains,
        }
    )
    return summary


async def _maybe_await(value: Any) -> Any:
    if inspect.isawaitable(value):
        return await value
    return value


def _cookie_attr(cookie: Any, name: str, default: Any = None) -> Any:
    if isinstance(cookie, dict):
        return cookie.get(name, default)
    return getattr(cookie, name, default)


def _extract_cf_cookie(cookies: Iterable[Any]) -> tuple[str, str]:
    for cookie in cookies:
        if _cookie_attr(cookie, "name") != "cf_clearance":
            continue
        value = _cookie_attr(cookie, "value", "")
        domain = str(_cookie_attr(cookie, "domain", "") or "").lstrip(".")
        if value:
            return str(value), domain
    return "", ""


class ClearanceProvider:
    """Mint, persist, and report Cloudflare clearance cookies per host."""

    def __init__(
        self,
        store_path: str | os.PathLike[str] | None = None,
        mint_timeout: float | None = None,
        *,
        minter: Optional[ClearanceMinter] = None,
    ):
        self._store_path = Path(store_path) if store_path else default_store_path()
        self._mint_timeout = float(mint_timeout or os.environ.get("ANIMEPAHE_MINT_TIMEOUT") or 90)
        self._minter = minter
        self._state: dict[str, dict[str, Any]] = self._load()
        self._lock = asyncio.Lock()
        self._last_results: dict[str, dict[str, Any]] = {}

    @property
    def store_path(self) -> Path:
        return self._store_path

    def get(self, host: str) -> Optional[dict[str, Any]]:
        host = normalize_host(host)
        pair = self._state.get(host)
        return dict(pair) if pair and pair.get("cf_clearance") else None

    def get_compatible(self, host: str) -> Optional[dict[str, Any]]:
        exact = self.get(host)
        if exact:
            return exact
        host = normalize_host(host)
        target_hosts = compatible_hosts(host)
        for stored_host, pair in self._state.items():
            if compatible_hosts(stored_host) & target_hosts and pair.get("cf_clearance"):
                return dict(pair)
        return None

    def items(self) -> list[tuple[str, dict[str, Any]]]:
        return [(host, dict(pair)) for host, pair in self._state.items() if pair.get("cf_clearance")]

    def clear(self, host: str) -> None:
        host = normalize_host(host)
        for key in list(self._state):
            if key == host or compatible_hosts(key) & compatible_hosts(host):
                self._state.pop(key, None)
        self._save()

    def is_challenge(self, status_code: int, headers: Any, body: str = "") -> bool:
        return looks_like_cf_challenge(status_code, headers, body)

    async def mint(
        self,
        url: str,
        host: str,
        *,
        force: bool = False,
        stale_before: float | None = None,
    ) -> dict[str, Any]:
        host = normalize_host(host)
        async with self._lock:
            cached = self.get_compatible(host)
            cached_minted_at = float((cached or {}).get("minted_at") or 0)
            if cached and not force:
                return cached
            if cached and stale_before is not None and cached_minted_at > stale_before:
                return cached

            started = time.time()
            try:
                minter = self._minter or self._mint_with_configured_browser
                pair = await minter(url, host)
            except Exception as exc:
                self._last_results[host] = {
                    "ok": False,
                    "message": str(exc),
                    "updated_at": time.time(),
                }
                raise ClearanceError(f"Cloudflare mint failed for {host}: {exc}") from exc

            cf_clearance = str(pair.get("cf_clearance") or "")
            user_agent = str(pair.get("user_agent") or "")
            actual_host = normalize_host(str(pair.get("host") or host))
            if not cf_clearance or not user_agent:
                raise ClearanceError("Browser did not return both cf_clearance and user_agent")

            stored_pair = {
                "cf_clearance": cf_clearance,
                "user_agent": user_agent,
                "minted_at": float(pair.get("minted_at") or time.time()),
                "host": actual_host,
            }
            self._state[actual_host] = stored_pair
            if host and host != actual_host:
                self._state[host] = stored_pair
            self._last_results[actual_host] = {
                "ok": True,
                "message": "minted",
                "updated_at": time.time(),
                "duration_seconds": round(time.time() - started, 2),
            }
            self._save()
            return dict(stored_pair)

    async def _mint_with_configured_browser(self, url: str, host: str) -> dict[str, Any]:
        browser = (os.environ.get("ANIMEPAHE_BROWSER") or "seleniumbase").strip().lower()
        if browser == "seleniumbase":
            return await asyncio.to_thread(self._mint_seleniumbase, url, host)
        if browser == "sidecar":
            raise ClearanceError("ANIMEPAHE_BROWSER=sidecar is not configured in this build")
        return await self._mint_nodriver(url, host)

    async def _mint_nodriver(self, url: str, host: str) -> dict[str, Any]:
        try:
            import nodriver as uc  # type: ignore
        except Exception as exc:  # pragma: no cover - depends on local package
            raise ClearanceError("nodriver is not installed; run `uv add nodriver`") from exc

        headless = (os.environ.get("ANIMEPAHE_BROWSER_HEADLESS") or "false").strip().lower() == "true"
        browser_args = []
        if not headless:
            browser_args.append("--window-position=-32000,-32000")

        browser = await uc.start(headless=headless, browser_args=browser_args)
        try:
            tab = await browser.get(url)
            try:
                verifier = getattr(tab, "cf_verify", None)
                if verifier:
                    await _maybe_await(verifier())
            except Exception:
                pass

            user_agent = await _maybe_await(tab.evaluate("navigator.userAgent"))
            deadline = time.time() + self._mint_timeout
            cf_clearance = ""
            cookie_host = host
            while time.time() < deadline:
                jar = await _maybe_await(browser.cookies.get_all(requests_cookie_format=True))
                try:
                    cookies = list(jar)
                except TypeError:
                    cookies = []
                cf_clearance, cookie_host = _extract_cf_cookie(cookies)
                if cf_clearance:
                    break
                sleeper = getattr(tab, "sleep", None)
                if sleeper:
                    await _maybe_await(sleeper(1.5))
                else:
                    await asyncio.sleep(1.5)

            if not cf_clearance:
                raise ClearanceError("Timed out waiting for cf_clearance")
            return {
                "cf_clearance": cf_clearance,
                "user_agent": str(user_agent),
                "host": cookie_host or host,
            }
        finally:
            stop_result = browser.stop()
            if inspect.isawaitable(stop_result):
                await stop_result

    def _mint_seleniumbase(self, url: str, host: str) -> dict[str, Any]:
        try:
            from seleniumbase import SB  # type: ignore
        except Exception as exc:  # pragma: no cover - depends on local package
            raise ClearanceError("seleniumbase is not installed; run `uv add seleniumbase`") from exc

        headless = (os.environ.get("ANIMEPAHE_BROWSER_HEADLESS") or "false").strip().lower() == "true"
        deadline = time.time() + self._mint_timeout
        with SB(uc=True, headless=headless) as sb:
            sb.activate_cdp_mode(url)
            try:
                sb.solve_captcha()
            except Exception:
                pass
            user_agent = sb.get_user_agent()
            cf_clearance = ""
            cookie_host = host
            while time.time() < deadline:
                for cookie in sb.get_cookies():
                    if cookie.get("name") == "cf_clearance":
                        cf_clearance = cookie.get("value") or ""
                        cookie_host = str(cookie.get("domain") or host).lstrip(".")
                        break
                if cf_clearance:
                    break
                time.sleep(1.5)
        if not cf_clearance:
            raise ClearanceError("Timed out waiting for cf_clearance")
        return {"cf_clearance": cf_clearance, "user_agent": user_agent, "host": cookie_host}

    def status(self, hosts: Iterable[str] = ()) -> dict[str, Any]:
        now = time.time()
        fresh_seconds = float(os.environ.get("ANIMEPAHE_CLEARANCE_FRESH_SECONDS") or DEFAULT_FRESH_SECONDS)
        requested = [normalize_host(host) for host in hosts if normalize_host(host)]
        all_hosts = sorted(set(requested) | set(self._state))
        per_host: dict[str, dict[str, Any]] = {}
        for host in all_hosts:
            pair = self.get_compatible(host)
            minted_at = float((pair or {}).get("minted_at") or 0)
            age = now - minted_at if minted_at else None
            per_host[host] = {
                "has_clearance": bool(pair and pair.get("cf_clearance")),
                "has_user_agent": bool(pair and pair.get("user_agent")),
                "minted_at": minted_at or None,
                "age_seconds": round(age, 1) if age is not None else None,
                "clearance_fresh": bool(age is not None and age <= fresh_seconds),
                "last_result": self._last_results.get(host),
            }
        return {
            "store_path": str(self._store_path),
            "hosts": per_host,
        }

    def _load(self) -> dict[str, dict[str, Any]]:
        try:
            payload = json.loads(self._store_path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            return {}
        if not isinstance(payload, dict):
            return {}
        raw_hosts = payload.get("hosts") if "hosts" in payload else payload
        if not isinstance(raw_hosts, dict):
            return {}
        state: dict[str, dict[str, Any]] = {}
        for host, pair in raw_hosts.items():
            if not isinstance(pair, dict):
                continue
            cf_clearance = str(pair.get("cf_clearance") or "")
            user_agent = str(pair.get("user_agent") or "")
            if not cf_clearance or not user_agent:
                continue
            state[normalize_host(host)] = {
                "cf_clearance": cf_clearance,
                "user_agent": user_agent,
                "minted_at": float(pair.get("minted_at") or 0),
                "host": normalize_host(pair.get("host") or host),
            }
        return state

    def _save(self) -> None:
        self._store_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"hosts": self._state}
        with NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=str(self._store_path.parent),
            delete=False,
            prefix=f".{self._store_path.name}.",
            suffix=".tmp",
        ) as tmp:
            json.dump(payload, tmp, indent=2, sort_keys=True)
            tmp.write("\n")
            temp_name = tmp.name
        Path(temp_name).replace(self._store_path)


def chrome_major_from_user_agent(user_agent: str) -> str | None:
    match = re.search(r"\bChrome/(\d+)", user_agent or "")
    if not match:
        return None
    return match.group(1)
