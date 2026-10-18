"""BrowserTransport contract tests using a fake page/context (no real browser)."""

from __future__ import annotations

import json
import asyncio

import pytest

from douyin_api.transport.browser import BrowserTransport


class FakeContext:
    def __init__(self, jar=None):
        self.jar = list(jar or [])
        self.reloaded = 0

    async def add_cookies(self, cookies):
        self.jar.extend(cookies)

    async def cookies(self, url=None):
        return list(self.jar)


class FakePage:
    def __init__(self, envelopes):
        self.envelopes = list(envelopes)
        self.closed = False
        self.reloads = 0
        self.waits = []

    def is_closed(self):
        return self.closed

    async def reload(self, **kw):
        self.reloads += 1

    async def wait_for_timeout(self, ms):
        self.waits.append(ms)

    async def wait_for_function(self, *a, **kw):
        return None

    async def evaluate(self, script, arg=None):
        if "frontierSign" in script and "location.origin" in script:
            return "warm"
        return self.envelopes.pop(0)


class SlowPage(FakePage):
    def __init__(self, envelopes):
        super().__init__(envelopes)
        self.active = 0
        self.max_active = 0

    async def evaluate(self, script, arg=None):
        self.active += 1
        self.max_active = max(self.max_active, self.active)
        try:
            await asyncio.sleep(0.01)
            return await super().evaluate(script, arg)
        finally:
            self.active -= 1


def build(envelopes, cookies=None):
    bt = BrowserTransport.__new__(BrowserTransport)
    bt.headless = True
    bt.timeout = 5.0
    bt.profile_dir = None
    bt.cdp_url = None
    bt._pw = None
    bt._browser = None
    bt._page = FakePage(envelopes)
    bt._context = FakeContext(cookies)
    import asyncio

    bt._lock = asyncio.Lock()
    bt._cookie_fingerprint = None
    bt._fetch_lock = asyncio.Lock()
    return bt


async def test_fetch_parses_json():
    bt = build([{"status": 200, "contentType": "application/json", "text": '{"a":1}'}])
    out = await bt.fetch("https://x/", "tok")
    assert out["status"] == 200
    assert out["json"] == {"a": 1}


async def test_fetch_serializes_page_evaluations():
    bt = build([{"status": 200, "contentType": "application/json", "text": "{}"}] * 2)
    bt._page = SlowPage([{"status": 200, "contentType": "application/json", "text": "{}"}] * 2)
    await asyncio.gather(bt.fetch("https://x/1"), bt.fetch("https://x/2"))
    assert bt._page.max_active == 1


async def test_fetch_non_json_returns_text():
    bt = build([{"status": 200, "contentType": "text/html", "text": "<html>"}])
    out = await bt.fetch("https://x/")
    assert out["json"] is None
    assert out["text"] == "<html>"


async def test_fetch_error_envelope_raises():
    from douyin_api.adapters.signature import SignError

    bt = build([{"status": 0, "contentType": "", "text": "", "error": "boom"}])
    with pytest.raises(SignError) as exc:
        await bt.fetch("https://x/")
    assert exc.value.code == "TRANSPORT_FAILED"


async def test_argus_403_is_not_retried():
    bt = build(
        [{"status": 403, "contentType": "text/plain", "text": "Blocked by ArgusSecurityPlugin Sign Invalid"}]
    )
    out = await bt.fetch("https://x/", "tok")
    assert out["status"] == 403
    assert out["text"].startswith("Blocked by ArgusSecurityPlugin")
    assert bt._page.waits == []

async def test_set_cookies_reloads_once_per_jar():
    bt = build([])
    await bt.set_cookies({"sessionid": "S"})
    assert bt._page.reloads == 1
    assert any(c["name"] == "sessionid" for c in bt._context.jar)
    # same jar again: no second reload
    await bt.set_cookies({"sessionid": "S"})
    assert bt._page.reloads == 1


async def test_set_cookies_reloads_when_jar_changes():
    bt = build([])
    await bt.set_cookies({"sessionid": "A"})
    await bt.set_cookies({"sessionid": "B"})
    assert bt._page.reloads == 2


async def test_cookies_are_scoped_to_douyin_domain():
    bt = build([])
    await bt.set_cookies({"sessionid": "S"})
    assert bt._context.jar[0]["domain"] == ".douyin.com"
    assert bt._context.jar[0]["path"] == "/"

