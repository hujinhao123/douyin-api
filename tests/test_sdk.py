"""SDK tests: verify path building and payload shaping without a live server."""

from __future__ import annotations

import json

import httpx
import pytest

from douyin_api.sdk import DouyinApiClient


def build(handler):
    return DouyinApiClient(base_url="http://local.test", transport=httpx.MockTransport(handler))


def recorder(seen):
    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(
            {
                "method": request.method,
                "path": request.url.path,
                "query": dict(httpx.QueryParams(request.url.query.decode())),
                "body": json.loads(request.content) if request.content else None,
            }
        )
        return httpx.Response(200, json={"ok": True})

    return handler


def test_feed_paths_and_query():
    seen = []
    client = build(recorder(seen))
    client.featured(count=5)
    client.recommend(count=7)
    client.following_feed(count=3)
    client.hot_search(limit=9)
    paths = [(s["method"], s["path"], s["query"]) for s in seen]
    assert paths[0] == ("GET", "/api/feed/featured", {"count": "5"})
    assert paths[1] == ("GET", "/api/feed/recommend", {"count": "7"})
    assert paths[2] == ("GET", "/api/feed/following", {"count": "3"})
    assert paths[3] == ("GET", "/api/feed/hot-search", {"limit": "9"})


def test_search_drops_none_filters():
    seen = []
    client = build(recorder(seen))
    client.search("kw", cursor=20, count=15, sort_type=None)
    q = seen[0]["query"]
    assert q["keyword"] == "kw"
    assert q["cursor"] == "20"
    assert "sort_type" not in q


def test_video_and_user_paths():
    seen = []
    client = build(recorder(seen))
    client.video("123")
    client.video_author("123")
    client.video_comments("123", cursor=5)
    client.video_media("123")
    client.user("MS4wLj")
    client.user_videos("MS4wLj", cursor=0)
    client.user_following("MS4wLj")
    client.user_followers("MS4wLj")
    assert [s["path"] for s in seen] == [
        "/api/video/123",
        "/api/video/123/author",
        "/api/video/123/comments",
        "/api/video/123/media",
        "/api/user/MS4wLj",
        "/api/user/MS4wLj/videos",
        "/api/user/MS4wLj/following",
        "/api/user/MS4wLj/followers",
    ]


def test_write_defaults_to_dry_run():
    seen = []
    client = build(recorder(seen))
    client.like("123")
    body = seen[0]["body"]
    assert body == {"dry_run": True, "confirm": False, "idempotency_key": None}
    assert seen[0]["method"] == "POST"


def test_delete_verbs_are_used_for_undo():
    seen = []
    client = build(recorder(seen))
    client.unlike("1")
    client.unfavorite("1")
    client.unfollow("u")
    assert [s["method"] for s in seen] == ["DELETE", "DELETE", "DELETE"]


def test_confirmed_write_passes_confirm_and_key():
    seen = []
    client = build(recorder(seen))
    client.favorite("9", dry_run=False, confirm=True, key="k-1")
    assert seen[0]["body"] == {"dry_run": False, "confirm": True, "idempotency_key": "k-1"}


def test_comment_sends_text_query_and_body():
    seen = []
    client = build(recorder(seen))
    client.comment("9", "hello", dry_run=False, confirm=True)
    assert seen[0]["query"]["text"] == "hello"
    assert seen[0]["body"]["confirm"] is True


def test_auth_flow_paths():
    seen = []
    client = build(recorder(seen))
    client.start_qr()
    client.qr_status("abc")
    client.cancel_qr("abc")
    client.session()
    client.issue_export_ticket()
    client.redeem_export_ticket("t")
    client.revoke_session()
    assert [(s["method"], s["path"]) for s in seen] == [
        ("POST", "/auth/qr/start"),
        ("GET", "/auth/qr/abc/status"),
        ("POST", "/auth/qr/abc/cancel"),
        ("GET", "/auth/session"),
        ("POST", "/auth/session/export"),
        ("POST", "/auth/session/export/redeem"),
        ("POST", "/auth/session/revoke"),
    ]
    assert seen[5]["body"] == {"ticket": "t"}


def test_error_status_raises():
    def handler(request):
        return httpx.Response(401, json={"detail": {"code": "SESSION_MISSING"}})

    client = build(handler)
    with pytest.raises(httpx.HTTPStatusError):
        client.featured()

def test_diagnostics_and_version_paths():
    seen = []
    client = build(recorder(seen))
    client.diagnostics()
    client.version()
    assert [(s["method"], s["path"]) for s in seen] == [
        ("GET", "/diagnostics/probe"),
        ("GET", "/diagnostics/version"),
    ]


def test_extended_bili_aligned_paths_and_payloads():
    seen = []
    client = build(recorder(seen))

    client.recommend_batch(want=12, rounds=4, count=6)
    client.search_users("猫", offset=20, count=7, search_id="sid-1")
    client.me()
    client.my_collection(cursor=3, count=18)
    client.my_history(cursor=4, count=20)
    client.my_watch_later(cursor=5, count=20)
    client.my_mixes(cursor=6, count=20)
    client.comment_replies("comment-1", item_id="video-1", cursor=7, count=10)
    client.mix_videos("mix-1", cursor=8, count=20)

    assert [(s["method"], s["path"]) for s in seen] == [
        ("GET", "/api/feed/recommend/batch"),
        ("GET", "/api/search/users"),
        ("GET", "/api/me"),
        ("GET", "/api/me/collection"),
        ("GET", "/api/me/history"),
        ("GET", "/api/me/watch-later"),
        ("GET", "/api/me/mixes"),
        ("GET", "/api/comment/comment-1/replies"),
        ("GET", "/api/mix/mix-1"),
    ]
    assert seen[0]["query"] == {"want": "12", "rounds": "4", "count": "6"}
    assert seen[1]["query"] == {
        "keyword": "猫",
        "offset": "20",
        "count": "7",
        "search_id": "sid-1",
    }
    assert seen[7]["query"] == {
        "item_id": "video-1",
        "cursor": "7",
        "count": "10",
    }


def test_sdk_exposes_every_documented_route_family():
    """Guard against a route existing on the server but missing from the SDK."""
    expected = {
        "health",
        "start_qr",
        "qr_status",
        "qr_image",
        "cancel_qr",
        "session",
        "issue_export_ticket",
        "redeem_export_ticket",
        "revoke_session",
        "featured",
        "recommend",
        "following_feed",
        "hot_search",
        "recommend_batch",
        "search",
        "search_users",
        "video",
        "video_author",
        "video_comments",
        "video_media",
        "user",
        "user_videos",
        "user_following",
        "user_followers",
        "me",
        "my_collection",
        "my_history",
        "my_watch_later",
        "my_mixes",
        "comment_replies",
        "mix_videos",
        "like",
        "unlike",
        "favorite",
        "unfavorite",
        "follow",
        "unfollow",
        "comment",
        "diagnostics",
        "version",
        "openapi",
    }
    actual = {m for m in dir(DouyinApiClient) if not m.startswith("_")}
    missing = expected - actual
    assert not missing, f"SDK missing: {sorted(missing)}"
