"""Contract tests: the code must agree with the captured live responses."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from douyin_api.adapters.request_profile import PROFILES
from douyin_api.transport.retry import (
    BAD_PARAM_CODES,
    PRIVACY_CODES,
    SESSION_EXPIRED_CODES,
    ErrorKind,
    classify_response,
)

CONTRACT = json.loads(
    (Path(__file__).parent / "fixtures" / "live_contract.json").read_text(encoding="utf-8")
)


@pytest.mark.parametrize(
    "profile_key,contract_key",
    [
        ("feed.featured", "feed_tab"),
        ("feed.recommend", "feed_tab"),
        ("video.detail", "video_detail"),
        ("video.comments", "video_comments"),
        ("user.profile", "user_profile"),
        ("user.posts", "user_posts"),
        ("search.general", "search_general"),
        ("user.following", "user_following"),
        ("user.followers", "user_followers"),
    ],
)
def test_profile_path_matches_captured_contract(profile_key, contract_key):
    contract = CONTRACT["responses"][contract_key]
    profile = PROFILES[profile_key]
    assert profile.response_key == contract.get("list_key") or profile.response_key == contract.get("object_key")


def test_corrected_relation_paths_are_the_verified_ones():
    assert PROFILES["user.following"].path == "/aweme/v1/web/user/following/list/"
    assert PROFILES["user.followers"].path == "/aweme/v1/web/user/follower/list/"
    for wrong in CONTRACT["path_corrections"]["wrong_guesses_404"]:
        assert wrong not in {p.path for p in PROFILES.values()}


def test_hot_search_is_public():
    assert PROFILES["feed.hot_search"].requires_auth is False


def test_write_profiles_are_post():
    for key in ("social.digg", "social.favorite", "social.follow", "social.comment"):
        assert PROFILES[key].method == "POST"
        assert PROFILES[key].is_write is True


def test_privacy_code_is_not_treated_as_expired():
    kind = classify_response(200, b"{}", {"status_code": 2096})
    assert kind is ErrorKind.PRIVACY_HIDDEN
    assert 2096 not in SESSION_EXPIRED_CODES
    assert 2096 in PRIVACY_CODES


def test_missing_param_code_is_bad_params():
    assert classify_response(200, b"{}", {"status_code": 5}) is ErrorKind.BAD_PARAMS
    assert 5 in BAD_PARAM_CODES


def test_documented_status_codes_cover_the_observed_set():
    observed = {int(k) for k in CONTRACT["status_codes"]}
    handled = SESSION_EXPIRED_CODES | PRIVACY_CODES | BAD_PARAM_CODES | {0}
    assert observed.issubset(handled)


def test_no_secret_material_in_fixtures():
    raw = json.dumps(CONTRACT)
    for banned in ("sessionid", "ttwid", "msToken", "a_bogus", "X-Bogus="):
        assert banned not in raw
