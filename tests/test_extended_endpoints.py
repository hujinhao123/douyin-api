"""Tests for the endpoints added in the bili-alignment pass."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from _auth_test_helpers import TEST_API_TOKEN, install_test_api_token

from douyin_api.adapters.request_profile import PROFILES
from douyin_api.auth.export import ExportService
from douyin_api.auth.qr_login import QRLoginManager
from douyin_api.auth.session import SessionState, SessionStore
from douyin_api.server import AppDeps, create_app
from douyin_api.storage.secrets import PlainProtector

SELF_USER = {
    "uid": "1001",
    "sec_uid": "SEC_SELF",
    "nickname": "me",
    "unique_id": "me_id",
    "signature": "",
    "follower_count": 3,
    "following_count": 4,
    "aweme_count": 5,
    "favoriting_count": 6,
    "avatar_thumb": {"url_list": ["https://example.invalid/a.jpg"]},
}


class FakeClient:
    """Routes every profile key to a canned payload; records the calls."""

    def __init__(self, payloads):
        self.payloads = payloads
        self.calls = []

    async def get(self, profile_key, params=None, **kw):
        self.calls.append(("GET", profile_key, dict(params or {})))
        value = self.payloads.get(profile_key)
        if callable(value):
            return value(params or {})
        if value is None:
            return {"status_code": 0}
        return value

    async def post(self, profile_key, params=None, **kw):
        self.calls.append(("POST", profile_key, dict(params or {})))
        return {"status_code": 0}


def build(tmp_path, payloads):
    install_test_api_token()
    store = SessionStore(tmp_path / "session.bin", protector=PlainProtector())
    store.save(
        SessionState(
            cookies={"sessionid": "S"},
            created_at=datetime.now(timezone.utc),
            expires_at=datetime.now(timezone.utc) + timedelta(days=1),
            adapter_version="2026.10.17",
            signer="browser",
            status="active",
        )
    )
    deps = AppDeps(
        session_store=store,
        export_service=ExportService(store, ttl_seconds=120),
        qr_manager=QRLoginManager(None),
        client=FakeClient(payloads),
    )
    return TestClient(create_app(deps=deps), headers={"Authorization": f"Bearer {TEST_API_TOKEN}"}), deps


def test_new_profiles_registered():
    for key in (
        "user.self",
        "user.collection",
        "user.history",
        "user.watchlater",
        "comment.replies",
        "mix.collection",
        "mix.detail",
        "search.user",
        "video.related",
    ):
        assert key in PROFILES, key


def test_abogus_only_where_verified():
    """No endpoint profile contains a guessed a_bogus value."""
    assert not hasattr(PROFILES["comment.replies"], "needs_abogus")
    assert not hasattr(PROFILES["search.user"], "needs_abogus")


def test_me_returns_counts(tmp_path):
    client, _ = build(
        tmp_path,
        {
            "user.self": {
                "status_code": 0,
                "user": SELF_USER,
                "user_collect_count": {"collect_count_list": [{"item_type": 2, "collect_count": 435}]},
                "user_watchlater_count": 2,
            }
        },
    )
    r = client.get("/api/me")
    assert r.status_code == 200
    body = r.json()
    assert body["user"]["sec_uid"] == "SEC_SELF"
    assert body["counts"]["watch_later"] == 2
    assert body["counts"]["collect"]["2"] == 435


def test_collection_uses_max_cursor_and_cut_version(tmp_path):
    client, deps = build(
        tmp_path,
        {
            "user.self": {"status_code": 0, "user": SELF_USER},
            "user.collection": {
                "status_code": 0,
                "aweme_list": [{"aweme_id": "v1", "desc": "d", "author": {"uid": "1"}}],
                "max_cursor": 12345,
                "has_more": 1,
            },
        },
    )
    r = client.get("/api/me/collection")
    assert r.status_code == 200
    body = r.json()
    assert body["cursor"] == 12345
    assert body["has_more"] is True
    assert body["items"][0]["id"] == "v1"
    call = [c for c in deps.client.calls if c[1] == "user.collection"][0]
    assert call[2]["cut_version"] == 1
    assert call[2]["sec_user_id"] == "SEC_SELF"


def test_history_paginates(tmp_path):
    client, _ = build(
        tmp_path,
        {
            "user.history": {
                "status_code": 0,
                "aweme_list": [{"aweme_id": "h1"}],
                "max_cursor": 999,
                "has_more": 0,
            }
        },
    )
    r = client.get("/api/me/history")
    body = r.json()
    assert body["cursor"] == 999
    assert body["has_more"] is False


def test_watch_later_reads_items_key(tmp_path):
    client, _ = build(
        tmp_path,
        {"user.watchlater": {"status_code": 0, "items": [{"aweme_id": "w1"}], "offset": 7, "has_more": 1}},
    )
    r = client.get("/api/me/watch-later")
    body = r.json()
    assert body["cursor"] == 7
    assert len(body["items"]) == 1


def test_mixes_reads_mix_infos(tmp_path):
    client, _ = build(
        tmp_path,
        {
            "mix.collection": {
                "status_code": 0,
                "mix_infos": [
                    {
                        "mix_info": {
                            "mix_id": "m1",
                            "mix_name": "A",
                            "cover_url": {"url_list": ["https://example.invalid/c.jpg"]},
                            "create_time": 1,
                        },
                        "statis": {"updated_to_episode": 12},
                    }
                ],
                "cursor": 5,
                "has_more": 1,
            }
        },
    )
    r = client.get("/api/me/mixes")
    body = r.json()
    assert body["items"][0]["mix_id"] == "m1"
    assert body["items"][0]["item_count"] == 12
    assert body["cursor"] == 5


def test_comment_replies_passes_item_id(tmp_path):
    client, deps = build(
        tmp_path,
        {
            "comment.replies": {
                "status_code": 0,
                "comments": [{"cid": "c2", "text": "reply", "user": {"uid": "9"}}],
                "cursor": 3,
                "total": 1,
                "has_more": 0,
            }
        },
    )
    r = client.get("/api/comment/c1/replies", params={"item_id": "v1"})
    assert r.status_code == 200
    body = r.json()
    assert body["items"][0]["id"] == "c2"
    call = [c for c in deps.client.calls if c[1] == "comment.replies"][0]
    assert call[2]["item_id"] == "v1"
    assert call[2]["comment_id"] == "c1"
    assert call[2]["cut_version"] == 1


def test_search_users_uses_offset(tmp_path):
    client, deps = build(
        tmp_path,
        {
            "search.user": {
                "status_code": 0,
                "data": [{"user_info": SELF_USER}],
                "has_more": 1,
                "extra": {"search_id": "SID"},
            }
        },
    )
    r = client.get("/api/search/users", params={"keyword": "abc"})
    body = r.json()
    assert body["items"][0]["sec_uid"] == "SEC_SELF"
    assert body["offset"] == 1
    assert body["search_id"] == "SID"
    call = [c for c in deps.client.calls if c[1] == "search.user"][0]
    assert call[2]["search_channel"] == "aweme_user_web"
    assert call[2]["offset"] == 0


def test_recommend_batch_dedupes(tmp_path):
    state = {"round": 0}

    def recommend(params):
        state["round"] += 1
        return {
            "status_code": 0,
            "aweme_list": [{"aweme_id": "v1"}, {"aweme_id": "v" + str(state["round"] + 1)}],
        }

    client, _ = build(tmp_path, {"feed.recommend": recommend})
    r = client.get("/api/feed/recommend/batch", params={"want": 3, "rounds": 5})
    body = r.json()
    ids = [i["id"] for i in body["items"]]
    assert len(ids) == len(set(ids))
    assert body["count"] == len(ids)
    assert body["rounds_used"] >= 2


def test_video_stream_caches_signed_url_and_keeps_length(tmp_path, monkeypatch):
    import douyin_api.endpoints.media as media_module

    class FakeResponse:
        def __init__(self, status_code=206):
            self.status_code = status_code
            self.headers = {
                "content-type": "video/mp4",
                "content-length": "4",
                "content-range": "bytes 0-3/4",
                "accept-ranges": "bytes",
            }

        async def aiter_bytes(self):
            if self.status_code in (200, 206):
                yield b"test"

        async def aclose(self):
            return None

    class FakeHTTPClient:
        seen_urls = []

        def __init__(self, *args, **kwargs):
            pass

        def build_request(self, method, url, headers=None):
            return {"method": method, "url": url, "headers": headers or {}}

        async def send(self, request, stream=True):
            url = request["url"]
            FakeHTTPClient.seen_urls.append(url)
            return FakeResponse(403 if url.endswith("/blocked.mp4") else 206)

        async def aclose(self):
            return None

    media_module._media_cache.clear()
    monkeypatch.setattr(media_module.httpx, "AsyncClient", FakeHTTPClient)
    client, deps = build(
        tmp_path,
        {
            "video.media": {
                "status_code": 0,
                "aweme_detail": {"aweme_id": "v1", "video": {"play_addr": {"url_list": [
                    "https://cdn.example/blocked.mp4",
                    "https://cdn.example/working.mp4",
                ]}}},
            }
        },
    )

    first = client.get("/api/video/v1/stream", headers={"Range": "bytes=0-3"})
    assert first.status_code == 206
    assert first.content == b"test"
    assert first.headers["content-length"] == "4"
    assert first.headers["content-range"] == "bytes 0-3/4"
    assert FakeHTTPClient.seen_urls == [
        "https://cdn.example/blocked.mp4",
        "https://cdn.example/working.mp4",
    ]

    # Second seek reuses the cached signed URL: no extra media lookup, and the
    # working URL is tried first so the blocked candidate is not re-hit.
    FakeHTTPClient.seen_urls.clear()
    second = client.get("/api/video/v1/stream", headers={"Range": "bytes=100-103"})
    assert second.status_code == 206
    assert FakeHTTPClient.seen_urls == ["https://cdn.example/working.mp4"]
    assert [c[1] for c in deps.client.calls] == ["video.media"]


def test_mix_detail_returns_videos(tmp_path):
    client, _ = build(
        tmp_path,
        {"mix.detail": {"status_code": 0, "aweme_list": [{"aweme_id": "m1"}], "cursor": 2, "has_more": 1}},
    )
    r = client.get("/api/mix/abc")
    body = r.json()
    assert body["items"][0]["id"] == "m1"
    assert body["cursor"] == 2


def test_new_routes_in_openapi(tmp_path):
    client, _ = build(tmp_path, {})
    paths = client.get("/openapi.json").json()["paths"]
    for p in (
        "/api/me",
        "/api/me/collection",
        "/api/me/history",
        "/api/me/watch-later",
        "/api/me/mixes",
        "/api/comment/{comment_id}/replies",
        "/api/search/users",
        "/api/feed/recommend/batch",
        "/api/mix/{mix_id}",
    ):
        assert p in paths, p

