from __future__ import annotations

import pytest

from douyin_api.adapters.request_profile import COMMON_PARAMS, PROFILES, build_query
from douyin_api.adapters.signature import SignError, SignerRegistry, StaticSigner
from douyin_api.adapters.versioning import detect_version
from douyin_api.transport.retry import ErrorKind, classify_response, should_retry


def test_build_query_merges_common_params_and_drops_empty():
    q = build_query({"aweme_id": "123", "cursor": 0, "empty": None, "blank": ""})
    assert q["aweme_id"] == "123"
    assert q["cursor"] == 0
    assert "empty" not in q
    assert "blank" not in q
    for key in ("device_platform", "aid", "channel", "version_code", "browser_language"):
        assert q[key] == COMMON_PARAMS[key]


def test_build_query_never_leaks_unknown_common_keys():
    q = build_query({})
    assert set(q) == set(COMMON_PARAMS)


def test_profiles_cover_documented_endpoints():
    required = {
        "feed.featured",
        "feed.recommend",
        "feed.following",
        "search.general",
        "video.detail",
        "video.comments",
        "video.media",
        "user.profile",
        "user.posts",
        "user.following",
        "user.followers",
        "social.digg",
        "social.favorite",
        "social.follow",
        "social.comment",
    }
    assert required.issubset(PROFILES)


def test_classify_rate_limited():
    assert classify_response(429, b"", None) is ErrorKind.RATE_LIMITED


def test_classify_empty_body_is_field_changed():
    assert classify_response(200, b"", None) is ErrorKind.FIELD_CHANGED


def test_classify_non_json_is_field_changed():
    assert classify_response(200, b"<html>blocked</html>", None) is ErrorKind.FIELD_CHANGED


def test_classify_session_expired_by_status_code():
    assert classify_response(200, b"{}", {"status_code": 8}) is ErrorKind.SESSION_EXPIRED


def test_classify_ok_returns_none():
    assert classify_response(200, b"{}", {"status_code": 0}) is None


def test_classify_server_error():
    assert classify_response(503, b"", None) is ErrorKind.UPSTREAM_ERROR


def test_should_retry_only_transient():
    assert should_retry(ErrorKind.RATE_LIMITED) is True
    assert should_retry(ErrorKind.UPSTREAM_ERROR) is True
    assert should_retry(ErrorKind.SESSION_EXPIRED) is False
    assert should_retry(ErrorKind.FIELD_CHANGED) is False


async def test_registry_uses_first_available_signer():
    calls = []

    async def browser_sign(url):
        calls.append(("browser", url))
        return "X-BOGUS-BROWSER"

    async def static_sign(url):
        calls.append(("static", url))
        return "X-BOGUS-STATIC"

    reg = SignerRegistry()
    reg.register("browser", browser_sign)
    reg.register("static", static_sign)
    token = await reg.sign("https://example/?a=1")
    assert token == "X-BOGUS-BROWSER"
    assert calls == [("browser", "https://example/?a=1")]


async def test_registry_falls_back_when_primary_raises():
    async def broken(url):
        raise RuntimeError("browser closed")

    async def static_sign(url):
        return "X-BOGUS-STATIC"

    reg = SignerRegistry()
    reg.register("browser", broken)
    reg.register("static", static_sign)
    assert await reg.sign("https://example/") == "X-BOGUS-STATIC"


async def test_registry_raises_sign_error_when_all_fail():
    async def broken(url):
        raise RuntimeError("nope")

    reg = SignerRegistry()
    reg.register("browser", broken)
    with pytest.raises(SignError) as exc:
        await reg.sign("https://example/")
    assert exc.value.code == "SIGN_FAILED"
    assert "browser" in exc.value.detail


async def test_static_signer_reports_missing_bundle(tmp_path):
    signer = StaticSigner(tmp_path / "missing.js", node_binary="node")
    with pytest.raises(SignError) as exc:
        await signer("https://example/")
    assert exc.value.code == "SIGNER_UNAVAILABLE"


def test_detect_version_from_bundle_names():
    urls = [
        "https://lf-douyin-pc-web.douyinstatic.com/obj/douyin-pc-web/ies/douyin_web/runtime~client-entry.4f889a96.js",
        "https://lf-douyin-pc-web.douyinstatic.com/obj/douyin-pc-web/ies/douyin_web/client-entry~0.33977799.js",
    ]
    v = detect_version(urls)
    assert v.build == "4f889a96"
    assert v.script_count == 2
