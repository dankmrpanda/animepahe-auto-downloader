# AnimePahe Web Downloader

Full-stack downloader for AnimePahe with a FastAPI backend and a Vite/Vanilla JS frontend. Supports queueing, concurrent downloads with progress, per-episode stop, stop-all, retries, and search with poster fallbacks (MAL/Jikan).

## Features
- Search AnimePahe with poster fallback via MyAnimeList (Jikan).
- View details, alt titles, synopsis, and episode list.
- Select individual episodes or ranges; batch download.
- Live progress via WebSocket; per-episode stop and Stop All.
- Retry failed, clear completed, processing placeholder while links are prepared.

## Prerequisites
- Python 3.10+
- UV
- Node.js 18+ and npm

## Setup
```bash
git clone https://github.com/your-username/animepahe-auto-downloader.git
cd animepahe-auto-downloader
npm run setup
```

### Development
Runs backend (FastAPI) and frontend (Vite) together:
```bash
npm run dev
```
Open the URL printed by Vite (usually `http://localhost:5173`).

### Production build
```bash
npm run build
```
This builds the frontend to `frontend/dist`; the Python backend serves it when present.

### Localhost Startup (With Checks)
Run explicit dependency/version/start checks before launching:
```bash
npm run check:start
npm run start:localhost
```

Windows users can also run:
```bat
run_web.bat
```

`run_web.bat` verifies UV is installed, synchronizes the repo-local Python environment, runs startup checks, and starts the API server on `http://127.0.0.1:8000`. It also refreshes the host/session environment variables listed in the Host Access Notes section on every launch.

## Localhost Diagnostics and Maintenance
- `GET /health` - local health status, queue summary, metrics, startup checks.
- `GET /api/diagnostics` - recent failures + environment checks.
- `GET /api/backup/export` - export settings + queue/history backup.
- `POST /api/backup/import` - import settings + queue/history backup payload.
- `POST /api/maintenance/cleanup` - remove stale partial/lock files and orphan queue entries.

## Host Access Notes
The backend uses `curl_cffi` with Chrome impersonation for AnimePahe, pahe.win,
Kwik, and CDN requests. This avoids the plain Python TLS fingerprint that caused
many Cloudflare/DDoS-Guard 403 responses. AnimePahe now may also require a
Cloudflare `cf_clearance` cookie minted by a real browser. The default Windows
startup path uses browser clearance mode: a headed Chrome window briefly opens
off-screen when clearance must be refreshed, then `curl_cffi` replays the cookie
for the fast requests.

AnimePahe defaults to `https://animepahe.com` and auto-detects the first
reachable mirror from the known domain list at startup. Pin a host only when you
need to override detection:

```powershell
$env:ANIMEPAHE_BASE_URL="https://animepahe.pw"
```

`run_web.bat` also sets:

```powershell
$env:ANIMEPAHE_CLEARANCE_MODE="browser"
$env:ANIMEPAHE_BROWSER="seleniumbase"
$env:ANIMEPAHE_CLEARANCE_STORE="<repo>\clearance.json"
$env:ANIMEPAHE_CURL_IMPERSONATE="chrome"
$env:ANIMEPAHE_COOKIE_FILE="<repo>\cookies.txt"
$env:KWIK_COOKIE_FILE="<repo>\cookies.txt"
```

`cookies.txt`, `user-agent.txt`, and Manual Import remain fallback tools for
machines where Chrome automation is unavailable or the host rejects the automated
refresh.

`ANIMEPAHE_BROWSER=seleniumbase` is the default because it imports cleanly in
the local Python environment. The code still supports `ANIMEPAHE_BROWSER=nodriver`
if you install a working nodriver build yourself.

To create or refresh the optional manual fallback files:

1. Open the same browser you normally use for AnimePahe/Kwik on the same internet connection where this app is running. Do not use a VPN/proxy in one place and not the other.
2. In the browser, open an AnimePahe episode and continue through to the Kwik download page until the Kwik page loads successfully.
3. Export cookies for `animepahe.*` and `kwik.cx` in Netscape / cookies.txt format. A browser extension such as `Get cookies.txt LOCALLY` can do this; export only the current AnimePahe and Kwik cookies if the extension lets you filter by domain.
4. Save the exported file as `cookies.txt` in the repository root, next to `run_web.bat`.
5. Copy the exact user-agent from that same browser session and save it as a single line in `user-agent.txt`, also next to `run_web.bat`. In Chrome or Edge, open DevTools Console and run `navigator.userAgent`.
6. Restart the app with `run_web.bat`, then retry the failed queue item or manual import.

For Windows batch startup, the fallback files should be here:

```text
animepahe-auto-downloader/
  cookies.txt
  user-agent.txt
  run_web.bat
```

Then launch:

```bat
run_web.bat
```

For non-batch startup, set the same optional environment variables before
running `npm run start:localhost`.

Export only cookies you are allowed to use, keep the file private, and refresh
it from a browser session on the same IP if the host expires it. If you use the
cookie fallback, a browser network CSV export is not enough; use Netscape cookie
format.

If you still get HTTP 403 after refreshing `cookies.txt`, check these common causes:

- If the log says `Loaded 6 Kwik cookies` and then every `https://kwik.cx/f/...` request is still `403 Forbidden`, the app is reading the file correctly. Kwik/Cloudflare rejected curl_cffi impersonation and the exported browser session.
- The file is not Netscape format. It should contain tab-separated cookie rows, not CSV columns.
- The file does not contain current `animepahe.*` or `kwik.cx` cookie rows.
- The `user-agent.txt` value does not exactly match the browser session that produced `cf_clearance`; Cloudflare can reject otherwise valid cookies when the user-agent changes.
- The browser session used for export is on a different VPN, proxy, network, or public IP than the app.
- The app was already running when you replaced `cookies.txt`; stop and restart it so the backend loads the new file.
- The Kwik page no longer works in the browser either; load it in the browser first, pass any challenge there, then export again.

When Kwik rejects a loaded browser session this way, the app stops resolving the remaining links in that request after the first failed episode. Refresh the session files first; retrying the rest of the batch without new cookies will produce the same 403 for every episode.

## Project structure
- `web/` – FastAPI backend (`main.py`, routes, core logic)
- `frontend/` – Vite/Vanilla JS UI
- `anime_downloads/` – default download output

## Notes
- Uses Jikan for poster/synopsis fallback; requests are rate-limited.
- Stop buttons show on hover in the downloads list.
- A “Processing downloads” placeholder appears while links are being prepared after starting a download.
- Download flow parity note: `docs/download-flow-main-parity.md`.
- Localhost production hardening checklist: `TODO.localhost.md`.

## Disclaimer
For educational purposes only. Please respect the terms of service of the websites you visit. The developers are not responsible for misuse.


