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
- Node.js 18+ and npm

## Setup
```bash
git clone https://github.com/your-username/animepahe-auto-downloader.git
cd animepahe-auto-downloader
npm install
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

## Localhost Diagnostics and Maintenance
- `GET /health` - local health status, queue summary, metrics, startup checks.
- `GET /api/diagnostics` - recent failures + environment checks.
- `GET /api/backup/export` - export settings + queue/history backup.
- `POST /api/backup/import` - import settings + queue/history backup payload.
- `POST /api/maintenance/cleanup` - remove stale partial/lock files and orphan queue entries.

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


