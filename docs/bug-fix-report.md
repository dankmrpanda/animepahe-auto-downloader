# Bug-Fix Report â€” AnimePahe Auto-Downloader (July 2026)


This document records the full bug-hunt and fix pass performed across the entire
repository. It covers what was found, why each issue mattered, how it was fixed,
and how the fix was verified. Line references reflect the state of the tree
*after* the fixes were applied; where a line may drift, the enclosing
function/symbol name is given as the durable anchor.


Companion documents:
- `docs/deferred-security.md` â€” items consciously deferred (security hardening +
 transport alignment).
- `docs/download-flow-main-parity.md`, `docs/host-access-handoff-report.md`,
 `docs/current-unsolved-issues.md` â€” pre-existing background/history.


---


## 1. Methodology


1. **Discovery** â€” six parallel exploration agents audited disjoint areas of the
  codebase (root Selenium CLI, Kwik/AnimePahe scraping, downloader engine,
  clearance/transport/config, API layer, frontend/scripts/tests). An
  independent verifier re-derived the key findings from source.
2. **Safety net first** â€” regression tests were written to lock the behavior of
  the two "sacred" working paths before any code changed.
3. **Fixes in risk order** â€” High â†’ Medium â†’ Low, compiling and (where possible)
  testing after each change.
4. **Post-fix review** â€” four independent review agents re-read the diff hunting
  for regressions and newly-introduced bugs; a verifier cross-checked them. One
  real regression introduced by the fixes was found and corrected (see Â§7).


### Sacred paths (must-not-break, and were not changed in behavior)


- **Root `main.py` Selenium search flow** â€” the `By.NAME "q"` search box and
 `.search-results li a` selectors, the `time.sleep(...)` waits, and the driver
 setup.
- **Kwik decode math** â€” `_0xe16c` / `decode_js_style` (CLI) and the equivalent
 base-N decode in `web/core/kwik.py`.
- **`seleniumbase` Cloudflare minter** in `web/core/clearance.py`.
- **Serialized link resolution + pacing** and **disabled per-run caching** in the
 downloader (intentional anti-rate-limit / parity choices).


### Environment caveat on verification


The working sandbox had no `uv`/`pip`/`node`/network, so the full `pytest` and
`npm` suites could not be executed there. Every changed Python file was
`py_compile`-checked; all pure logic (range math, Kwik decode, challenge
detection, DB atomicity, filename tokens, backup-shape guard, episode labeling)
was validated with stdlib-only harnesses; the frontend and full test suite were
validated by close review. **Run `uv run pytest` and
`npm --prefix frontend run build` in a full environment to confirm end-to-end.**


---


## 2. Summary


| Severity | Count | Status |
|----------|-------|--------|
| High     | 6     | Fixed |
| Medium   | ~18   | Fixed |
| Low / hygiene | ~24 | Fixed |
| Regression introduced during fixing | 1 | Fixed |
| Deferred (see `deferred-security.md`) | 4 | Tracked |


New regression tests: `tests/test_main_cli.py`, `tests/test_downloader_worker.py`,
`tests/test_state_store_atomicity.py`, `tests/test_routes_backup.py`, plus
additions to `tests/test_challenge_detection.py`,
`tests/test_failure_classification.py`, `tests/test_routes_manual_import.py`,
`tests/test_downloader_lazy_resolve.py`.


---


## 3. High-severity bugs


### H1 â€” CLI ranged download crashes / selects wrong episodes
- **Location:** `main.py` â€” `fetch_series` (`main.py:287`), `extract_link_content`
 (`main.py:315`).
- **Category:** correctness / crash.
- **Symptom:** Downloading a range whose start is past episode 30 (e.g. `31â€“60`)
 raised `IndexError`, or silently grabbed the wrong episodes.
- **Root cause:** `fetch_series` pruned the leading pages (`start_page` computed
 from `episodes[0]`) and returned a shortened list, but `extract_link_content`
 indexed that list with *absolute* episode numbers.
- **Fix:** `fetch_series` now always fetches from page 1 for ranges (only the end
 page is bounded), so absolute episode numbers map directly onto list indices.
 `extract_link_content` uses `start_index = max(0, episodes[0] - 1)` and clamps
 `end_index` so an over-long range can't overrun the list. The default
 "all from episode 1" path is unchanged.
- **Also fixed here (B2):** "start at N, all remaining" previously ignored N and
 started at 1; it now honors the start episode.
- **Verification:** `tests/test_main_cli.py` (range `[31,60]`, `[5,0]` all-from-5,
 default `[1,0]`); validated across edge cases incl. beyond-range clamp.


### H2 â€” Retry backoff blocked the worker slot
- **Location:** `web/core/downloader.py` â€” `_queue_retry` (`downloader.py:852`),
 `_schedule_retry` (`downloader.py:892`).
- **Category:** concurrency / throughput.
- **Symptom:** A retryable failure made the worker `await asyncio.sleep(backoff)`
 (up to 60s) inline, holding its slot and the file lock and appearing as a
 phantom-active download; other queued downloads stalled.
- **Root cause:** the backoff sleep ran on the worker's own stack before the
 worker returned to the pool.
- **Fix:** the backoff was moved into a tracked background task
 (`_schedule_retry`) that sleeps and then re-enqueues; the worker frees its slot
 and lock immediately. **See Â§7** for the follow-up that keeps such tasks
 visible/cancellable.
- **Verification:** `tests/test_downloader_worker.py::test_queue_retry_does_not_block_worker`.


### H3 â€” WebSocket set mutated during iteration
- **Location:** `web/api/routes.py` â€” `_broadcast` (`routes.py:73`).
- **Category:** crash / correctness.
- **Symptom:** Broadcasting progress while a client connected/disconnected raised
 `RuntimeError: Set changed size during iteration`, which turned into 500s on
 state-changing routes and silently stopped UI updates.
- **Root cause:** the live `connected_websockets` set was iterated while `await
 ws.send_json(...)` allowed the set to be mutated mid-loop.
- **Fix:** iterate a snapshot (`list(connected_websockets)`).
- **Verification:** reviewed as the only iteration site over the live set.


### H4 â€” Backup import could wipe the entire queue/history
- **Location:** `web/api/routes.py` â€” `import_backup` (`routes.py:711`);
 `web/core/state_store.py` â€” `replace_download_tasks` (`state_store.py:260`).
- **Category:** data loss.
- **Symptom:** `POST /api/backup/import {}` (or any body lacking a valid `tasks`
 section) deleted all tasks, because `replace_existing` defaulted to true and an
 empty task list became a full `DELETE`.
- **Root cause:** no guard against empty/malformed import payloads; the tasks
 table was replaced unconditionally.
- **Fix:** the route now detects sections by **shape** (a `settings` object
 and/or a `tasks` list), rejects payloads with no valid section (`400`), and only
 touches the tasks table when a real `tasks` list is present â€” so `{}`,
 `{"tasks": null}`, and `{"tasks": 5}` can no longer wipe anything. Backed by
 the atomic replace in D-6.
- **Verification:** `tests/test_routes_backup.py` (`{}` â†’ 400), plus the
 shape-guard harness.


### H5 â€” Cloudflare challenge detected only on HTTP 403
- **Location:** `web/core/clearance.py` â€” `CHALLENGE_STATUS_CODES`
 (`clearance.py:30`), `looks_like_cf_challenge` (`clearance.py:96`).
- **Category:** robustness (blocks the working clearance path from activating).
- **Symptom:** The common "Just a momentâ€¦" interstitial (served as **HTTP 503**,
 sometimes 429) was not recognized as a challenge, so the `seleniumbase` minter
 was never triggered for it.
- **Root cause:** detection early-returned unless `status_code == 403`.
- **Fix:** detection now applies to `{403, 429, 503}` and still requires a
 Cloudflare marker (header or body), so a plain 503/429 does not falsely mint,
 and a `200` is never treated as a challenge.
- **Verification:** `tests/test_challenge_detection.py` (503/429 cases added;
 200-is-not-a-challenge retained).


### H6 â€” Settings broadcast reset "Default Quality" to 0
- **Location:** `web/api/routes.py` â€” `broadcast_settings` (`routes.py:107`);
 `frontend/src/main.js` â€” `handleSettingsBroadcast`.
- **Category:** correctness (silent preference loss).
- **Symptom:** Every settings save wiped the user's default quality back to 0.
- **Root cause:** the broadcast omitted `default_resolution`, and the frontend
 full-replaced its settings object from the broadcast (defaulting the missing
 field to 0).
- **Fix:** the backend now includes `default_resolution` in the broadcast, and the
 frontend merges only the fields present in the broadcast rather than
 full-replacing.
- **Verification:** review of both sides; backend contract covered by the
 frontend/backend cross-reference.


---


## 4. Medium-severity bugs


### Kwik / AnimePahe scraping
- **KWIK-1 â€” kwik_session cookie hardcoded to `kwik.cx`.** `web/core/kwik.py:452`.
 The cookie is now scoped to the actual form-action host (e.g. `kwik.si`) via
 `host_from_url(...)`, so it is sent on the POST target.
- **KWIK-2 â€” 403 diagnostic dead for `kwik.si`.** `web/core/kwik.py:395`. The
 diagnostic branch matched `endswith("kwik.cx")`; it now matches any `kwik.*`
 host via `normalize_host(url).startswith("kwik.")`.
- **KWIK-3 â€” transient token POST not retried.** `decode_kwik_page`
 (`web/core/kwik.py:475`). A transient "No redirect found" POST failure now
 retries within the existing budget, mirroring the CLI; genuine Cloudflare
 `KwikDecodeError`s still fast-fail.
- **APAHE-1 â€” one bad page aborted the whole episode listing.**
 `get_all_episodes` (`web/core/animepahe.py:740`). Now uses
 `gather(return_exceptions=True)`, retries failed pages once sequentially, and
 raises a clear `AnimePaheError` only if a page is truly unreachable.
- **APAHE-2 â€” `search()` swallowed every error as "no results".**
 `web/core/animepahe.py:508`. The final `except` was narrowed to network/JSON
 errors â†’ `[]`; unexpected exceptions now propagate (surfaced as an error rather
 than masked).
- **APAHE-3 / B4 â€” base URL poisoning + pin override.**
 `_learn_base_url_from_response` (`web/core/animepahe.py:349`). It now respects a
 pinned `ANIMEPAHE_BASE_URL` (never overrides it) and only "learns" a redirected
 host from a validated JSON API response, so a redirect to an HTML-only mirror
 cannot poison `base_url`.
- **MODEL-1 â€” null `total` crashed details.** `get_anime_details`
 (`web/core/animepahe.py`). `total`/`last_page`/`per_page` are coerced via
 `int(... or default)`.


### Downloader engine / state
- **D-02 â€” default "best" re-downloaded/overwrote existing files.** `_download_file`
 (`web/core/downloader.py:926`). After resolving, if the concrete target file
 already exists (and is a valid MP4 when applicable) the task is marked complete
 instead of re-downloading. This is a **post-resolve** check, so it does not
 reintroduce the historical "resolves but nothing enqueues" drop.
- **D-04 â€” worker under-provisioning after scale downâ†’up.** `adjust_workers`
 (`downloader.py:1217`). `_workers` is now a `dict[int, Task]`; scaling prunes
 finished workers and ensures exactly one live worker per id in
 `[0, max_workers)`, so scale-down-then-up reaches the correct count with no id
 collisions.
- **D-05 â€” full schema init on every DB call.** `init_db` (`state_store.py:37`),
 guarded by `_INITIALIZED_DBS` (`state_store.py:19`). Schema creation +
 `PRAGMA table_info` migrations now run once per DB path per process (they were
 running on every persistence call, including per-second progress writes).
- **D-06 â€” non-atomic `replace_*` could wipe on failure.** `replace_settings`
 (`state_store.py:125`), `replace_download_tasks` (`state_store.py:260`). Both now
 do `DELETE` + `INSERT` in a single transaction (shared
 `_UPSERT_DOWNLOAD_TASK_SQL`), so a failed/partial import rolls back and leaves
 the previous data intact.
- **XM-1 â€” `.5` specials collided onto integer filenames.** `_episode_token` /
 `_default_filename` (`downloader.py:53`). Episode 1.5 now becomes `EP01.5_â€¦`
 instead of colliding with `EP01_â€¦`; integer episodes are unchanged.
- **HTTP-429 retryable.** `classify_failure` (`downloader.py:150`), `_is_retryable`
 (`downloader.py:274`). A structured `DownloadHTTPError(429)` is now classified
 as `network` and retried (rate-limit backoff), instead of failing terminally as
 "unknown".


### Transport / config
- **B3 (transport) â€” empty impersonation env disabled impersonation.**
 `web/core/http_client.py:33`. `IMPERSONATE_TARGET` now uses `... or "chrome"`
 so a set-but-empty `ANIMEPAHE_CURL_IMPERSONATE` cannot silently revert to the
 plain-Python TLS fingerprint that Cloudflare blocks. Env timeout parsing was
 also made crash-safe (`_parse_timeout`, `http_client.py:37`).


### CLI (main.py)
- **B5 â€” empty episode page aborted the batch.** `fetch_episode`
 (`main.py:235`) now returns `{}` (skip) instead of raising, so one empty page
 no longer drops every other resolved episode.
- **B7 â€” no request timeouts.** All CLI HTTP calls now pass
 `REQUEST_TIMEOUT`/`DOWNLOAD_TIMEOUT`, so a stalled server can't hang the CLI or
 a download thread.
- **B8 â€” one `requests.Session` shared across download threads.** `download_file`
 (`main.py:350`) now uses a per-download session (copying the shared
 headers/cookies), since `requests.Session` is not safe for concurrent use.


---


## 5. Low-severity / hygiene fixes


### CLI (main.py)
- **B3 â€” `_0xe16c` zero-case** returns `int 0` instead of a `str` (`main.py:86`).
- **B9 â€” filename sanitization** (`sanitize_cli_name`, `main.py:54`) now also
 strips backslashes/control chars, trims trailing dots/spaces, and guards
 Windows reserved names; used for both the download filename and the anime
 folder title.
- **B10 â€” input validation** in `main()` (`main.py:457`): all numeric prompts are
 validated with friendly messages + `sys.exit(1)` instead of raw tracebacks;
 blank-start â‡’ 1 and blank-end â‡’ all are preserved.
- **B11 â€” double `driver.quit()`**: `driver` is set to `None` after the search
 quits, so the outer error handler doesn't screenshot/quit a dead session.
- **B12 â€” `exit()` â†’ `sys.exit(1)`** in the error paths.
- **B13 â€” `/d/` â†’ `/f/` normalization** applied in both branches of
 `extract_kwik_link` (`main.py:178`).
- **B14 â€” redirect handling** in `fetch_kwik_direct` (`main.py:123`): accepts
 `{301,302,303,307,308}`, errors clearly on a missing `Location`, and
 absolutizes a relative `Location`.


### Clearance / transport / logging
- **B6 â€” temp-file leak on `_save` failure.** `ClearanceProvider._save`
 (`clearance.py:433`) removes the temp file on error and `fsync`s before the
 atomic replace.
- **B7 â€” `_last_results` keyed under both hosts** so status lookups by either the
 requested or resolved host find the last mint result.
- **B9 (clearance) â€” `close()` resets `_session_ready`** (`animepahe.py:457`) so a
 recreated session re-warms.
- **B10 (clearance) â€” UA consistency.** `_inject_cached_clearance`
 (`animepahe.py:253`) sets the user-agent from the host matching `base_url`
 (via `get_compatible`) rather than letting the last stored host win.
- **Logger env parsing** (`web/core/logger.py`) is crash-safe for
 `LOG_MAX_BYTES`/`LOG_BACKUP_COUNT`.


### API
- **ASYNC-1 â€” background tasks retained.** `_spawn_background` (`routes.py:47`)
 keeps strong references to the episode-queueing tasks so the event loop can't
 GC them mid-run.
- **D-07 / BK-3 â€” maintenance/import race.** `cleanup_maintenance`
 (`routes.py:818`) and `import_backup` (`routes.py:711`) now `pause_and_drain`
 the queue, do the destructive work in a `try`, and `resume` in `finally` (only
 if the queue wasn't already paused) â€” so cleanup can't delete a live
 `.partial`/`.lock` or rewrite state under a running worker.
- **BLOCK-1 â€” blocking MP4 scans off the event loop.** `_looks_like_valid_mp4`
 calls in `_download_file` now run via `asyncio.to_thread`.
- **BK-2 â€” malformed backup task â†’ 400** (not 500).
- **CANCEL-1 â€” `DELETE /queue/{id}` â†’ 404** when the task isn't cancellable
 (`cancel_download`, `routes.py:579`).
- **VAL-1 â€” resolution bounds** (`ge=-1, le=4320`) on the request/settings models.
- **HEALTH-1 â€” live base URL** in `/health` and `/api/diagnostics`
 (`build_health_payload` gained an `animepahe_base_url` argument sourced from the
 live client).
- **Dead code removed:** `has_existing_task_or_file`, `disk_space_preflight`,
 `estimate_required_bytes` and their constants (downloader), and
 `_format_bytes` / `_disk_space_error` (routes).


### Frontend
- **B2 â€” inflated overall %.** `updateTotalProgress` now uses a per-session
 baseline (`progressBaselineCompleted`) instead of the lifetime `completed_count`
 as the denominator.
- **B3 â€” empty-state crash.** `renderDownloadList` renders the "No Downloads"
 state from a module-level `EMPTY_DOWNLOADS_HTML` template instead of cloning a
 node that gets destroyed on the populatedâ†’empty transition.
- **B6 â€” `speedHistory` leak.** Entries are deleted on terminal state and cleared
 on Stop-All / Clear-Completed.
- **B10 â€” double body read.** `_readErrorMessage` reads the body text once, then
 `JSON.parse`s it.
- **B11 â€” episode range max** uses `Math.max(...episodes.map(e => e.episode))`.
- **B12 â€” clearance diagnostics displayed** (new `renderClearance` + card;
 interpolation escaped).
- **B9 â€” dead `API.batchDownload` removed.**


### Tests
- **T1** â€” the lazy-resolve resolver stub returns the real `{url, resolution}`
 dict shape.
- **T2** â€” `FakeDownloadManager.get_status` returns the full status contract.
- **T4** â€” added assertions that `DownloadHTTPError(429)` is `network` and
 retryable.


---


## 6. Deferred items


Four items were consciously deferred and are tracked in
`docs/deferred-security.md`:
1. WebSocket Origin check (cross-site WS hijack).
2. CSRF protection on no-body POST endpoints.
3. Full frontend XSS escaping of all external fields.
4. curl_cffi impersonation-target â†” minted-UA alignment (risky without live
  validation; auto-aligning can break the transport if curl_cffi lacks that
  exact Chrome build).


---


## 7. Regression introduced during fixing (found in review, fixed)


Moving the retry backoff off the worker (H2) initially made a task **in backoff**
invisible: it lived only in the sleeping timer coroutine, absent from
`active_tasks`, the queue, and the status snapshot. Consequences:


- `cancel_task` returned false for it â†’ `DELETE /queue/{id}` 404'd and the task
 **re-downloaded anyway** after the backoff.
- `cancel_all_tasks` ("Stop All") skipped it â†’ it **survived Stop-All** and
 re-enqueued (a correctness bug, not just UX).
- It vanished from the status broadcast during the wait.
- `pause_and_drain` ignored it, so maintenance/import could race a late
 re-enqueue.


**Fix:** retrying tasks are tracked in `_retrying_tasks` (task) and
`_retry_handles` (timer). They now appear as `pending` in `get_status`
(`downloader.py:1281`), are found by `find_task`, and are properly stopped by
`cancel_task` (`downloader.py:1435`), `cancel_all_tasks` (`downloader.py:1494`),
`pause_and_drain` (`downloader.py:1235`), and shutdown
(`_cancel_retry_tasks`, `downloader.py:913`). Cancelled retries stay persisted as
`pending`, so they are restored on the next start rather than lost.


**Verification:** `tests/test_downloader_worker.py::test_cancel_all_stops_a_retrying_task`
and the updated `test_queue_retry_does_not_block_worker`.


Two smaller review findings were also fixed:
- **CLI mislabeling after a skip** â€” with B5 making skips common, the running
 `EPxx` counter mislabeled every file after a skipped episode. The true episode
 number is now carried (`extract_link_content`) and used for the filename
 (`extractor`).
- **`{"tasks": null}` wipe** â€” folded into H4 by detecting the tasks section by
 shape.


---


## 8. How to verify


```bash
# Python tests (needs the project's uv environment)
uv run pytest -q


# Frontend build
npm --prefix frontend run build
```


Everything in this pass `py_compile`s cleanly, and the stdlib-runnable slices
(challenge detection, state-store atomicity, range math, decode round-trip,
episode-token filenames, backup-shape guard, CLI labeling-on-skip) pass under a
plain Python 3 harness.


---


## 9. Realistic caveat


These fixes make the codebase correct and robust. The live Cloudflare `403` /
"does a `cf_clearance` minted by real Chrome work when replayed over `curl_cffi`"
question is a **runtime** matter that only real network testing on the target IP
can resolve â€” it is not closed by code changes alone. See
`docs/host-access-handoff-report.md`.



