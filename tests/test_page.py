from __future__ import annotations

import pytest

from douyin_api.adapters.page import extract_media, normalize_aweme, normalize_comment, normalize_user, pick_list


def test_pick_list_prefers_named_key():
    payload = {"aweme_list": [{"a": 1}], "items": [{"b": 2}]}
    assert pick_list(payload, "aweme_list") == [{"a": 1}]


def test_pick_list_falls_back_to_data():
    assert pick_list({"data": [1, 2]}, "missing") == [1, 2]


def test_pick_list_returns_empty_for_unknown_shape():
    assert pick_list({"unexpected": 1}, "aweme_list") == []


def test_normalize_aweme_keeps_stable_fields():
    raw = {
        "aweme_id": "7300000000000000000",
        "desc": "hello",
        "create_time": 1700000000,
        "author": {"uid": "1", "sec_uid": "MS4wLj", "nickname": "n", "unique_id": "u"},
        "statistics": {"digg_count": 5, "comment_count": 6, "play_count": 7},
        "video": {"duration": 15000, "ratio": "720p", "cover": {"url_list": ["c"]}, "play_addr": {"url_list": ["p"]}},
    }
    out = normalize_aweme(raw)
    assert out["id"] == "7300000000000000000"
    assert out["author"]["sec_uid"] == "MS4wLj"
    assert out["stats"]["digg_count"] == 5
    assert out["video"]["play_addr"] == "p"


def test_normalize_aweme_tolerates_missing_sections():
    out = normalize_aweme({"aweme_id": "1"})
    assert out["id"] == "1"
    assert out["author"] is None
    assert out["video"] is None
    assert out["stats"]["digg_count"] is None


def test_normalize_comment_maps_user():
    out = normalize_comment({"cid": "c1", "text": "hi", "user": {"uid": "9", "nickname": "z"}})
    assert out["id"] == "c1"
    assert out["user"]["nickname"] == "z"


def test_normalize_user_maps_counts():
    out = normalize_user({"uid": "1", "follower_count": 10, "following_count": 2, "aweme_count": 3})
    assert out["follower_count"] == 10
    assert out["aweme_count"] == 3


def test_extract_media_builds_bitrate_table():
    detail = {
        "aweme_id": "1",
        "video": {
            "duration": 9000,
            "cover": {"url_list": ["cov"]},
            "play_addr": {"url_list": ["play1", "play2"]},
            "download_addr": {"url_list": ["dl"]},
            "bit_rate": [
                {"gear_name": "1080p", "bit_rate": 3000, "width": 1920, "height": 1080, "play_addr": {"url_list": ["hd"]}}
            ],
        },
        "music": {"title": "song", "play_url": {"url_list": ["m"]}},
    }
    out = extract_media(detail)
    assert out["play_addr"] == ["play1", "play2"]
    assert out["bit_rates"][0]["gear_name"] == "1080p"
    assert out["bit_rates"][0]["urls"] == ["hd"]
    assert out["music"]["title"] == "song"


def test_extract_media_without_video_is_empty_not_crash():
    out = extract_media({"aweme_id": "1"})
    assert out["play_addr"] == []
    assert out["bit_rates"] == []
    assert out["music"] is None

def test_normalize_aweme_keeps_large_id_as_string():
    raw = {"aweme_id": 7697712884738001698}
    out = normalize_aweme(raw)
    assert out["id"] == "7697712884738001698"
    assert isinstance(out["id"], str)
