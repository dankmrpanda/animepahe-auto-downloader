from __future__ import annotations

from core.downloader import DownloadHTTPError, _is_retryable, classify_failure
from core.http_client import CurlTimeout


def test_classify_http_status_errors() -> None:
    assert classify_failure(DownloadHTTPError(403))[0] == "link_expired"
    assert classify_failure(DownloadHTTPError(500))[0] == "network"
    assert classify_failure(DownloadHTTPError(507))[0] == "disk_full"


def test_retryability_matches_transport_and_status() -> None:
    assert _is_retryable(DownloadHTTPError(500))
    assert not _is_retryable(DownloadHTTPError(403))
    assert _is_retryable(CurlTimeout("timed out"))


def test_message_classification_fallbacks() -> None:
    assert classify_failure("kwik forbidden")[0] == "link_expired"
    assert classify_failure("no space left on device")[0] == "disk_full"
    assert classify_failure("connection reset by peer")[0] == "network"
