from __future__ import annotations

from core.clearance import looks_like_cf_challenge


def test_detects_cf_mitigated_header() -> None:
    assert looks_like_cf_challenge(403, {"cf-mitigated": "challenge"}, "")


def test_detects_managed_challenge_body() -> None:
    assert looks_like_cf_challenge(403, {}, "<title>Just a moment...</title>")
    assert looks_like_cf_challenge(403, {}, "/cdn-cgi/challenge-platform/h/b/orchestrate/")


def test_ignores_non_challenge_responses() -> None:
    assert not looks_like_cf_challenge(200, {"cf-mitigated": "challenge"}, "ok")
    assert not looks_like_cf_challenge(403, {}, "plain forbidden")
