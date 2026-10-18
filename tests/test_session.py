from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from douyin_api.auth.export import ExportService
from douyin_api.auth.session import SessionState, SessionStore
from douyin_api.redaction import redact_mapping, redact_cookie_string
from douyin_api.storage.secrets import PlainProtector


def make_state(**over):
    base = dict(
        cookies={"sessionid": "SESSION_VALUE", "ttwid": "TTWID_VALUE"},
        created_at=datetime.now(timezone.utc),
        expires_at=datetime.now(timezone.utc) + timedelta(days=7),
        adapter_version="2026.10.17",
        signer="browser",
        status="active",
    )
    base.update(over)
    return SessionState(**base)


def test_session_roundtrip_persists_cookies(tmp_path):
    store = SessionStore(tmp_path / "session.bin", protector=PlainProtector())
    store.save(make_state())
    loaded = store.load()
    assert loaded is not None
    assert loaded.cookies["sessionid"] == "SESSION_VALUE"
    assert loaded.status == "active"


def test_session_file_does_not_contain_plaintext_cookie(tmp_path):
    path = tmp_path / "session.bin"
    store = SessionStore(path, protector=PlainProtector(prefix="ENC:"))
    store.save(make_state())
    raw = path.read_text(encoding="utf-8")
    assert "SESSION_VALUE" not in raw
    assert raw.startswith("ENC:")


def test_revoke_clears_session_and_marks_status(tmp_path):
    store = SessionStore(tmp_path / "session.bin", protector=PlainProtector())
    store.save(make_state())
    store.revoke()
    assert store.load() is None
    assert store.status() == "revoked"


def test_expired_session_reports_expired(tmp_path):
    store = SessionStore(tmp_path / "session.bin", protector=PlainProtector())
    store.save(make_state(expires_at=datetime.now(timezone.utc) - timedelta(seconds=1)))
    assert store.status() == "expired"


def test_export_ticket_is_single_use(tmp_path):
    store = SessionStore(tmp_path / "session.bin", protector=PlainProtector())
    store.save(make_state())
    svc = ExportService(store, ttl_seconds=60)
    ticket = svc.issue()
    assert ticket.ticket
    first = svc.redeem(ticket.ticket)
    assert first["sessionid"] == "SESSION_VALUE"
    with pytest.raises(PermissionError):
        svc.redeem(ticket.ticket)


def test_export_ticket_invalidated_by_revoke(tmp_path):
    store = SessionStore(tmp_path / "session.bin", protector=PlainProtector())
    store.save(make_state())
    svc = ExportService(store, ttl_seconds=60)
    ticket = svc.issue()
    store.revoke()
    with pytest.raises(PermissionError):
        svc.redeem(ticket.ticket)


def test_export_requires_active_session(tmp_path):
    store = SessionStore(tmp_path / "session.bin", protector=PlainProtector())
    svc = ExportService(store, ttl_seconds=60)
    with pytest.raises(PermissionError):
        svc.issue()


def test_redact_mapping_hides_sensitive_values():
    payload = {"sessionid": "ABC", "msToken": "XYZ", "nickname": "alice"}
    out = redact_mapping(payload)
    assert out["sessionid"] == "***"
    assert out["msToken"] == "***"
    assert out["nickname"] == "alice"


def test_redact_cookie_string_keeps_only_names():
    out = redact_cookie_string("sessionid=ABC; ttwid=DEF; odin_tt=GHI")
    assert "ABC" not in out and "DEF" not in out and "GHI" not in out
    assert "sessionid" in out


def test_aesgcm_roundtrip_and_no_plaintext(tmp_path):
    from douyin_api.storage.aesgcm import AesGcmProtector

    key = tmp_path / "master.key"
    protector = AesGcmProtector(key)
    token = protector.protect(b"sessionid=SECRET")
    assert token.startswith("AESGCM1:")
    assert "SECRET" not in token
    assert protector.unprotect(token) == b"sessionid=SECRET"


def test_aesgcm_wrong_key_fails(tmp_path):
    from douyin_api.storage.aesgcm import AesGcmProtector

    first = AesGcmProtector(tmp_path / "one.key")
    token = first.protect(b"secret")
    second = AesGcmProtector(tmp_path / "two.key")
    with pytest.raises(Exception):
        second.unprotect(token)
