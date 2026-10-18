from __future__ import annotations

from _auth_test_helpers import TEST_API_TOKEN, install_test_api_token

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from douyin_api.auth.export import ExportService
from douyin_api.auth.qr_login import QRLoginManager
from douyin_api.auth.session import SessionState, SessionStore
from douyin_api.server import AppDeps, create_app
from douyin_api.storage.secrets import PlainProtector


class FakeHTTP:
    def __init__(self, responses):
        self.responses = list(responses)

    async def get_json(self, path, params=None, headers=None):
        return self.responses.pop(0)


class FakeClient:
    def __init__(self):
        self.calls = []

    async def get(self, profile_key, params=None, **kw):
        self.calls.append(("GET", profile_key, dict(params or {})))
        return {"status_code": 0, "items": [{"id": "1"}], "profile": profile_key}

    async def post(self, profile_key, params=None, **kw):
        self.calls.append(("POST", profile_key, dict(params or {})))
        return {"status_code": 0, "action": profile_key}


START_OK = {
    "status_code": 0,
    "data": {
        "qrcode": "BASE64PNG",
        "qrcode_index_url": "https://www.douyin.com/passport/qrcode/?token=TOKEN123",
        "token": "TOKEN123",
        "web_name": "<PRIVATE_ACCOUNT_NUMBER_b90765981cdba8db>",
        "expire_time": 300,
    },
}


def make_deps(tmp_path, session=True):
    store = SessionStore(tmp_path / "session.bin", protector=PlainProtector())
    if session:
        store.save(
            SessionState(
                cookies={"sessionid": "SESSION_VALUE"},
                created_at=datetime.now(timezone.utc),
                expires_at=datetime.now(timezone.utc) + timedelta(days=1),
                adapter_version="2026.10.17",
                signer="browser",
                status="active",
            )
        )
    return AppDeps(
        session_store=store,
        export_service=ExportService(store, ttl_seconds=120),
        qr_manager=QRLoginManager(FakeHTTP([START_OK])),
        client=FakeClient(),
    )


def build(tmp_path, session=True):
    install_test_api_token()
    deps = make_deps(tmp_path, session=session)
    app = create_app(deps=deps)
    return TestClient(app, headers={"Authorization": f"Bearer {TEST_API_TOKEN}"}), deps


def test_health_ok(tmp_path):
    client, _ = build(tmp_path)
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_openapi_exposes_planned_routes(tmp_path):
    client, _ = build(tmp_path)
    paths = client.get("/openapi.json").json()["paths"]
    expected = {
        "/health",
        "/auth/qr/start",
        "/auth/qr/{qr_id}/status",
        "/auth/qr/{qr_id}/cancel",
        "/auth/session",
        "/auth/session/export",
        "/auth/session/revoke",
        "/api/feed/featured",
        "/api/feed/recommend",
        "/api/feed/following",
        "/api/search",
        "/api/video/{video_id}",
        "/api/video/{video_id}/author",
        "/api/video/{video_id}/media",
        "/api/video/{video_id}/comments",
        "/api/user/{user_id}",
        "/api/user/{user_id}/videos",
        "/api/user/{user_id}/following",
        "/api/user/{user_id}/followers",
        "/api/video/{video_id}/like",
        "/api/video/{video_id}/favorite",
        "/api/video/{video_id}/comment",
        "/api/user/{user_id}/follow",
    }
    assert expected.issubset(set(paths))


def test_qr_start_returns_image(tmp_path):
    client, _ = build(tmp_path)
    r = client.post("/auth/qr/start")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "created"
    assert body["image_base64"] == "BASE64PNG"
    assert body["qr_id"]


def test_session_reports_active_without_leaking_cookie(tmp_path):
    client, _ = build(tmp_path)
    r = client.get("/auth/session")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "active"
    assert "SESSION_VALUE" not in r.text
    assert "cookies" not in body


def test_session_export_returns_cookie_once(tmp_path):
    client, _ = build(tmp_path)
    issued = client.post("/auth/session/export").json()
    assert "ticket" in issued
    first = client.post("/auth/session/export/redeem", json={"ticket": issued["ticket"]})
    assert first.status_code == 200
    assert first.json()["cookies"]["sessionid"] == "SESSION_VALUE"
    second = client.post("/auth/session/export/redeem", json={"ticket": issued["ticket"]})
    assert second.status_code == 403


def test_session_export_requires_active_session(tmp_path):
    client, _ = build(tmp_path, session=False)
    r = client.post("/auth/session/export")
    assert r.status_code == 403


def test_feed_returns_items(tmp_path):
    client, deps = build(tmp_path)
    r = client.get("/api/feed/featured", params={"count": 5})
    assert r.status_code == 200
    assert r.json()["items"][0]["id"] == "1"
    assert deps.client.calls[0][1] == "feed.featured"


def test_write_requires_confirmation(tmp_path):
    client, deps = build(tmp_path)
    r = client.post("/api/video/123/like", json={"dry_run": False, "confirm": False})
    assert r.status_code == 409
    assert r.json()["detail"]["code"] == "CONFIRM_REQUIRED"
    assert deps.client.calls == []


def test_write_dry_run_does_not_call_upstream(tmp_path):
    client, deps = build(tmp_path)
    r = client.post("/api/video/123/like", json={"dry_run": True})
    assert r.status_code == 200
    assert r.json()["dry_run"] is True
    assert deps.client.calls == []


def test_write_confirmed_calls_upstream(tmp_path):
    client, deps = build(tmp_path)
    r = client.post(
        "/api/video/123/like",
        json={"dry_run": False, "confirm": True, "idempotency_key": "k1"},
    )
    assert r.status_code == 200
    assert deps.client.calls[0][1] == "social.digg"


def test_write_idempotent_replay_is_cached(tmp_path):
    client, deps = build(tmp_path)
    payload = {"dry_run": False, "confirm": True, "idempotency_key": "same-key"}
    client.post("/api/video/123/like", json=payload)
    client.post("/api/video/123/like", json=payload)
    assert len(deps.client.calls) == 1


def test_missing_session_blocks_content_api(tmp_path):
    client, _ = build(tmp_path, session=False)
    r = client.get("/api/feed/featured")
    assert r.status_code == 401
    assert r.json()["detail"]["code"] == "SESSION_MISSING"



