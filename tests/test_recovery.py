"""Drift-detection tests: each failure mode must produce an actionable verdict."""

from __future__ import annotations

import pytest

from douyin_api.recovery import (
    MINIMAL_PARAMS,
    ProfileProbe,
    build_report,
    classify_probe,
    probe_all,
    probe_profile,
)
from douyin_api.adapters.request_profile import PROFILES


BASELINE = {
    "responses": {
        "feed_tab": {"top_level": ["aweme_list", "has_more", "log_pb", "status_code"], "list_key": "aweme_list"},
        "video_detail": {"top_level": ["aweme_detail", "log_pb", "status_code"], "object_key": "aweme_detail"},
    }
}


class FakeClient:
    def __init__(self, responses):
        self.responses = responses
        self.calls = []

    async def get(self, key, params=None):
        self.calls.append((key, dict(params or {})))
        value = self.responses[key]
        if isinstance(value, Exception):
            raise value
        return value


def test_healthy_response_is_ok():
    probe = ProfileProbe(
        profile="feed.featured",
        path=PROFILES["feed.featured"].path,
        http=200,
        status_code=0,
        top_level_keys=["aweme_list", "has_more", "log_pb", "status_code"],
        list_key_present=True,
        list_len=5,
    )
    assert classify_probe(probe, BASELINE["responses"]["feed_tab"]) == "OK"


def test_404_means_the_path_moved():
    probe = ProfileProbe(profile="feed.featured", path="/old/", http=404)
    assert classify_probe(probe, None) == "PATH_CHANGED"


def test_401_means_the_session_died():
    probe = ProfileProbe(profile="feed.featured", path="/x/", http=401)
    assert classify_probe(probe, None) == "AUTH_CHANGED"


def test_status_8_means_session_expired():
    probe = ProfileProbe(profile="feed.featured", path="/x/", http=200, status_code=8)
    assert classify_probe(probe, None) == "AUTH_CHANGED"


def test_missing_key_means_field_changed():
    probe = ProfileProbe(
        profile="feed.featured",
        path="/x/",
        http=200,
        status_code=0,
        top_level_keys=["has_more", "status_code"],  # aweme_list disappeared
        list_key_present=False,
    )
    assert classify_probe(probe, BASELINE["responses"]["feed_tab"]) == "FIELD_CHANGED"


def test_status_5_means_params_changed():
    probe = ProfileProbe(profile="feed.featured", path="/x/", http=200, status_code=5)
    assert classify_probe(probe, None) == "PARAMS_CHANGED"


def test_signer_failure_is_distinguishable():
    probe = ProfileProbe(profile="feed.featured", path="/x/", error="SignError: no token")
    assert classify_probe(probe, None) == "SIGN_FAILED"


def test_transport_error_is_not_mistaken_for_drift():
    probe = ProfileProbe(profile="feed.featured", path="/x/", error="ConnectError: refused")
    assert classify_probe(probe, None) == "TRANSPORT_ERROR"


async def test_probe_profile_records_shape():
    client = FakeClient({"feed.featured": {"status_code": 0, "aweme_list": [{}, {}], "has_more": 1}})
    probe = await probe_profile(client, "feed.featured")
    assert probe.http == 200
    assert probe.list_len == 2
    assert probe.list_key_present is True
    assert "aweme_list" in probe.top_level_keys
    assert probe.pagination["has_more"] == 1


async def test_probe_profile_turns_exceptions_into_verdicts():
    client = FakeClient({"feed.featured": RuntimeError("signer exploded")})
    probe = await probe_profile(client, "feed.featured")
    assert probe.error
    assert classify_probe(probe, None) in {"TRANSPORT_ERROR", "SIGN_FAILED"}


async def test_probe_all_only_covers_profiles_with_safe_params():
    client = FakeClient({k: {"status_code": 0, "aweme_list": []} for k in MINIMAL_PARAMS})
    probes = await probe_all(client)
    assert {p.profile for p in probes} == set(MINIMAL_PARAMS)
    for key in ("video.detail", "social.digg"):
        assert key not in {p.profile for p in probes}


def test_report_is_healthy_only_when_every_profile_is_ok():
    good = ProfileProbe(
        profile="feed.featured",
        path="/x/",
        http=200,
        status_code=0,
        top_level_keys=["aweme_list", "has_more", "log_pb", "status_code"],
        list_key_present=True,
    )
    report = build_report([good], BASELINE)
    assert report["healthy"] is True
    assert report["next_action"] == "none"


def test_report_points_at_the_right_fix():
    bad = ProfileProbe(profile="feed.featured", path="/old/", http=404)
    report = build_report([bad], BASELINE)
    assert report["healthy"] is False
    assert "paths moved" in report["next_action"]
    assert report["profiles"][0]["verdict"] == "PATH_CHANGED"


def test_report_recommends_relogin_when_auth_changed():
    bad = ProfileProbe(profile="feed.featured", path="/x/", http=401)
    assert "QR login" in build_report([bad], BASELINE)["next_action"]


def test_report_recommends_signer_check():
    bad = ProfileProbe(profile="feed.featured", path="/x/", error="SignError: empty token")
    assert "frontierSign" in build_report([bad], BASELINE)["next_action"]


def test_report_recommends_field_update():
    bad = ProfileProbe(
        profile="feed.featured", path="/x/", http=200, status_code=0,
        top_level_keys=["has_more"], list_key_present=False,
    )
    assert "normalize_" in build_report([bad], BASELINE)["next_action"]
