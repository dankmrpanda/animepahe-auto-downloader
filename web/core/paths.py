"""
Path and filename safety helpers for localhost-only file operations.
"""

from __future__ import annotations

import os
import re
from urllib.parse import unquote

WINDOWS_RESERVED_NAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    "COM1",
    "COM2",
    "COM3",
    "COM4",
    "COM5",
    "COM6",
    "COM7",
    "COM8",
    "COM9",
    "LPT1",
    "LPT2",
    "LPT3",
    "LPT4",
    "LPT5",
    "LPT6",
    "LPT7",
    "LPT8",
    "LPT9",
}

INVALID_FS_CHARS_RE = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


class PathSafetyError(ValueError):
    """Raised when a path/filename fails local safety validation."""


def normalize_download_path(path: str) -> str:
    """Normalize and validate a download directory path."""
    raw = str(path or "").strip()
    if not raw:
        raise PathSafetyError("Download path is required")

    normalized = os.path.abspath(os.path.normpath(os.path.expanduser(raw)))
    if not os.path.isabs(normalized):
        raise PathSafetyError("Download path must be absolute")

    os.makedirs(normalized, exist_ok=True)
    if not os.path.isdir(normalized):
        raise PathSafetyError("Download path must be a directory")

    return normalized


def safe_join(base_path: str, *parts: str) -> str:
    """Join paths while enforcing that the result stays inside base_path."""
    base_abs = os.path.abspath(base_path)
    target_abs = os.path.abspath(os.path.normpath(os.path.join(base_abs, *parts)))
    if os.path.commonpath([base_abs, target_abs]) != base_abs:
        raise PathSafetyError("Resolved path escapes download directory")
    return target_abs


def sanitize_path_segment(
    segment: str,
    fallback: str = "unknown",
    reject_separators: bool = False,
) -> str:
    """Sanitize a single folder/file path segment."""
    raw = unquote(str(segment or "")).strip()
    if not raw:
        raw = fallback

    if reject_separators and ("/" in raw or "\\" in raw):
        raise PathSafetyError("Path segments must not include separators")
    raw = raw.replace("/", " ").replace("\\", " ")

    safe = INVALID_FS_CHARS_RE.sub("_", raw)
    safe = safe.strip().strip(".")
    safe = re.sub(r"\s+", " ", safe)

    if safe in {"", ".", ".."}:
        raise PathSafetyError("Path segment resolves to an unsafe value")

    if safe.upper() in WINDOWS_RESERVED_NAMES:
        safe = f"_{safe}"

    # Keep filesystem-friendly max segment size.
    if len(safe) > 180:
        safe = safe[:180].rstrip(" .")

    if safe in {"", ".", ".."}:
        raise PathSafetyError("Path segment resolves to an unsafe value")

    return safe


def sanitize_filename(filename: str) -> str:
    """Sanitize and validate a filename (single segment, no traversal)."""
    safe = sanitize_path_segment(filename, fallback="download", reject_separators=True)
    if ".." in safe.split("."):
        raise PathSafetyError("Filename contains unsafe path traversal segment")
    return safe
