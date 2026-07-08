# Current Unsolved Issues

Last reviewed: 2026-07-08

This document is a handoff for future sessions. It focuses on issues that remain
unsolved, with references to prior-session artifacts and local runtime evidence.

## Executive Summary

The original web-app queue bug appears resolved: the app no longer uses the
optimized flow that could resolve links but enqueue nothing. The current blocking
problem is host/session access. Prior sessions repeatedly reached either
AnimePahe or pahe.win, then became blocked by HTTP 403 responses from AnimePahe
play pages or Kwik/Cloudflare final-link pages.

In short: the queue path is now mostly deterministic, but link resolution is
still blocked whenever the local HTTP client cannot reuse a valid browser
session.

## Past Session References

- `docs/download-flow-main-parity.md` records the resolved historical bug:
  "links resolve in logs but nothing enters the download queue." The fix was to
  match `main.py`: resolve each episode in order, sort, then enqueue.
- `logs/app.log` records the current blocked state from 2026-07-02. Several
  sessions show `https://animepahe.pw` or `/play/...` returning `403 Forbidden`.
- `logs/app.log` also shows a later session where pahe.win returned `200 OK`,
  `cookies.txt` was loaded, and then every `https://kwik.cx/f/...` request still
  returned `403 Forbidden`.
- `README.md` now documents the expected cookie/user-agent refresh flow for
  Kwik, including the case where cookies are loaded but Cloudflare still rejects
  the session.
- `TODO.localhost.md` shows most localhost production work as complete, with
  localhost-only exposure confirmation still unchecked.

## Unsolved Issues

### 1. Kwik/Cloudflare 403 Blocks Final Link Resolution

Status: blocked by host/session behavior.

Evidence:

- `logs/app.log` at `2026-07-02T09:41:35Z` shows `KWIK_COOKIE_FILE` was missing
  and Kwik requests returned `403 Forbidden`.
- Later sessions show `Loaded 6 Kwik cookies from ...\cookies.txt`, followed by
  repeated `https://kwik.cx/f/...` responses with `HTTP/1.1 403 Forbidden`.
- The strongest log entry is `2026-07-02T09:54:20Z`: loaded cookies included
  `cf_clearance` and `kwik_session`, but Kwik still returned 403. The app
  classified this as `No links resolved (link_expired)`.

Current behavior:

- The backend can read an explicit Netscape-format `cookies.txt`.
- `run_web.bat` sets `KWIK_COOKIE_FILE`, `KWIK_USER_AGENT`, and
  `ANIMEPAHE_USER_AGENT`.
- `web/core/kwik.py` emits a useful error when cookies load but are rejected.

What remains unsolved:

- A valid browser session still may not replay in the app.
- The app cannot automatically prove that `cf_clearance`, `kwik_session`, user
  agent, public IP, and the live browser session all match.
- When Kwik rejects the session, downloads cannot proceed, even through manual
  import.

Likely next work:

- Add a dedicated "Kwik session check" diagnostic that tests one user-provided
  Kwik page and reports cookie count, presence of `cf_clearance`, user-agent
  source, HTTP status, and whether the browser should be refreshed.
- Add UI copy that clearly distinguishes "cookies missing" from "cookies loaded
  but rejected."
- Consider a safer manual mode that accepts already-resolved direct links, if
  that is acceptable for the intended local workflow.

### 2. AnimePahe 403 Blocks Normal Search/Play-Page Resolution

Status: partially worked around, not fully solved.

Evidence:

- `logs/app.log` shows `https://animepahe.pw` returning `403 Forbidden` during
  startup/session warmup.
- Earlier log entries show AnimePahe search and `/play/...` pages returning
  `403 Forbidden`.
- One logged manual-import attempt failed with: the release JSON import worked,
  but the server was still blocked from opening `/play` pages to find pahe.win
  options.

Current behavior:

- The backend defaults to `https://animepahe.pw`.
- Manual import was added so browser-fetched release metadata and play-page
  options can be pasted into the app.
- The frontend includes a browser-console snippet generator for manual import.

What remains unsolved:

- Normal server-side AnimePahe search/play-page scraping can still be blocked by
  403 responses.
- There is no AnimePahe equivalent of `KWIK_COOKIE_FILE` for a first-class
  browser-session replay path.
- Manual import reduces AnimePahe dependence but does not remove the later Kwik
  dependency.

Likely next work:

- Decide whether the project should support an explicit AnimePahe cookie export
  path, similar to Kwik, or keep the current manual-import workaround.
- Add diagnostics that separately report AnimePahe API reachability, AnimePahe
  play-page reachability, pahe.win reachability, and Kwik reachability.

### 3. Manual Import Still Cannot Bypass Kwik Rejection

Status: useful workaround, still blocked at final link step.

Evidence:

- The manual-import route exists in `web/api/routes.py`.
- The import models support browser-fetched `options` in `web/api/models.py`.
- Runtime logs show manual import got far enough to process imported episodes,
  but still ended with `No links resolved (link_expired)` when Kwik returned
  403.

Current behavior:

- Manual import can bypass some AnimePahe API/play-page blocking if the pasted
  JSON includes enough browser-fetched option data.
- The backend still calls `get_direct_download_link()` for the selected pahe.win
  option, which leads back to Kwik.

What remains unsolved:

- Manual import is not a complete offline/browser-assisted path.
- It still needs the backend HTTP client to successfully decode and submit the
  Kwik page.

Likely next work:

- Add a clear manual-import preflight that warns when imported episodes have no
  options.
- If acceptable, add an advanced import format for direct final URLs so users can
  paste browser-resolved links without another backend Kwik request.

### 4. Cookie/User-Agent Workflow Is Fragile

Status: documented, but still operationally fragile.

Evidence:

- `README.md` now explains that `cookies.txt` must be Netscape format and that
  `user-agent.txt` must match the same browser session.
- Prior logs show both failure modes: missing cookie file, then loaded cookies
  still rejected by Kwik/Cloudflare.

Current behavior:

- `run_web.bat` reads `user-agent.txt` if present and falls back to a built-in
  browser user-agent.
- `cookies.txt` and `user-agent.txt` are ignored by git.

What remains unsolved:

- The app has no UI-visible freshness check for cookies.
- The app cannot tell whether the export was created on the same public IP,
  VPN, proxy, or network as the backend.
- Users can replace `cookies.txt` while the app is running, but the backend must
  be fully restarted to reload it.

Likely next work:

- Surface cookie-file path, load count, `cf_clearance` presence, and loaded
  user-agent source in diagnostics.
- Add a restart-required warning when session files are changed.

### 5. Localhost-Only Exposure Is Not Fully Closed Out

Status: mostly implemented, not formally confirmed.

Evidence:

- `TODO.localhost.md` still has `Confirm app remains localhost-only (no
  public/LAN exposure by default)` unchecked.
- `web/main.py` restricts CORS origins to localhost and 127.0.0.1.
- `run_web.bat` and the `__main__` entrypoint bind Uvicorn to `127.0.0.1`.

What remains unsolved:

- There is no explicit verification document or automated check proving all
  supported start paths bind only to loopback.
- `npm run dev` starts both backend and Vite; its actual host exposure should be
  verified, especially Vite's dev server binding.

Likely next work:

- Add a short localhost-only verification checklist.
- Add startup checks that report the actual bound host/port for backend and
  frontend dev mode.

### 6. Verification/Test Coverage Is Thin in the Current Workspace

Status: unresolved verification gap.

Evidence:

- The workspace has a `tests/__pycache__` file, but no visible source test files
  under `tests/`.
- Prior work appears to have focused on runtime behavior and manual logs rather
  than an executable regression suite.

What remains unsolved:

- There are no obvious tracked tests for the current resilience paths:
  AnimePahe 403 classification, Kwik 403 classification, cookie-load summaries,
  manual-import validation, and queue behavior after link-resolution failure.

Likely next work:

- Add small unit tests around failure classification and Kwik cookie-summary
  behavior.
- Add route-level tests for manual import with mocked AnimePahe/Kwik clients.

### 7. Session Changes Are Not Finalized

Status: current workspace/process issue.

Evidence:

- Git status in the current sandbox reported branch `app...origin/app` with
  modified files including `.gitignore`, `README.md`, frontend files,
  `run_web.bat`, `web/api/models.py`, `web/api/routes.py`, and
  `web/core/kwik.py`.
- Git also required a `safe.directory` override in this sandbox because Windows
  ownership differs between the user account and sandbox account.

What remains unsolved:

- It is not clear which local changes are intended to be committed, squashed, or
  revised.
- Runtime artifacts exist locally (`logs/app.log`, `app_state.sqlite3`,
  `cookies.txt`, `user-agent.txt`) and are intentionally ignored, but future
  sessions should avoid treating them as source files.

Likely next work:

- Review the dirty diff before more implementation.
- Commit or otherwise checkpoint the intended code/docs changes once the user is
  satisfied.

## Resolved Historical Issue To Avoid Re-Chasing

The old queue bug is documented as fixed. The important distinction for future
sessions:

- Old issue: valid links were resolved but dropped before enqueue.
- Current issue: valid final direct links are usually not obtained because
  AnimePahe or Kwik returns 403.

Future debugging should start at host reachability/session replay diagnostics
before changing queue insertion logic again.

