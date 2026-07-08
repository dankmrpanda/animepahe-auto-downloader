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
AnimePahe currently redirects `animepahe.org` to `animepahe.pw`; the web backend defaults to the current `.pw` host. Override it with `ANIMEPAHE_BASE_URL` only if the public host changes again.

If the queue shows `No links resolved (link_expired)` with a message like `Kwik returned HTTP 403 with the configured KWIK_COOKIE_FILE`, the saved Kwik browser cookies are missing, stale, or from a different IP/session. The backend can reuse an explicit Netscape-format cookie export for Kwik without reading browser profile databases.

To create or refresh that file:

1. Open the same browser you normally use for AnimePahe/Kwik on the same internet connection where this app is running. Do not use a VPN/proxy in one place and not the other.
2. In the browser, open an AnimePahe episode and continue through to the Kwik download page until the Kwik page loads successfully.
3. Export cookies for `kwik.cx` in **Netscape / cookies.txt format**. A browser extension such as `Get cookies.txt LOCALLY` can do this; export only the current `kwik.cx` cookies if the extension lets you filter by domain.
4. Save the exported file as `cookies.txt` in the repository root, next to `run_web.bat`.
5. Copy the exact user-agent from that same browser session and save it as a single line in `user-agent.txt`, also next to `run_web.bat`. In Chrome or Edge, open DevTools Console and run `navigator.userAgent`.
6. Restart the app with `run_web.bat`, then retry the failed queue item or manual import.

For the Windows batch startup, the file should be here:

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

The batch script sets these values on every launch:

```powershell
$env:KWIK_COOKIE_FILE="<repo>\cookies.txt"
$env:KWIK_USER_AGENT="<contents of user-agent.txt, or the built-in default if the file is missing>"
$env:ANIMEPAHE_USER_AGENT=$env:KWIK_USER_AGENT
$env:ANIMEPAHE_BASE_URL="https://animepahe.pw"
```

For non-batch startup, set the same environment variables before running `npm run start:localhost`.

Export only cookies you are allowed to use, keep the file private, and refresh it from a browser session on the same IP if the host expires it.

A CSV export from the browser network tab is not enough for this. It usually omits the `Cookie`, `Set-Cookie`, request-header, and response-body data required to replay a normal browser session.

If you still get HTTP 403 after refreshing `cookies.txt`, check these common causes:

- If the log says `Loaded 6 Kwik cookies` and then every `https://kwik.cx/f/...` request is still `403 Forbidden`, the app is reading the file correctly. The exported browser session is being rejected by Kwik/Cloudflare.
- The file is not Netscape format. It should contain tab-separated cookie rows, not CSV columns.
- The file does not contain current `kwik.cx` cookie rows.
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


