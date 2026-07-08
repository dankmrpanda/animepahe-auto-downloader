"""
Runtime diagnostics and self-check helpers.
"""

from __future__ import annotations

import os
import shutil
import tempfile
from datetime import datetime, timezone
from typing import Any

from core.clearance import cookie_file_summary, default_store_path, normalize_clearance_mode
from core.http_client import IMPERSONATE_TARGET, make_async_session


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _check_download_path_exists(download_path: str) -> dict[str, Any]:
    exists = os.path.isdir(download_path)
    return {
        "ok": exists,
        "detail": "Download path exists" if exists else "Download path does not exist",
        "path": download_path,
    }


def _check_download_path_writable(download_path: str) -> dict[str, Any]:
    try:
        os.makedirs(download_path, exist_ok=True)
        probe = tempfile.NamedTemporaryFile(
            mode="w",
            prefix=".write_check_",
            suffix=".tmp",
            dir=download_path,
            delete=False,
            encoding="utf-8",
        )
        probe.write("ok")
        probe.flush()
        probe.close()
        os.remove(probe.name)
        return {"ok": True, "detail": "Download path is writable", "path": download_path}
    except Exception as e:
        return {
            "ok": False,
            "detail": f"Download path is not writable: {e}",
            "path": download_path,
        }


def _check_disk_space(download_path: str) -> dict[str, Any]:
    try:
        usage = shutil.disk_usage(download_path)
        return {
            "ok": True,
            "detail": "Disk usage collected",
            "path": download_path,
            "free_bytes": usage.free,
            "total_bytes": usage.total,
            "used_bytes": usage.used,
        }
    except Exception as e:
        return {"ok": False, "detail": f"Disk usage check failed: {e}", "path": download_path}


async def _check_internet_reachability(test_url: str = "https://animepahe.com") -> dict[str, Any]:
    base_url = test_url.rstrip("/")
    probe_url = f"{base_url}/api?m=search&l=1&q=naruto"
    headers = {
        "accept": "application/json, text/javascript, */*; q=0.01",
        "accept-language": "en-US,en;q=0.9",
        "x-requested-with": "XMLHttpRequest",
        "cookie": "__ddg2_=",
        "referer": base_url + "/",
    }
    try:
        async with make_async_session(timeout=8.0) as client:
            response = await client.get(probe_url, headers=headers, allow_redirects=True)
        json_ok = False
        if response.status_code == 200:
            try:
                json_ok = isinstance(response.json(), dict)
            except Exception:
                json_ok = False
        return {
            "ok": response.status_code == 200 and json_ok,
            "detail": (
                "Reachable JSON API"
                if response.status_code == 200 and json_ok
                else f"Unexpected response ({response.status_code})"
            ),
            "url": probe_url,
            "status_code": response.status_code,
        }
    except Exception as e:
        return {"ok": False, "detail": f"Unreachable: {e}", "url": probe_url}


async def run_environment_checks(
    download_path: str,
    animepahe_base_url: str | None = None,
) -> dict[str, Any]:
    test_url = animepahe_base_url or "https://animepahe.com"
    anime_cookie = cookie_file_summary(os.environ.get("ANIMEPAHE_COOKIE_FILE"), ("animepahe.",))
    kwik_cookie = cookie_file_summary(os.environ.get("KWIK_COOKIE_FILE"), ("kwik.",))
    checks: dict[str, Any] = {
        "path_exists": _check_download_path_exists(download_path),
        "path_writable": _check_download_path_writable(download_path),
        "disk_space": _check_disk_space(download_path),
        "internet_reachability": await _check_internet_reachability(test_url),
    }
    return {
        "checked_at": utc_now_iso(),
        "ok": all(item.get("ok", False) for item in checks.values()),
        "animepahe_base_url": test_url.rstrip("/"),
        "curl_impersonate": IMPERSONATE_TARGET,
        "clearance_mode": normalize_clearance_mode(),
        "clearance_store": str(default_store_path()),
        "animepahe_cookie_rows": anime_cookie["rows"],
        "animepahe_has_cf_clearance": anime_cookie["has_cf_clearance"],
        "kwik_cookie_rows": kwik_cookie["rows"],
        "kwik_has_cf_clearance": kwik_cookie["has_cf_clearance"],
        "kwik_has_kwik_session": kwik_cookie["has_kwik_session"],
        "checks": checks,
    }


def collect_recent_errors(failed_tasks: list[Any], limit: int = 20) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for task in reversed(failed_tasks[-limit:]):
        items.append(
            {
                "id": task.id,
                "filename": task.filename,
                "anime_title": task.anime_title,
                "episode": task.episode,
                "resolution": task.resolution,
                "status": task.status,
                "failure_reason": task.failure_reason,
                "failure_detail": task.failure_detail or task.error,
                "error": task.error,
                "retry_count": task.retry_count,
                "terminal": task.terminal,
                "created_at": task.created_at.isoformat() if task.created_at else None,
                "completed_at": task.completed_at.isoformat() if task.completed_at else None,
            }
        )
    return items


def build_health_payload(
    download_manager: Any,
    startup_checks: dict[str, Any] | None = None,
    started_at: str | None = None,
) -> dict[str, Any]:
    manager_ready = bool(download_manager)
    running = bool(download_manager._running) if manager_ready else False
    status = "healthy" if manager_ready and running else "degraded"

    queue_status: dict[str, Any] = {}
    metrics: dict[str, Any] = {}
    if manager_ready:
        queue_status = {
            "pending_count": len(download_manager._pending_tasks_snapshot()),
            "active_count": len(download_manager.active_tasks),
            "completed_count": len(download_manager.completed_tasks),
            "failed_count": len(download_manager.failed_tasks),
            "paused": download_manager.is_paused,
        }
        metrics = download_manager.get_metrics()

    return {
        "status": status,
        "started_at": started_at,
        "checked_at": utc_now_iso(),
        "download_path": download_manager.download_path if manager_ready else None,
        "workers_active": running,
        "max_workers": download_manager.max_workers if manager_ready else None,
        "metrics": metrics,
        "queue": queue_status,
        "animepahe_base_url": (startup_checks or {}).get("animepahe_base_url"),
        "curl_impersonate": (startup_checks or {}).get("curl_impersonate", IMPERSONATE_TARGET),
        "clearance_mode": (startup_checks or {}).get("clearance_mode", normalize_clearance_mode()),
        "startup_checks": startup_checks or {},
    }
