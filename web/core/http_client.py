"""Shared curl_cffi HTTP layer with browser TLS impersonation.


All AnimePahe, Kwik, and CDN traffic should go through curl_cffi so the TLS
and HTTP/2 fingerprints match a real Chrome client instead of Python's default
TLS stack.
"""

from __future__ import annotations


import os


from curl_cffi.requests import AsyncSession

try:
    from curl_cffi.requests.exceptions import (
        ConnectionError as CurlConnectionError,
        HTTPError as CurlHTTPError,
        RequestException as CurlRequestError,
        Timeout as CurlTimeout,
    )
except Exception:  # pragma: no cover - compatibility for older curl_cffi
    from curl_cffi.requests.errors import RequestsError as CurlRequestError  # type: ignore

    CurlTimeout = CurlConnectionError = CurlHTTPError = CurlRequestError


# Do not use the environment variable name CURL_IMPERSONATE. curl_cffi/libcurl
# also observes it, and on Windows it can make every request fail before network
# I/O with curl error 43 while setting CURLOPT_URL.
# `or "chrome"` (not a get() default) so that a set-but-empty
# ANIMEPAHE_CURL_IMPERSONATE does not silently disable impersonation and revert
# to the plain-Python TLS fingerprint that Cloudflare/DDoS-Guard block.
IMPERSONATE_TARGET = os.environ.get("ANIMEPAHE_CURL_IMPERSONATE") or "chrome"
os.environ.pop("CURL_IMPERSONATE", None)


def _parse_timeout(raw: str | None, default: float) -> float:
    try:
        return float(raw) if raw not in (None, "") else default
    except (TypeError, ValueError):
        return default


DEFAULT_TIMEOUT = _parse_timeout(os.environ.get("HTTP_TIMEOUT"), 30.0)


NETWORK_EXCEPTIONS: tuple[type[Exception], ...] = tuple(
    {CurlTimeout, CurlConnectionError, CurlRequestError}
)


def make_async_session(
    *,
    timeout: float | tuple[float, float] | None = DEFAULT_TIMEOUT,
    max_clients: int = 10,
    **kwargs,
) -> AsyncSession:
    """Create an AsyncSession configured for browser TLS impersonation."""
    return AsyncSession(
        impersonate=IMPERSONATE_TARGET,
        timeout=timeout,
        max_clients=max_clients,
        **kwargs,
    )
