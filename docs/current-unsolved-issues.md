# Current Issues and Handoff Notes

Last reviewed: 2026-07-08

This document is a handoff for future sessions. It separates resolved historical
failures from the risks that still need runtime evidence.

## Executive Summary

The old queue bug is resolved, and the main AnimePahe/Kwik access blocker has
now been addressed at the transport layer. AnimePahe, pahe.win, Kwik, and CDN
requests use `curl_cffi` with Chrome impersonation instead of plain
`httpx`/`requests`, which avoids the Python TLS fingerprint that produced many
Cloudflare/DDoS-Guard 403 responses.

Manual Import, `cookies.txt`, and `user-agent.txt` remain as optional fallbacks
for periods where the hosts reject even browser-like impersonation.

See `docs/host-access-handoff-report.md` for the 2026-07-08 live diagnostic
pass. That report records a fixed local env-var bug (`CURL_IMPERSONATE` caused
curl error 43 on Windows), the current AnimePahe Cloudflare 403/HTML responses,
and the fact that the refreshed `cookies.txt` contains AnimePahe cookies but no
Kwik cookie rows.

## Historical Fixes

### 1. Kwik/Cloudflare 403 Blocks Final Link Resolution

Status: addressed by the `curl_cffi` transport swap.

What changed:

- `web/core/kwik.py` now accepts a `curl_cffi.requests.AsyncSession`.
- The default path lets curl_cffi supply Chrome-compatible user-agent and client
  hint headers.
- `KWIK_COOKIE_FILE` still loads Netscape-format `kwik.cx` cookies as a fallback.
- If loaded cookies are still rejected, the app fails fast with a session-level
  `link_expired` message instead of retrying every episode.

Remaining risk:

- Kwik can still enter an "under attack" period and reject the impersonated
  client. Refresh `cookies.txt` and `user-agent.txt` from a browser session on
  the same IP before retrying.

### 2. AnimePahe 403 Blocks Normal Search/Play-Page Resolution

Status: addressed by the `curl_cffi` transport swap and domain auto-detection.

What changed:

- `web/core/animepahe.py` now uses an impersonating async session.
- The default host changed to `https://animepahe.com`.
- Startup auto-detects the first reachable known AnimePahe mirror unless
  `ANIMEPAHE_BASE_URL` is explicitly set.
- The resolved base URL is exposed in health and diagnostics output.

Remaining risk:

- Mirror availability can drift. If auto-detection picks poorly, pin
  `ANIMEPAHE_BASE_URL` temporarily and capture the failing health payload.

### 3. Manual Import

Status: fallback path, not the primary happy path.

Current behavior:

- Manual Import still accepts browser-collected release JSON and generated
  console output with `pahe.win` options.
- It still routes selected options through the backend Kwik decoder so the normal
  queue and downloader machinery remain unchanged.

Remaining risk:

- Manual Import is not a direct-final-URL mode. If Kwik rejects the backend
  session, Manual Import may still fail at final-link resolution.

### 4. Cookie/User-Agent Workflow

Status: optional fallback.

Current behavior:

- `run_web.bat` sets `KWIK_COOKIE_FILE=%~dp0cookies.txt`.
- `run_web.bat` sets `ANIMEPAHE_CURL_IMPERSONATE=chrome`. Do not set the
  legacy `CURL_IMPERSONATE` variable; it caused curl_cffi URL setopt failures
  on Windows.
- `run_web.bat` only sets `KWIK_USER_AGENT` and `ANIMEPAHE_USER_AGENT` when
  `user-agent.txt` exists.
- The default path avoids forced UA overrides so TLS and header identity stay
  aligned with curl_cffi's Chrome impersonation.

Remaining risk:

- Cookie freshness, matching public IP, and browser-session validity are still
  external conditions. Restart the app after replacing fallback files.

### 5. Localhost-Only Exposure Is Not Fully Closed Out

Status: mostly implemented, not formally confirmed.

Evidence:

- `web/main.py` restricts CORS origins to localhost and 127.0.0.1.
- `run_web.bat` and the `__main__` entrypoint bind Uvicorn to `127.0.0.1`.

Likely next work:

- Add a short localhost-only verification checklist.
- Verify Vite dev-server host binding for `npm run dev`.

### 6. Verification/Test Coverage

Status: partially closed.

What changed:

- Unit coverage now targets Kwik decode helpers, downloader failure
  classification, AnimePahe domain resolution, and manual-import route behavior.

Remaining risk:

- The real proof is still live smoke testing against AnimePahe/Kwik:
  search, episode listing, option extraction, direct-link resolution, a completed
  MP4 download, and resume from a partial file.

## Resolved Historical Issue To Avoid Re-Chasing

The old queue bug is documented as fixed in `docs/download-flow-main-parity.md`.
The important distinction for future sessions:

- Old issue: valid links were resolved but dropped before enqueue.
- New transport issue: valid final links could not be obtained because
  AnimePahe/Kwik rejected the client fingerprint.

Future debugging should start at health diagnostics and transport reachability
before changing queue insertion logic again.
