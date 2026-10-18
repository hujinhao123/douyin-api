"""Tests for the guarded session-import endpoint."""

from __future__ import annotations

from _auth_test_helpers import TEST_API_TOKEN, install_test_api_token

import importlib

import pytest
from fastapi.testclient import TestClient

from douyin_api.auth.export import ExportService
from douyin_api.auth.qr_login import QRLoginManager
from douyin_api.auth.session import SessionStore
from douyin_api.endpoints import session_import
from douyin_api.server import AppDeps, create_app
from douyin_api.storage.secrets import PlainProtector


class NoopHTTP:
    async def get_json(self, path, params=None, headers=None):
        return {"data": {"token": "t", "qrcode": "q", "expire_time": 60}}


def make_client(tmp_path, monkeypatch, token="secret-token"):
    install_test_api_token()
    if token is None:
        monkeypatch.delenv("DOUYIN_IMPORT_TOKEN", raising=False)
    else:
        monkeypatch.setenv("DOUYIN_IMPORT_TOKEN", token)
    session_import._reset_for_tests()
    store = SessionStore(tmp_path / "session.bin", protector=PlainProtector())
    deps = AppDeps(
        session_store=store,
        export_service=ExportService(store),
        qr_manager=QRLoginManager(NoopHTTP()),
        client=object(),
    )
    return TestClient(create_app(deps=deps), headers={"Authorization": f"Bearer {TEST_API_TOKEN}"}), store


def test_import_disabled_without_env(tmp_path, monkeypatch):
    client, _ = make_client(tmp_path, monkeypatch, token=None)
    r = client.post("/auth/session/import", json={"cookies": {"sessionid": "S"}})
    assert r.status_code == 404
    assert r.json()["detail"]["code"] == "IMPORT_DISABLED"


def test_import_rejects_wrong_token(tmp_path, monkeypatch):
    client, _ = make_client(tmp_path, monkeypatch)
    r = client.post(
        "/auth/session/import",
        json={"cookies": {"sessionid": "S"}},
        headers={"X-Import-Token": "wrong"},
    )
    assert r.status_code == 403
    assert r.json()["detail"]["code"] == "IMPORT_TOKEN_INVALID"


def test_import_rejects_missing_session_cookie(tmp_path, monkeypatch):
    client, _ = make_client(tmp_path, monkeypatch)
    r = client.post(
        "/auth/session/import",
        json={"cookies": {"ttwid": "T"}},
        headers={"X-Import-Token": "secret-token"},
    )
    assert r.status_code == 400
    assert r.json()["detail"]["code"] == "NO_SESSION_COOKIE"


def test_import_stores_session_once(tmp_path, monkeypatch):
    client, store = make_client(tmp_path, monkeypatch)
    r = client.post(
        "/auth/session/import",
        json={"cookies": {"sessionid": "S", "ttwid": "T"}},
        headers={"X-Import-Token": "secret-token"},
    )
    assert r.status_code == 200
    assert r.json()["status"] == "imported"
    assert r.json()["cookie_count"] == 2
    assert store.status() == "active"
    assert store.load().cookies["sessionid"] == "S"


def test_import_token_is_single_use(tmp_path, monkeypatch):
    client, _ = make_client(tmp_path, monkeypatch)
    payload = {"cookies": {"sessionid": "S"}}
    headers = {"X-Import-Token": "secret-token"}
    assert client.post("/auth/session/import", json=payload, headers=headers).status_code == 200
    second = client.post("/auth/session/import", json=payload, headers=headers)
    assert second.status_code == 409
    assert second.json()["detail"]["code"] == "IMPORT_TOKEN_USED"


def test_imported_session_never_echoes_cookie(tmp_path, monkeypatch):
    client, _ = make_client(tmp_path, monkeypatch)
    r = client.post(
        "/auth/session/import",
        json={"cookies": {"sessionid": "VERY-SECRET-VALUE"}},
        headers={"X-Import-Token": "secret-token"},
    )
    assert "VERY-SECRET-VALUE" not in r.text



