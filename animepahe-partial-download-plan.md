# Fix Plan: "Only the first ~5 episodes download"

Prepared: 2026-07-08 · Scope: diagnosis + plan only (no code modified)

The Cloudflare browser‑mint (`ANIMEPAHE_CLEARANCE_MODE=browser`, SeleniumBase) works — search, anime details, and episode listing all return 200. The remaining problem is that a "download all" only ever lands ~5 episodes, silently. This document explains exactly why and how to fix it.

---

## Part A — What the evidence shows

From the terminal capture of the failing run:

- `Cloudflare clearance mode: browser`; SeleniumBase downloads `uc_driver` and mints clearance; `GET /api/search`, `/api/anime/...`, `/api/anime/.../episodes?all_pages=true` all return **200**. Minting works.
- `Loaded 5 AnimePahe cookies` = cookie **rows** in `cookies.txt`, unrelated to the 5 episodes (red herring).
- `POST /api/download` → 200, then exactly **one** `core.kwik: No Kwik cookies found ...` warning at the first Kwik hit (21:51:09).
- After that: only a long stream of `GET /api/queue` polls. **No `Error processing download links` log. No `link_error`. No SeleniumBase re‑launch output.**

That combination is the key: the resolve loop neither crashed nor re‑minted — episodes past ~5 are being **silently discarded**.

---

## Part B — Root cause (primary)

**The `/download` route resolves every episode's link in a tight, upfront, sequential burst before any download starts, and quietly drops the episodes that fail.**

`web/api/routes.py` → `start_download()` → `process_and_queue()` (lines 303–360):

```python
for episode in episodes_to_download:          # tight loop, no pacing
    try:
        options = await animepahe_client.get_episode_download_options(...)   # animepahe /play
        selected = _select_download_option(...)
        direct_link = await animepahe_client.get_direct_download_link(...)   # pahe.win + kwik.cx
        resolved_links.append(...)
    except Exception as e:
        if _is_kwik_session_rejected_error(e):     # only ONE specific message matches
            raise RuntimeError(...)                # (would abort, but this branch isn't hit here)
        link_errors.append(str(e))                 # <-- everything else: SKIP episode, keep going
    processed += 1
# ...
if added_count == 0 and link_errors:              # <-- error is surfaced ONLY if ZERO resolved
    ... broadcast_link_error(...)
```

Each episode fires ~4 automated requests (`/play` on animepahe.pw, then pahe.win embed, kwik page, and the `_token` POST on kwik.cx). Because the loop has **no throttling**, this is a rapid burst against two Cloudflare‑fronted hosts. After roughly five episodes, **Kwik/pahe.win starts returning 403/429** (rate‑limit). Critically, that rate‑limit 403 is **not** a Cloudflare *challenge* page, so:

- `kwik.py::_fetch_with_retry` does **not** re‑mint (its mint path only triggers when `looks_like_cf_challenge()` is true — `clearance.py:89`, needs `cf-mitigated` header or "just a moment"/"turnstile" body). A bare rate‑limit 403 fails that test.
- It falls through to `kwik.py:372` and raises `KwikDecodeError("Kwik returned HTTP 403 before the page could be decoded…")`.
- That message is **not** matched by `routes.py::_is_kwik_session_rejected_error` (which only matches "Kwik still returned HTTP 403" / "Cloudflare rejected the exported browser session"), so it is appended to `link_errors` and the loop **continues** — no crash, no re‑mint (matches the terminal: no errors, no SeleniumBase relaunch).

Result: the first ~5 episodes resolve and get enqueued; episodes 6+ hit the rate‑limit, fail, and are **silently skipped**. Since `added_count > 0`, the `broadcast_link_error` branch (routes.py:352) never fires, so the UI shows 5 tasks and **no error**. This is precisely "only the first 5 download."

The same upfront‑burst pattern exists in `/download/batch` (routes.py:483–503) and `AnimePaheClient.get_episode_links_batch` (animepahe.py:915–917).

---

## Part C — Contributing causes

1. **Kwik/pahe.win clearance coverage gaps** (`clearance.py:60–67`, `205–218`): `compatible_hosts()` / `get_compatible()` only group `animepahe.*` and `kwik.*`. **`pahe.win` is not covered**, so a pahe.win challenge can't reuse any minted clearance, and clearance isn't shared sensibly across the resolve chain. `cookies.txt` also has **no `kwik.*` rows** (`No Kwik cookies found`), so the cookie fallback is empty (fine in browser mode, but it means Kwik relies entirely on mint/impersonation).

2. **Rate‑limit vs challenge not distinguished** (`kwik.py:268–378`): a 403/429 that isn't a CF *challenge* is treated as a fatal per‑episode error instead of a "back off and retry" condition. There is no delay/backoff tuned for rate‑limiting, and the mint path is skipped for these.

3. **Link expiry + non‑retryable 403 + no auto‑re‑resolve** (`downloader.py`): even links that DO resolve are short‑lived Kwik CDN URLs. `_is_retryable()` (216–225) only retries ≥500 — a 403 is **terminal**, and the worker never re‑resolves (927–963). For any batch big enough that later queue positions age out before their turn, those tasks fail with `link_expired`. Today this is masked by the primary bug (only 5 ever enqueue), but it will bite once resolution is fixed. `add_task` (689–733) also requires a fully‑resolved `url` up front, which forces the eager‑resolution design.

4. **Silent partial failure** (routes.py:352): the user is told nothing when *some* episodes fail — the single worst UX symptom.

---

## Part D — The fix

### Keystone: resolve each link just‑in‑time inside the download worker (not upfront)

Move link resolution **into `DownloadManager._download_file`**, immediately before streaming each file, instead of resolving the whole season in `process_and_queue()`.

Why this one change fixes the core problem:
- **No burst.** Resolutions are naturally paced to the worker pool (`max_workers`, default 4) instead of a tight N‑episode loop, so Cloudflare/Kwik rate‑limiting is far less likely to trip.
- **Links are always fresh** when used → eliminates the expiry failure mode (Part C‑3) for free.
- **Nothing is silently dropped.** Every selected episode is enqueued as a visible task; a resolution failure becomes a *visible failed task the user can retry*, not a silent skip.

Concrete shape (no code applied):
- Give `DownloadManager` a resolver callback, e.g. `set_link_resolver(async (anime_session, episode_session, resolution) -> (direct_url, filename_meta))`, wired in `main.py`/`routes.py` to `AnimePaheClient.get_episode_download_options` + `_select_download_option` + `get_direct_download_link` (the exact logic already in `/queue/{id}/re-resolve`, routes.py:559–596).
- Allow `add_task(...)` to enqueue an **unresolved** task (blank `url`, status `pending`) carrying `anime_session`, `episode_session`, `resolution`, `anime_title`, `episode` (all already fields on `DownloadTask`).
- In `_download_file`, if `task.url` is empty, call the resolver first (inside the existing try/except so failures classify normally), populate `task.url`, then proceed to stream. Keep the resolver call inside the retry envelope so a transient challenge/rate‑limit re‑resolves.
- `process_and_queue()` in both `/download` and `/download/batch` becomes: enqueue one pending task per selected episode (fast, no network burst), then return. Deduplication/`_known_episodes` still applies.

### Supporting fix 1 — throttle + backoff the resolve/Kwik path

Even with lazy resolution, add pacing so 4 workers don't burst Kwik simultaneously:
- A shared `asyncio.Semaphore` (e.g. 1–2) around the pahe.win→kwik resolution, plus a small **jittered delay** between Kwik hits.
- In `kwik.py::_fetch_with_retry`, treat **429 and non‑challenge 403** as *retryable rate‑limits*: exponential backoff (respect `Retry‑After` if present) for a couple of attempts before giving up, distinct from the CF‑challenge (mint) path and the "session rejected" (fatal) path.

### Supporting fix 2 — auto‑re‑resolve on `link_expired`

In `downloader.py` failure handling (927–963): when the failure is `link_expired`/403 **and** the task has `anime_session` + `episode_session`, re‑resolve a fresh link via the resolver and retry (bounded, e.g. 2 attempts). Make `link_expired` retryable *only when re‑resolution is available*. (Largely redundant once lazy resolution lands, but a good safety net for links that expire mid‑download.)

### Supporting fix 3 — stop hiding partial failures

- With lazy resolution, failed episodes are already visible as failed tasks (retryable via the existing `/queue/retry`).
- Additionally, always broadcast a resolve summary ("X queued, Y failed: <first reason>") even when `added_count > 0` (fix the `added_count == 0` gate at routes.py:352 / 450).

### Supporting fix 4 — clearance host coverage

- Add `pahe.win` to the grouping in `clearance.py::compatible_hosts()` (and the `get_compatible()` fallbacks) so a pahe.win clearance persists and is reused across episodes instead of being re‑minted per hit.
- Optional: pre‑mint clearance for `animepahe.pw`, `pahe.win`, and `kwik.cx` once at the start of a batch so the first several episodes don't each risk a cold challenge.

### Optional — base‑URL detection timing (minor)

Startup `ensure_base_url()` runs before any clearance exists, so it logs `Could not verify an AnimePahe JSON API domain; using https://animepahe.com` and self‑heals via `_learn_base_url_from_response` after the first successful search. Low priority; if desired, mint clearance at startup or retry domain detection after the first mint so the base URL is correct earlier.

---

## Part E — Recommended sequencing

1. **Keystone (lazy just‑in‑time resolution)** — the single change that turns "5 silently" into "all episodes, paced, visible." ~1 day.
2. **Throttle + 429/403‑rate‑limit backoff in Kwik** — prevents tripping Cloudflare in the first place. ~0.5 day.
3. **Surface partial failures** (drop the `added_count == 0` gate) — immediate UX truth. ~0.5–1 hr.
4. **Auto‑re‑resolve on `link_expired`** + **`pahe.win` clearance coverage** — robustness. ~0.5 day.

A fast partial mitigation without the keystone (if a quick patch is wanted first): in `kwik.py`, make non‑challenge 403/429 retry with backoff, and in `routes.py` add a small `await asyncio.sleep()` between episodes and always broadcast the failure summary. This will raise the "5" and at least tell the user what failed — but only the keystone truly fixes it.

---

## Part F — Success criteria
- Queue a full season: **every selected episode appears as a task** (none silently missing).
- Downloads proceed paced; Cloudflare/Kwik 403/429 becomes rare, and when it happens the worker backs off / re‑mints and continues rather than dropping the episode.
- Late‑queue episodes download successfully (fresh, just‑in‑time links — no `link_expired` from expiry).
- Any genuinely unresolvable episode shows as a **failed task with a clear reason** and is retryable; the UI reports "X queued, Y failed."

## Part G — Risks / notes
- Lazy resolution slightly delays the *first byte* of each download (resolve happens at download time) — negligible and worth it.
- Throttling trades a little total throughput for reliability; expose the resolve concurrency/delay as env knobs (e.g. `ANIMEPAHE_RESOLVE_CONCURRENCY`, `ANIMEPAHE_RESOLVE_DELAY_MS`).
- Re‑minting via SeleniumBase is heavy (opens a headed browser); keep it reserved for true CF challenges, and use lightweight backoff for plain rate‑limits so a big batch doesn't launch browsers repeatedly.
- Keep `_known_episodes` dedup semantics when enqueuing unresolved tasks so retries/re‑resolves don't double‑queue.

## Part H — Key code references
- `web/api/routes.py:303–360` upfront sequential resolve + silent drop; `:352` `added_count == 0` gate; `:41–46` `_is_kwik_session_rejected_error`; `:469–519` same pattern in `/download/batch`; `:559–596` existing single‑task re‑resolve to model the resolver on.
- `web/core/kwik.py:268–378` `_fetch_with_retry` (mint only on challenge; non‑challenge 403 → fatal per episode); `:372` the raised message that gets silently dropped.
- `web/core/clearance.py:60–67`, `205–218` host grouping missing `pahe.win`; `:89–104` `looks_like_cf_challenge`.
- `web/core/downloader.py:216–225` `_is_retryable` (403 not retryable); `:689–733` `add_task` requires a resolved url; `:927–963` failure path (no auto‑re‑resolve); `config.py:40` `max_workers=4`.
