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

If Kwik returns `403 Forbidden` while the same page works in your browser, the host may be requiring a fresh browser session for your IP. The backend can reuse an explicit Netscape-format cookie export for Kwik without reading browser profile databases.

For the Windows batch startup, export the Kwik browser cookies to `cookies.txt` in the repository root:

```text
animepahe-auto-downloader/
  cookies.txt
  run_web.bat
```

Then launch:

```bat
run_web.bat
```

The batch script sets these values on every launch:

```powershell
$env:KWIK_COOKIE_FILE="<repo>\cookies.txt"
$env:KWIK_USER_AGENT="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36"
$env:ANIMEPAHE_USER_AGENT=$env:KWIK_USER_AGENT
$env:ANIMEPAHE_BASE_URL="https://animepahe.pw"
```

For non-batch startup, set the same environment variables before running `npm run start:localhost`.

Export only cookies you are allowed to use, keep the file private, and refresh it from a browser session on the same IP if the host expires it.

A CSV export from the browser network tab is not enough for this. It usually omits the `Cookie`, `Set-Cookie`, request-header, and response-body data required to replay a normal browser session.

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


