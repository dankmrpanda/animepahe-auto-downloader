# Fix Plan: AnimePahe Cloudflare Managed-Challenge Blocker

Prepared: 2026-07-08 · Updated: 2026-07-08 (decision locked)

> **DECISION (locked):** Build the **hybrid architecture** — an automated, in‑app **headed browser mints `cf_clearance`**, and `curl_cffi` replays it for all fast API/scrape/download work, auto‑refreshing when Cloudflare re‑challenges. This is the durable path (formerly "Tier 2"). The cookie‑application + re‑challenge‑detection work (formerly "Tier 1") is **not a separate track** — it is **Milestone 1**, the shared foundation the browser minter plugs into. A pure‑`curl_cffi` (no browser) solution is **not viable** against AnimePahe's 2026 Cloudflare managed challenge and is explicitly rejected.

---

## Part A — Verification: was the previous curl_cffi plan implemented correctly?

**Yes — faithfully, across every file.** Verified by reading the committed code (HEAD `2fafdbe report`):

| Plan item | File | Status |
|---|---|---|
| Impersonating transport factory | `web/core/http_client.py` | ✅ `make_async_session(impersonate=...)`, version‑tolerant exception imports, `NETWORK_EXCEPTIONS`. |
| AnimePahe client → curl_cffi | `web/core/animepahe.py` | ✅ `AsyncSession`, instance `base_url`, `allow_redirects`, UA opt‑in, domain auto‑detect. |
| Domain auto‑detection | `web/core/animepahe.py` | ✅ `ensure_base_url()` requires a JSON dict (correctly rejects `.ru` 200‑HTML). |
| Kwik resolver → curl_cffi | `web/core/kwik.py` | ✅ `AsyncSession`, UA opt‑in, `referer` param, cookie fallback, `kwik_session` domain‑scoped. |
| Downloader → curl_cffi streaming | `web/core/downloader.py` | ✅ `DownloadHTTPError`, `session.stream()`+`aiter_content`, per‑chunk `asyncio.wait_for` watchdog, exception rewire. |
| Diagnostics / startup / launcher / tests | `diagnostics.py`, `main.py`, `run_web.bat`, `tests/` | ✅ all present. |

Also correctly handled by the implementer: the **`CURL_IMPERSONATE` env collision** (libcurl reads it too → `curl: (43)` on Windows) was renamed to `ANIMEPAHE_CURL_IMPERSONATE` + `os.environ.pop("CURL_IMPERSONATE")`. curl_cffi TLS impersonation confirmed working (browserleaks → 200).

**The swap is correct. It is a necessary foundation, not the reason the app is still blocked.**

---

## Part B — The real remaining blocker (diagnosis)

Around **June 2026 AnimePahe moved from DDoS‑Guard to a Cloudflare "Under Attack" / managed challenge (Turnstile).** Independently reproduced this session:

```
animepahe.com/.org  → 301 → animepahe.pw
animepahe.pw/api?…  → HTTP 403, body "<title>Just a moment...</title>",
                       header cf-mitigated: challenge, server: cloudflare
```

- A managed challenge requires **executing Cloudflare's JavaScript** to earn `cf_clearance`. `curl_cffi` gives a perfect TLS/JA3+HTTP2 fingerprint but **runs no JS**, so it can only *replay* a `cf_clearance` a real browser minted — it cannot *solve* the challenge. The original "curl_cffi alone suffices" premise was true under DDoS‑Guard and is now obsolete.
- **Concrete bug:** the user's `cookies.txt` has a valid `cf_clearance` for `animepahe.pw`, but the AnimePahe client **never applies it** (cookie loading lives only in `kwik.py`, filtered to `kwik.*`). Milestone 1 fixes this.
- **Research consensus (5 agents + verifier, live‑checked):** every working 2026 AnimePahe tool uses a real/automated browser (to solve, or to inherit the session); the pure‑HTTP `justfoolingaround/animdl` is confirmed broken. `cf_clearance` is bound to **IP + exact User‑Agent + browser‑class TLS**, is short‑lived (~15–60 min), and can be revoked mid‑session by Cloudflare "Precursor" JS. **Kwik (`kwik.cx`) is a separate Cloudflare zone** (currently lighter — returns 200 — but plan for it).

---

## Part C — Chosen architecture (the hybrid)

```
┌─────────────────────────────────────────────────────────────────────┐
│ FastAPI app (curl_cffi does all fast HTTP: /api, /play, pahe.win,     │
│              kwik decode + _token POST, .mp4 download)                │
│                                                                       │
│   AnimePaheClient ─┐                                                  │
│                    ├─► needs a valid cf_clearance + matching UA       │
│   KwikPahe ────────┘        per host (animepahe.pw, kwik.cx)          │
│                    │                                                  │
│                    ▼                                                  │
│         ClearanceProvider  (NEW, web/core/clearance.py)              │
│           • cache {host: {cf_clearance, user_agent, minted_at}}      │
│           • mint(host): headed nodriver solves challenge, exports    │
│             cf_clearance + exact UA                                  │
│           • inject into curl_cffi session; refresh on 403/challenge  │
│           • persist last‑good pair across restarts                   │
└─────────────────────────────────────────────────────────────────────┘
```

Why this design (vs the alternatives):
- **Pure curl_cffi (no browser): rejected** — cannot pass a managed challenge (Part B).
- **Cookie‑replay forever (manual export): rejected as the *end state*** — works but expires every ~30–60 min and needs constant manual re‑export. It is kept only as the *foundation* (Milestone 1) and as a **manual fallback mode** when no browser is available.
- **Hybrid (chosen):** the browser only mints/refreshes the cookie occasionally; curl_cffi does the heavy lifting at full speed. This is exactly what every working 2026 AnimePahe downloader does, and it is unusually reliable *here* because the browser and the app share the same residential IP (the hardest `cf_clearance` binding is satisfied for free).

---

## Part D — Milestone 1: clearance foundation (cookie application + detection)

This is shared by both the `cookie` (manual) and `browser` (automated) modes; build it first because the minter injects into exactly these hooks.

### D1. `web/core/animepahe.py` — AnimePahe cookie application
- `__init__`: `self.cookie_file = os.environ.get("ANIMEPAHE_COOKIE_FILE")`.
- Add `_load_cookie_file(client)` modeled on `KwikPahe._load_cookie_file` but filtering `domain.startswith("animepahe")` (or "not kwik"), setting each via `client.cookies.set(name, value, domain=..., path=...)` in try/except, recording a summary (`count`, `has_cf_clearance`).
- Call it in `_get_client()` **right after `make_async_session(...)` and before `ensure_base_url()`** so the `.pw` cookie applies through the `.com → 301 → .pw` probe redirect.
- Add `set_clearance(cf_clearance, user_agent, host)` (used by the minter): inject the cookie into the session jar and store the UA so `_get_headers()` sends it.

### D2. Exact User‑Agent + impersonate alignment
`_get_headers()` already sends `user-agent` when set. Requirement: the UA must equal the browser that minted the cookie (the minter supplies it in `browser` mode; `user-agent.txt` in `cookie` mode). Keep `ANIMEPAHE_CURL_IMPERSONATE` aligned to that UA's Chrome **major** version (e.g. `chrome141`), falling back to `chrome`.

### D3. Re‑challenge detection helper
Add `_looks_like_cf_challenge(response)` → true if `status == 403` and (`cf-mitigated` header present or body contains `"just a moment"` / `"challenge-platform"`). Use it in `search`, `get_anime_details`, `get_episodes`, `get_episode_download_options`. In `cookie` mode it raises an actionable `AnimePaheError` ("refresh cf_clearance"); in `browser` mode it triggers a re‑mint (Milestone 2, §E4). Mirror this in `kwik.py` for the `kwik.cx` host.

### D4. Diagnostics split
Add to `/api/diagnostics`: `animepahe_cookie_rows`, `animepahe_has_cf_clearance`, `kwik_cookie_rows`, `kwik_has_kwik_session`, plus current `clearance_mode` and per‑host `clearance_fresh` / `last_minted_at`. Resolves the report's AnimePahe‑vs‑Kwik cookie confusion.

**Milestone‑1 exit:** with a fresh browser‑exported `cookies.txt` + matching `user-agent.txt`, `ANIMEPAHE_COOKIE_FILE` set, and base pinned to `.pw`, `GET /api/search?q=naruto` returns real results. (This is the fast unblock; the minter then automates the refresh.)

---

## Part E — Milestone 2: the automated `cf_clearance` minter (the committed solution)

### E1. New module `web/core/clearance.py`
```python
# proposed — not yet applied
from __future__ import annotations
import asyncio, json, os, time
from pathlib import Path
from typing import Optional

class ClearanceError(Exception): ...

class ClearanceProvider:
    """Mints & caches {cf_clearance, user_agent} per host using a headed browser."""
    def __init__(self, store_path: str, mint_timeout: float = 90.0):
        self._store_path = Path(store_path)
        self._mint_timeout = mint_timeout
        self._state: dict[str, dict] = self._load()          # host -> {cf_clearance, user_agent, minted_at}
        self._lock = asyncio.Lock()                          # serialize browser mints (one at a time)

    def get(self, host: str) -> Optional[dict]: ...          # cached pair (caller decides freshness)
    def is_challenge(self, status: int, headers, body: str) -> bool: ...

    async def mint(self, url: str, host: str) -> dict:
        """Launch a headed browser, solve the challenge, export cf_clearance + exact UA."""
        async with self._lock:
            pair = await self._mint_nodriver(url)            # or _mint_seleniumbase per config
            pair["minted_at"] = time.time()
            self._state[host] = pair
            self._save()
            return pair

    async def _mint_nodriver(self, url: str) -> dict:
        import nodriver as uc
        browser = await uc.start(headless=False,             # MUST be headed on Windows (no xvfb)
                                 browser_args=["--window-position=-32000,-32000"])  # off-screen
        try:
            tab = await browser.get(url)
            try:
                await tab.cf_verify()                        # clicks Turnstile if opencv-python present
            except Exception:
                pass
            # poll until cf_clearance appears or timeout
            deadline = time.time() + self._mint_timeout
            cf = None; ua = await tab.evaluate("navigator.userAgent")
            while time.time() < deadline:
                jar = await browser.cookies.get_all(requests_cookie_format=True)
                cf = next((c.value for c in jar if c.name == "cf_clearance"), None)
                if cf: break
                await tab.sleep(1.5)
            if not cf:
                raise ClearanceError("Timed out solving Cloudflare challenge")
            return {"cf_clearance": cf, "user_agent": ua}
        finally:
            browser.stop()

    def _load(self) -> dict: ...   # read JSON store (ignore if missing/corrupt)
    def _save(self) -> None: ...   # atomic write; file is gitignored
```
Notes: nodriver is async → drops into uvicorn's loop with `await`. `_lock` prevents concurrent browser launches. `cf_verify()` needs `opencv-python`; if absent, the poll‑for‑cookie loop still works for the common auto‑solving managed challenge on a residential IP.

### E2. Wire into `AnimePaheClient`
- `__init__`: read `ANIMEPAHE_CLEARANCE_MODE` (`off|cookie|browser`, default `cookie`); if `browser`, construct a `ClearanceProvider`.
- `_get_client()`: after building the session, if mode is `browser`, load any persisted pair and inject it via `set_clearance(...)`; if none/ stale, `await provider.mint(self.base_url, host)` then inject.
- Add a thin request wrapper used by all four API methods:
```python
async def _get_json(self, url, referer):
    client = await self._get_client()
    resp = await client.get(url, headers=self._get_headers(referer), allow_redirects=True)
    if self._mode == "browser" and self._looks_like_cf_challenge(resp):
        pair = await self._provider.mint(self.base_url, host_of(url))   # re-mint ONCE
        self.set_clearance(pair["cf_clearance"], pair["user_agent"], host_of(url))
        client = await self._get_client()
        resp = await client.get(url, headers=self._get_headers(referer), allow_redirects=True)
    return resp
```
Bound re‑mint to **once per request** to avoid loops.

### E3. Wire into `KwikPahe`
Give `KwikPahe` an optional `clearance_provider` + host `kwik.cx`. In `_fetch_with_retry`, when a `kwik.cx` response is a challenge (currently rare — Kwik returns 200), mint for `kwik.cx` and retry once. The existing packer‑decode + `_token`→302 flow is unchanged and already matches working references.

### E4. Refresh policy
Refresh **on signal, not on a timer**: any AnimePahe/Kwik response that `is_challenge(...)` → discard cached pair, re‑mint once, retry. Persist the last‑good pair so restarts reuse it (skips an unnecessary browser launch).

### E5. Lifecycle & UX (`web/main.py`)
- Startup: if mode `browser`, optionally pre‑mint for `animepahe.pw` so the first user request is fast (or mint lazily on first call — recommended to avoid a browser flash at boot).
- Shutdown: nothing persistent to close (browser is launched per‑mint and stopped in `finally`).
- **Windows reality:** the mint launches a **real, headed Chrome window** (headless is detectable; no `xvfb` on Windows). Move it off‑screen via `--window-position`. Surface a WS/diagnostics status like `"Refreshing Cloudflare clearance…"` so the brief window is expected, not alarming.

### E6. Health/diagnostics
Expose `clearance_mode`, and per host `{ has_clearance, minted_at, age_seconds, last_result }`. On mint failure, set a clear diagnostics error ("Cloudflare mint failed — is Chrome installed? is a VPN on?").

---

## Part F — Tool choice & fallbacks

- **Primary: `nodriver`** — async (native FastAPI fit), CDP‑direct (no chromedriver tell), first‑class cookie export, top independent 2026 pick for Cloudflare. Uses installed Chrome/Chromium.
- **Alternate (sync, easiest docs): `SeleniumBase` CDP Mode** — `sb.activate_cdp_mode(url)`, `sb.solve_captcha()`, `get_all_cookies()`, `get_user_agent()`. Run via `asyncio.to_thread(...)` from the async app. Select with `ANIMEPAHE_BROWSER=seleniumbase`.
- **Sidecar fallback (no in‑process browser): `Byparr`** (maintained FlareSolverr‑API successor) or **`Scrapling` `StealthyFetcher(solve_cloudflare=True)`**. Useful if bundling Chrome in‑process is undesirable; `ClearanceProvider` gets a `_mint_sidecar()` that POSTs to the local solver and reads back `cookies` + `userAgent`.
- **Manual fallback:** `ANIMEPAHE_CLEARANCE_MODE=cookie` uses `ANIMEPAHE_COOKIE_FILE` (Milestone 1) with no browser — for machines where Chrome automation is unavailable.
- **Optional escape hatch (unchanged):** the existing in‑browser **manual‑import** path (`/download/manual-import` + console snippet) — fully client‑side resolution, most CF‑proof, kept as a documented fallback.

Rejected: undetected‑chromedriver (stale, fails Turnstile), plain Playwright+stealth (JS‑layer only), camoufox (weakest on Windows).

---

## Part G — Config / env matrix

| Env | Default | Meaning |
|---|---|---|
| `ANIMEPAHE_CLEARANCE_MODE` | `cookie` | `off` \| `cookie` (manual file) \| `browser` (auto‑mint) — **set `browser` for the chosen solution** |
| `ANIMEPAHE_BROWSER` | `nodriver` | `nodriver` \| `seleniumbase` \| `sidecar` |
| `ANIMEPAHE_BROWSER_HEADLESS` | `false` | Must stay `false` on Windows (documented) |
| `ANIMEPAHE_CLEARANCE_STORE` | `./clearance.json` | Persisted last‑good pairs (gitignored) |
| `ANIMEPAHE_MINT_TIMEOUT` | `90` | Seconds to wait for a challenge to clear |
| `ANIMEPAHE_COOKIE_FILE` | – | Manual `cf_clearance` file (cookie mode / fallback) |
| `ANIMEPAHE_BASE_URL` | – | Pin `https://animepahe.pw` while cookie‑scoped |
| `ANIMEPAHE_CURL_IMPERSONATE` | `chrome` | Align to the minted/exported UA's Chrome major version |

`run_web.bat`: default to `set "ANIMEPAHE_CLEARANCE_MODE=browser"`, keep the cookie‑file lines for fallback, and add `.gitignore` entries for `clearance.json`.

---

## Part H — Dependencies & install
- `uv add nodriver` (pulls a Chrome/Chromium driver path; uses installed Chrome). Optional `uv add opencv-python` for `tab.cf_verify()` Turnstile clicks.
- If `seleniumbase` path chosen: `uv add seleniumbase` (auto‑manages drivers).
- Regenerate `uv.lock`; confirm Windows wheels install. Keep `curl_cffi` (unchanged core).
- Document that **Google Chrome must be installed** on the host for `browser` mode.

---

## Part I — Tests (extend `tests/`)
- `test_clearance_provider.py`: inject a **fake minter** (no real browser) → assert caching, single‑flight `_lock`, persistence round‑trip, freshness/`age_seconds`.
- `test_challenge_detection.py`: `is_challenge()` / `_looks_like_cf_challenge()` for 403+`cf-mitigated`, "just a moment" body, and normal 200.
- `test_animepahe_remint.py`: mock the session to return challenge‑then‑200 → assert **exactly one** re‑mint and a successful retry; assert `cookie` mode raises the actionable error instead.
- Keep existing tests green. Mock at the client/provider boundary — never launch a real browser in CI.

---

## Part J — Sequencing & effort
1. **Milestone 1** (D1–D4): cookie application + exact UA + challenge detection + diagnostics split. Fast unblock with the user's existing artifacts. ~0.5–1 day.
2. **Verify** via `uv run python scripts\diagnose_host_access.py` (success criteria below).
3. **Milestone 2** (E1–E6, F, G, H, I): `ClearanceProvider` + nodriver mint + wiring + refresh‑on‑403 + persistence + tests. ~2–4 days.
4. Keep manual‑import (Part F escape hatch) documented.

---

## Part K — Success criteria
Run `scripts\diagnose_host_access.py` and the app after each milestone:
- An AnimePahe candidate returns **HTTP 200 + JSON dict** (not "Just a moment").
- `GET /api/search?q=naruto` returns non‑empty results.
- Diagnostics show `clearance_mode=browser`, `animepahe_has_cf_clearance=true`, resolved `base_url`, recent `minted_at`.
- End‑to‑end: search → episodes → `/play` (pahe.win) → Kwik `_token`→302 → completed, integrity‑passing `.mp4`.
- **Auto‑refresh proof:** force a stale cookie → app re‑mints once (brief off‑screen Chrome window) → request succeeds, no manual step.

---

## Part L — Risks & caveats
- **Headed window on Windows:** unavoidable for `browser` mode (no `xvfb`); mitigate with off‑screen positioning + a clear status message. Provide `cookie` fallback for headless/CI hosts.
- **Chrome dependency:** `browser` mode needs Chrome installed; detect and error clearly if missing.
- **IP binding:** the mint browser and curl_cffi share one machine/IP (good) — don't add a one‑sided VPN/proxy.
- **UA/impersonate drift:** minter supplies the exact UA; keep `ANIMEPAHE_CURL_IMPERSONATE` aligned to its Chrome major.
- **Precursor/short TTL:** absorbed by refresh‑on‑signal; occasional extra mints are expected.
- **Domain/zone rotation:** `cf_clearance` is per‑host; mint per host (`animepahe.pw`, `kwik.cx`) and re‑pin if AnimePahe moves.
- **nodriver not a guaranteed solve:** on hardest Turnstile it can fail; fallbacks (SeleniumBase, Byparr/Scrapling sidecar, manual import) cover the tail.

---

## Part M — Sources (details in this session's research artifacts)
- Cloudflare *Clearance/Precursor* docs (2026‑07‑06): cookie "securely tied to the specific visitor and device"; may be "reduced or invalidated… even if the cookie has not expired."
- Datahut / Scrapfly / roundproxies / dev.to (2026): curl_cffi beats TLS but "won't clear Turnstile"; fix = "real browser solves once, grab cf_clearance, hand it to curl_cffi"; bound to IP+UA+TLS; ~30–60 min TTL.
- Tool status (verified 2026‑07): nodriver 0.50.3 (2026‑05‑13); SeleniumBase 4.50.5 (2026‑07‑03); FlareSolverr v3.5.0 (2026‑05‑26); Byparr v2.1.0 (2026‑02); undetected‑chromedriver stale (2024‑02).
- Working AnimePahe projects (2026): udb (undetected‑chromedriver + cache), animepahe‑auto (Playwright/CDP), pahebatcher (FlareSolverr), Aniyomi (WebView), hitarth‑gg (extension); animdl pure‑HTTP = broken.
- Live probe (2026‑07‑08): `.com/.org → 301 → .pw`; `.pw` + `/api` → 403 `cf-mitigated: challenge`; `kwik.cx → 200` + `kwik_session`.
