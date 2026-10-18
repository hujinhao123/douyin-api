from __future__ import annotations

import asyncio
import time
from types import SimpleNamespace

import pytest

from douyin_api.adapters.signature import SignerRegistry
from douyin_api.errors import Blocked, SessionExpired
from douyin_api.transport.client import DouyinClient
from douyin_api.transport.throttle import Throttle


class FakeStore:
    def __init__(self, cookies=None):
        self.cookies = dict(cookies or {"sessionid": "S1"})

    def load(self):
        return SimpleNamespace(cookies=self.cookies)


class FakeSigner:
    def __init__(self, events):
        self.events = events

    async def sign(self, url):
        self.events.append(("sign", time.monotonic()))
        return "signature"


class FakeBrowser:
    def __init__(self, events, envelopes):
        self.events = events
        self.envelopes = list(envelopes)
        self.cookie_installs = 0

    async def set_cookies(self, cookies):
        self.cookie_installs += 1
        self.events.append(("cookies", time.monotonic()))

    async def fetch(self, url, token, *, method="GET", form=None):
        self.events.append(("fetch", time.monotonic()))
        return self.envelopes.pop(0)

    async def close(self):
        pass


@pytest.mark.asyncio
async def test_session_installed_before_sign_and_only_once():
    events = []
    browser = FakeBrowser(events, [
        {"status": 200, "text": '{"status_code":0}', "json": {"status_code": 0}},
        {"status": 200, "text": '{"status_code":0}', "json": {"status_code": 0}},
    ])
    client = DouyinClient(FakeStore(), SignerRegistry().register("fake", FakeSigner(events).sign),
                          browser=browser, throttle=Throttle(min_interval=0, jitter=0))
    await client.get("feed.hot_search")
    await client.get("feed.hot_search")
    assert [e[0] for e in events] == ["cookies", "sign", "fetch", "sign", "fetch"]
    assert browser.cookie_installs == 1
    await client.aclose()


@pytest.mark.asyncio
async def test_forbidden_response_is_not_retried_and_enters_cooldown():
    events = []
    browser = FakeBrowser(events, [
        {"status": 403, "text": "blocked", "json": None},
        {"status": 200, "text": '{"status_code":0}', "json": {"status_code": 0}},
    ])
    throttle = Throttle(min_interval=0, jitter=0, cooldown_base=0.03, cooldown_max=0.03)
    client = DouyinClient(FakeStore(), SignerRegistry().register("fake", FakeSigner(events).sign),
                          browser=browser, throttle=throttle)
    started = time.monotonic()
    with pytest.raises(Blocked):
        await client.get("feed.hot_search")
    assert len([e for e in events if e[0] == "fetch"]) == 1
    assert throttle.cooling_down_for > 0
    await client.get("feed.hot_search")
    assert time.monotonic() - started >= 0.02
    await client.aclose()


@pytest.mark.asyncio
async def test_expired_session_latches_without_more_network_calls():
    events = []
    browser = FakeBrowser(events, [
        {"status": 200, "text": '{"status_code":8}', "json": {"status_code": 8}},
        {"status": 200, "text": '{"status_code":0}', "json": {"status_code": 0}},
    ])
    store = FakeStore()
    client = DouyinClient(store, SignerRegistry().register("fake", FakeSigner(events).sign),
                          browser=browser, throttle=Throttle(min_interval=0, jitter=0))
    with pytest.raises(SessionExpired):
        await client.get("user.self")
    before = len([e for e in events if e[0] == "fetch"])
    with pytest.raises(SessionExpired):
        await client.get("user.self")
    assert len([e for e in events if e[0] == "fetch"]) == before == 1
    store.cookies = {"sessionid": "S2"}
    await client.get("feed.hot_search")
    assert len([e for e in events if e[0] == "fetch"]) == 2
    await client.aclose()


@pytest.mark.asyncio
async def test_concurrent_requests_are_spaced():
    throttle = Throttle(min_interval=0.02, jitter=0)
    events = []

    async def one():
        await throttle.wait()
        events.append(time.monotonic())

    await asyncio.gather(one(), one(), one())
    assert len(events) == 3
    assert min(b - a for a, b in zip(events, events[1:])) >= 0.015
