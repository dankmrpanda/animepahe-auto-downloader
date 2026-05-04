# Localhost Production TODO

Purpose: a persistent checklist for future model/user sessions to make this app production-grade for localhost-only use (single user, not publicly exposed).

## P0 Core Reliability

- [x] Run backend in non-dev mode (`no --reload`) with automatic restart on crash.
- [x] Persist queue/history/settings to SQLite so app restarts do not lose state.
- [x] Restore pending/in-progress downloads automatically on startup.
- [x] Ensure graceful shutdown: active downloads pause safely and resume later.
- [x] Keep strict download integrity checks before marking tasks complete.
- [x] Add capped retry policy with exponential backoff and clear terminal failure state.

## P0 Local Safety

- [x] Validate and normalize download paths before use.
- [x] Sanitize filenames and reject unsafe path segments.
- [x] Add disk-space preflight checks before starting batch downloads.
- [x] Add file lock/write safeguards to avoid duplicate or conflicting writes.

## P1 Seamless UX

- [x] Show actionable failure reasons (`network`, `link expired`, `integrity failed`, `disk full`).
- [x] Add one-click recovery actions (`retry`, `re-resolve link`, `re-validate file`).
- [x] Keep fast perceived load with frontend + backend caching.
- [x] Preserve user preferences reliably (quality, workers, paths, UI state).
- [x] Improve keyboard-only navigation and status announcements for accessibility.
- [x] Verify that the UI follows the [Web Interface Guidelines](https://vercel.com/design/guidelines)

## P1 Local Observability

- [x] Add rotating local log files with structured log fields.
- [x] Add lightweight metrics counters (downloads started/completed/failed/retried).
- [x] Keep a working `/health` endpoint for local diagnostics.
- [x] Add an in-app diagnostics view (recent errors + environment checks).

## P1 Setup and Maintenance

- [x] Make one-command setup/start checks explicit (Python/Node deps and versions).
- [x] Add startup self-checks (write permissions, path exists, internet reachability).
- [x] Add export/import for settings + download history backup.
- [x] Add a safe cleanup tool for stale partial files and orphan queue entries.

## Not Required for Localhost-Only

- [ ] Confirm app remains localhost-only (no public/LAN exposure by default).
- [ ] Defer internet-facing requirements (auth/SSO, TLS cert automation, WAF, multi-tenant RBAC, horizontal scaling).
