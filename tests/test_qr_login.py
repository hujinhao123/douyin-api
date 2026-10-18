from __future__ import annotations

import pytest

from douyin_api.auth.qr_login import QRLoginManager, QRStatus


class FakeHTTP:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    async def get_json(self, path, params=None, headers=None):
        self.calls.append((path, dict(params or {})))
        if not self.responses:
            raise AssertionError("no more canned responses")
        item = self.responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


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


async def test_start_returns_qr_payload():
    mgr = QRLoginManager(FakeHTTP([START_OK]))
    start = await mgr.start()
    assert start.qr_id
    assert start.image_base64 == "BASE64PNG"
    assert start.status == QRStatus.CREATED
    assert start.expires_in_seconds == 300
    assert start.poll_interval_seconds >= 1


async def test_status_created_then_scanned_then_confirmed():
    http = FakeHTTP(
        [
            START_OK,
            {"data": {"status": 1}},
            {"data": {"status": 2}},
            {"data": {"status": 3, "redirect_url": "https://www.douyin.com/?x=1"}},
        ]
    )
    mgr = QRLoginManager(http)
    start = await mgr.start()
    assert (await mgr.poll(start.qr_id)).status == QRStatus.CREATED
    assert (await mgr.poll(start.qr_id)).status == QRStatus.SCANNED
    confirmed = await mgr.poll(start.qr_id)
    assert confirmed.status == QRStatus.CONFIRMED
    assert confirmed.redirect_url.endswith("?x=1")


async def test_cancel_marks_cancelled_and_stops_polling():
    http = FakeHTTP([START_OK])
    mgr = QRLoginManager(http)
    start = await mgr.start()
    state = await mgr.cancel(start.qr_id)
    assert state.status == QRStatus.CANCELLED
    with pytest.raises(KeyError):
        await mgr.poll(start.qr_id)


async def test_unknown_qr_id_raises_keyerror():
    mgr = QRLoginManager(FakeHTTP([START_OK]))
    with pytest.raises(KeyError):
        await mgr.poll("does-not-exist")


async def test_expired_token_maps_to_expired():
    http = FakeHTTP([START_OK, {"data": {"status": 4}}])
    mgr = QRLoginManager(http)
    start = await mgr.start()
    assert (await mgr.poll(start.qr_id)).status == QRStatus.EXPIRED


async def test_transport_error_maps_to_failed():
    http = FakeHTTP([START_OK, RuntimeError("boom")])
    mgr = QRLoginManager(http)
    start = await mgr.start()
    assert (await mgr.poll(start.qr_id)).status == QRStatus.FAILED
