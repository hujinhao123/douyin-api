"""Settings must honor environment overrides (documented in docs/handoff.md §2.7)."""

from __future__ import annotations

from pathlib import Path

from douyin_api.config import Settings


def test_defaults_are_loopback_only(monkeypatch):
    for name in (
        "DOUYIN_ALLOW_LAN",
        "DOUYIN_BROWSER_CDP",
        "DOUYIN_HEADLESS",
        "DOUYIN_PORT",
        "DOUYIN_LOGIN",
        "DOUYIN_TRANSPORT",
    ):
        monkeypatch.delenv(name, raising=False)
    s = Settings()
    assert s.host == "127.0.0.1"
    assert s.allow_lan is False
    assert s.browser_cdp is None
    assert s.browser_headless is True
    assert s.login_mode == "page"
    assert s.transport_mode == "browser"


def test_cdp_url_from_env(monkeypatch):
    monkeypatch.setenv("DOUYIN_BROWSER_CDP", "http://127.0.0.1:9222")
    assert Settings().browser_cdp == "http://127.0.0.1:9222"


def test_browser_executable_from_env(monkeypatch):
    path = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
    monkeypatch.setenv("DOUYIN_BROWSER_EXECUTABLE", path)
    assert str(Settings().browser_executable) == path


def test_headless_flag_accepts_common_false_spellings(monkeypatch):
    for value in ("0", "false", "no", "off", "FALSE"):
        monkeypatch.setenv("DOUYIN_HEADLESS", value)
        assert Settings().browser_headless is False, value
    monkeypatch.setenv("DOUYIN_HEADLESS", "1")
    assert Settings().browser_headless is True


def test_data_dir_and_session_path(monkeypatch, tmp_path):
    monkeypatch.setenv("DOUYIN_API_DATA", str(tmp_path))
    s = Settings()
    assert s.data_dir == tmp_path
    assert s.session_path == tmp_path / "session.bin"
    s.ensure_dirs()
    assert (tmp_path / "evidence").is_dir()


def test_port_and_ttl_are_ints(monkeypatch):
    monkeypatch.setenv("DOUYIN_PORT", "9999")
    monkeypatch.setenv("DOUYIN_EXPORT_TTL", "30")
    s = Settings()
    assert s.port == 9999
    assert s.export_ttl_seconds == 30


def test_allow_lan_requires_explicit_opt_in(monkeypatch):
    monkeypatch.setenv("DOUYIN_ALLOW_LAN", "true")
    assert Settings().allow_lan is True
    monkeypatch.setenv("DOUYIN_ALLOW_LAN", "false")
    assert Settings().allow_lan is False
