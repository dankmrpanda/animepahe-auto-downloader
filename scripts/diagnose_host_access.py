#!/usr/bin/env python
"""Diagnose AnimePahe/Kwik host access without printing cookie values."""

from __future__ import annotations

import asyncio
import os
import sys
from collections import Counter
from http.cookiejar import MozillaCookieJar
from pathlib import Path
from urllib.parse import quote


ROOT = Path(__file__).resolve().parents[1]
WEB_DIR = ROOT / "web"
if str(WEB_DIR) not in sys.path:
    sys.path.insert(0, str(WEB_DIR))

from core.animepahe import AnimePaheClient, CANDIDATE_DOMAINS  # noqa: E402
from core.http_client import IMPERSONATE_TARGET, make_async_session  # noqa: E402
from core.kwik import KwikPahe  # noqa: E402


def _load_runtime_files() -> dict[str, object]:
    ua_path = ROOT / "user-agent.txt"
    cookie_path = ROOT / "cookies.txt"
    result: dict[str, object] = {
        "user_agent_exists": ua_path.exists(),
        "cookie_file_exists": cookie_path.exists(),
        "env_legacy_curl_impersonate_repr": repr(os.environ.get("CURL_IMPERSONATE")),
        "env_app_curl_impersonate_repr": repr(os.environ.get("ANIMEPAHE_CURL_IMPERSONATE")),
        "env_animepahe_user_agent_length_before_file": len(os.environ.get("ANIMEPAHE_USER_AGENT") or ""),
        "env_animepahe_cookie_file_repr": repr(os.environ.get("ANIMEPAHE_COOKIE_FILE")),
        "env_kwik_cookie_file_repr": repr(os.environ.get("KWIK_COOKIE_FILE")),
    }

    if ua_path.exists():
        ua = ua_path.read_text(encoding="utf-8-sig").strip()
        os.environ["ANIMEPAHE_USER_AGENT"] = ua
        os.environ["KWIK_USER_AGENT"] = ua
        result.update(
            {
                "user_agent_length": len(ua),
                "user_agent_has_nul": "\x00" in ua,
                "user_agent_has_linebreak": "\r" in ua or "\n" in ua,
            }
        )

    if cookie_path.exists():
        os.environ["ANIMEPAHE_COOKIE_FILE"] = str(cookie_path)
        os.environ["KWIK_COOKIE_FILE"] = str(cookie_path)
        rows = [
            line
            for line in cookie_path.read_text(encoding="utf-8-sig", errors="replace").splitlines()
            if line and not line.startswith("#")
        ]
        domains = Counter()
        names = set()
        for row in rows:
            parts = row.split("\t")
            if len(parts) >= 7:
                domains[parts[0].lstrip(".").lower()] += 1
                names.add(parts[5])
        result.update(
            {
                "cookie_rows": len(rows),
                "cookie_domains": dict(domains.most_common()),
                "animepahe_cookie_rows": sum(
                    count for domain, count in domains.items() if domain.startswith("animepahe.")
                ),
                "kwik_cookie_rows": sum(count for domain, count in domains.items() if domain.startswith("kwik.")),
                "has_cf_clearance": "cf_clearance" in names,
                "has_kwik_session": "kwik_session" in names,
            }
        )

    return result


def _classify_body(text: str) -> str:
    trimmed = (text or "").strip()
    lowered = trimmed.lower()
    if not trimmed:
        return "empty"
    if trimmed.startswith("{") or trimmed.startswith("["):
        return "json-shaped"
    if "just a moment" in lowered or "__cf_chl" in lowered or "cloudflare" in lowered:
        return "cloudflare-html"
    if "<html" in lowered or "<!doctype" in lowered:
        return "html"
    return "other"


async def _probe_url(session, label: str, url: str, headers: dict[str, str] | None = None) -> None:
    try:
        response = await session.get(url, headers=headers, allow_redirects=True, timeout=12.0)
        content_type = response.headers.get("content-type", "")
        server = response.headers.get("server", "")
        cf_ray = response.headers.get("cf-ray", "")
        print(
            f"{label}: status={response.status_code} final={response.url} "
            f"type={content_type!r} server={server!r} cf-ray={bool(cf_ray)} "
            f"body={_classify_body(response.text)}"
        )
    except Exception as exc:
        print(f"{label}: error={type(exc).__name__}: {exc}")


async def main() -> int:
    runtime = _load_runtime_files()
    print("runtime_files:", runtime)
    print("curl_impersonate:", IMPERSONATE_TARGET)

    async with make_async_session(timeout=15.0) as session:
        await _probe_url(session, "tls_browserleaks", "https://tls.browserleaks.com/json")

    app_client = AnimePaheClient()
    async with make_async_session(timeout=15.0) as session:
        app_client._load_cookie_file(session)
        print("animepahe_cookie_load_summary:", app_client._cookie_load_summaries.get(id(session), {}))
        for candidate in CANDIDATE_DOMAINS:
            raw_url = f"{candidate}/api?m=search&l=1&q={quote('naruto')}"
            headers = app_client._get_headers(candidate + "/")
            await _probe_url(session, f"animepahe_api_raw {candidate}", raw_url, headers)
            await _probe_url(
                session,
                f"animepahe_home {candidate}",
                candidate + "/",
                {"accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"},
            )

    async with make_async_session(timeout=15.0) as session:
        kwik = KwikPahe()
        kwik._load_cookie_file(session)
        print("kwik_cookie_load_summary:", kwik._cookie_load_summaries.get(id(session), {}))

    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
