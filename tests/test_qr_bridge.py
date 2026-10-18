from __future__ import annotations

import base64

import pytest

from douyin_api.auth.qr_bridge import PageQRBridge
from douyin_api.auth.qr_login import QRStatus


class FakePage:
    def __init__(self, panels, cookies):
        self.panels = list(panels)
        self.cookies = cookies
        self.closed = False
        self.pressed = []

    def is_closed(self):
        return self.closed

    async def evaluate(self, script, *args):
        if "document.querySelector('.douyin_login_new_class')" in script and "!!" in script:
            return self.panels[0].get("present") if self.panels else False
        return self.panels.pop(0) if len(self.panels) > 1 else self.panels[0]

    @property
    def keyboard(self):
        outer = self

        class _Kb:
            async def press(self, key):
                outer.pressed.append(key)

        return _Kb()


class FakeContext:
    def __init__(self, jar):
        self.jar = jar

    async def cookies(self, url=None):
        return [{"name": k, "value": v} for k, v in self.jar.items()]


def build(panels, cookies=None):
    bridge = PageQRBridge.__new__(PageQRBridge)
    bridge.profile_dir = "unused"
    bridge.headless = True
    bridge.timeout = 5.0
    bridge.ttl_seconds = 300
    import time

    bridge.clock = time.time
    bridge._pw = None
    bridge._context = FakeContext(cookies or {})
    bridge._page = FakePage(panels, cookies or {})
    bridge._records = {}
    bridge._lock = __import__("asyncio").Lock()
    return bridge


QR_PANEL = {
    "present": True,
    "qr": "data:image/png;base64," + base64.b64encode(b"PNGDATA").decode(),
    "text": "扫码登录",
}


async def test_start_returns_png_bytes_and_record():
    bridge = build([QR_PANEL])
    start = await bridge.start()
    assert start.image_base64 == base64.b64encode(b"PNGDATA").decode()
    assert start.status == QRStatus.CREATED
    assert start.qr_id in bridge._records


async def test_poll_reports_created_while_waiting():
    bridge = build([QR_PANEL, {"present": True, "qr": None, "text": "扫码登录"}])
    start = await bridge.start()
    state = await bridge.poll(start.qr_id)
    assert state.status == QRStatus.CREATED


async def test_poll_reports_scanned_when_phone_confirms_scan():
    bridge = build([QR_PANEL, {"present": True, "qr": None, "text": "扫码成功 请在手机上确认"}])
    start = await bridge.start()
    state = await bridge.poll(start.qr_id)
    assert state.status == QRStatus.SCANNED


async def test_poll_confirms_when_session_cookie_appears():
    bridge = build(
        [QR_PANEL, {"present": True, "qr": None, "text": "扫码登录"}],
        cookies={"sessionid": "S", "ttwid": "T"},
    )
    start = await bridge.start()
    state = await bridge.poll(start.qr_id)
    assert state.status == QRStatus.CONFIRMED


async def test_poll_cancels_when_modal_closes_without_session():
    bridge = build([QR_PANEL, {"present": False}], cookies={"ttwid": "T"})
    start = await bridge.start()
    state = await bridge.poll(start.qr_id)
    assert state.status == QRStatus.CANCELLED


async def test_expired_record_reports_expired():
    bridge = build([QR_PANEL])
    start = await bridge.start()
    bridge._records[start.qr_id].expires_at = 0
    state = await bridge.poll(start.qr_id)
    assert state.status == QRStatus.EXPIRED


async def test_collect_cookies_requires_session():
    bridge = build([QR_PANEL], cookies={"ttwid": "T"})
    start = await bridge.start()
    with pytest.raises(PermissionError):
        await bridge.collect_cookies(start.qr_id)


async def test_collect_cookies_returns_session_after_confirm():
    bridge = build(
        [QR_PANEL, {"present": True, "qr": None, "text": "扫码登录"}],
        cookies={"sessionid": "S"},
    )
    start = await bridge.start()
    await bridge.poll(start.qr_id)
    cookies = await bridge.collect_cookies(start.qr_id)
    assert cookies["sessionid"] == "S"


async def test_cancel_removes_record_and_presses_escape():
    bridge = build([QR_PANEL])
    start = await bridge.start()
    state = await bridge.cancel(start.qr_id)
    assert state.status == QRStatus.CANCELLED
    assert start.qr_id not in bridge._records
    assert bridge._page.pressed == ["Escape"]
