from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from douyin_api.auth.export import ExportService
from douyin_api.auth.session import SessionStore
from douyin_api.config import Settings
from douyin_api.deps import AppDeps
from douyin_api.server import create_app
from douyin_api.storage.secrets import PlainProtector


class DummyClient:
    signer = SimpleNamespace(names=[])
    async def aclose(self):
        return None


class DummyQR:
    pass


def make_app(monkeypatch, tmp_path, token: str | None = "x" * 32):
    monkeypatch.setenv("DOUYIN_API_DATA", str(tmp_path))
    if token is None:
        monkeypatch.delenv("DOUYIN_API_TOKEN", raising=False)
    else:
        monkeypatch.setenv("DOUYIN_API_TOKEN", token)
    settings = Settings()
    store = SessionStore(tmp_path / "session.bin", protector=PlainProtector())
    deps = AppDeps(
        session_store=store,
        export_service=ExportService(store),
        qr_manager=DummyQR(),
        client=DummyClient(),
    )
    return create_app(settings, deps=deps)


def test_health_is_public(monkeypatch, tmp_path):
    app = make_app(monkeypatch, tmp_path)
    response = TestClient(app).get("/health")
    assert response.status_code == 200


def test_business_requires_token(monkeypatch, tmp_path):
    app = make_app(monkeypatch, tmp_path)
    response = TestClient(app).get("/api/feed/hot-search")
    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "API_TOKEN_INVALID"


def test_business_rejects_wrong_token(monkeypatch, tmp_path):
    app = make_app(monkeypatch, tmp_path)
    response = TestClient(app).get(
        "/api/feed/hot-search",
        headers={"Authorization": "Bearer wrong"},
    )
    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "API_TOKEN_INVALID"


def test_lan_without_strong_token_fails(monkeypatch, tmp_path):
    monkeypatch.setenv("DOUYIN_API_DATA", str(tmp_path))
    monkeypatch.setenv("DOUYIN_ALLOW_LAN", "true")
    monkeypatch.setenv("DOUYIN_API_TOKEN", "short")
    with pytest.raises(RuntimeError, match="at least 32"):
        Settings().validate()


def test_token_is_required_even_on_loopback(monkeypatch, tmp_path):
    app = make_app(monkeypatch, tmp_path, token=None)
    response = TestClient(app).get("/api/feed/hot-search")
    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "API_TOKEN_MISSING"
