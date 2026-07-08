# Host Access Handoff Report

Generated: 2026-07-08

## Summary

The app had two separate problems during the July 7 startup:

1. A local startup bug caused curl_cffi to fail before network I/O with curl
   error 43:
   `Failed to setopt 10002 b'https://...`, `curl: (43)`.
2. After isolating and fixing that local bug, AnimePahe is still blocking this
   machine/session at the HTTP layer. The probes reach the hosts, but the API
   endpoints do not return AnimePahe JSON.

The refreshed `cookies.txt` does not currently contain Kwik cookies. It contains
AnimePahe cookies only, so the retained Kwik fallback will load zero cookies.

## Local Bug Found and Fixed

Root cause:

- `run_web.bat` set `CURL_IMPERSONATE=chrome`.
- curl_cffi/libcurl also observes that environment variable internally.
- On this Windows setup, merely having `CURL_IMPERSONATE` in the environment
  made every curl_cffi request fail before network I/O while setting
  `CURLOPT_URL`.
- This reproduced even against `https://tls.browserleaks.com/json`, so it was
  not AnimePahe-specific.

Fix applied:

- `run_web.bat` now sets `ANIMEPAHE_CURL_IMPERSONATE=chrome`.
- `web/core/http_client.py` now reads `ANIMEPAHE_CURL_IMPERSONATE`.
- `web/core/http_client.py` defensively removes legacy `CURL_IMPERSONATE` from
  the Python process before curl_cffi sessions are created.

Important restart note:

- Any server already started with the old `CURL_IMPERSONATE` environment must be
  stopped and restarted. Its stored startup check will continue to show the old
  curl error until restart.

## Live Probe Results

Command:

```bat
uv run python scripts\diagnose_host_access.py
```

Runtime/session files:

- `user-agent.txt`: present, length 111, no NUL or line break.
- `cookies.txt`: present, 12 cookie rows.
- Cookie domains: `animepahe.pw` only.
- Kwik cookie rows: 0.
- `cf_clearance`: present in the cookie file.
- `kwik_session`: not present.

Transport sanity:

- `https://tls.browserleaks.com/json`: HTTP 200 JSON through curl_cffi Chrome
  impersonation after the env-var fix.

AnimePahe candidates:

- `https://animepahe.com/api?m=search&l=1&q=naruto`
  redirects/finalizes to `https://animepahe.pw/...`, returns HTTP 403
  Cloudflare HTML.
- `https://animepahe.org/api?m=search&l=1&q=naruto`
  redirects/finalizes to `https://animepahe.pw/...`, returns HTTP 403
  Cloudflare HTML.
- `https://animepahe.pw/api?m=search&l=1&q=naruto`
  returns HTTP 403 Cloudflare HTML.
- `https://animepahe.ru/api?m=search&l=1&q=naruto`
  returns HTTP 200, but the body is HTML, not AnimePahe JSON.
- `https://animepahe.si`
  does not resolve from this environment.

Conclusion:

- curl_cffi itself is functioning after the env-var fix.
- Current automatic AnimePahe search/release/play-page access is still blocked
  because no candidate returns a valid JSON API response.

## Current Open Issues

### 1. AnimePahe cookies are not used by the AnimePahe client

The refreshed `cookies.txt` appears to be for `animepahe.pw`, not `kwik.cx`.
Current code only loads `KWIK_COOKIE_FILE` inside `web/core/kwik.py`, and that
loader intentionally filters for `kwik.*` domains.

Impact:

- These refreshed AnimePahe cookies do not help current AnimePahe search/API
  requests.
- They also do not help Kwik, because there are zero Kwik cookie rows.

Likely fix:

- Add an AnimePahe cookie-file loader to `web/core/animepahe.py` that can load
  explicit Netscape-format cookies for `animepahe.*` domains.
- Keep Kwik cookie loading separate, or rename the env var to make scope clear:
  for example `ANIMEPAHE_COOKIE_FILE` and `KWIK_COOKIE_FILE`.
- Include diagnostics that report AnimePahe cookie row counts and Kwik cookie
  row counts separately.

### 2. Kwik fallback currently has no usable cookies

The current `cookies.txt` has:

- Kwik cookie rows: 0.
- `kwik_session`: no.

Impact:

- If the flow reaches Kwik, `_load_cookie_file()` will report no Kwik cookies
  and the fallback cannot help.

Likely fix:

- Export `kwik.cx` cookies separately after opening an actual Kwik page in the
  browser, or update docs/UI to distinguish AnimePahe cookie export from Kwik
  cookie export.

### 3. Domain detection correctly refuses HTML, but no domain currently passes

The stricter domain detection is behaving correctly: `.ru` returns 200 but HTML,
so it should not be selected as a working API base.

Impact:

- The app falls back to `https://animepahe.com`, which currently redirects to
  `.pw` and returns Cloudflare 403.

Likely fix paths:

- Add AnimePahe cookie replay support.
- Test whether a specific `curl_cffi` impersonation target such as `chrome124`,
  `chrome131`, or a target matching the exported browser UA improves access.
- If cookie replay plus impersonation still fails, the remaining practical path
  is browser-assisted import for AnimePahe release/play data.

### 4. Running server health may show stale startup diagnostics

The running server stores `startup_checks` at process start. After code/env
fixes, `/health` will still include the old startup failure until the server is
restarted.

Likely fix:

- Restart after this patch.
- Optionally add a "current environment check" field to `/health`, or make the
  UI clearly distinguish startup checks from refreshed `/api/diagnostics`
  checks.

## Commands Run

Local checks:

```bat
uv run pytest
npm --prefix frontend run build
uv run python scripts\localhost_checks.py --mode start
```

Host diagnostics:

```bat
uv run python scripts\diagnose_host_access.py
```

Specific curl_cffi isolation tests:

- Minimal PowerShell curl_cffi request: passed.
- Minimal cmd.exe curl_cffi request: passed.
- cmd.exe with `CURL_IMPERSONATE=chrome`: failed before fix with curl error 43.
- cmd.exe with `ANIMEPAHE_CURL_IMPERSONATE=chrome` and legacy env cleanup:
  passed the neutral TLS probe.

## Recommended Next Fix

Implement explicit AnimePahe cookie replay first. The refreshed cookie file is
AnimePahe-scoped and contains `cf_clearance`, so it is the most relevant
available session artifact. The current code never applies it to AnimePahe
requests.

After that, rerun:

```bat
uv run python scripts\diagnose_host_access.py
```

Success criteria:

- At least one AnimePahe API candidate returns HTTP 200 with JSON-shaped body.
- `/api/search?q=naruto` returns non-empty results.
- If progressing to final links, `cookies.txt` or a separate Kwik cookie file
  must include `kwik.cx` rows.
