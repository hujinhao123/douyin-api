"""QR login state machine for the <PRIVATE_ACCOUNT_NUMBER_b90765981cdba8db> web passport flow."""

from __future__ import annotations

import base64
import io
import time
import uuid
from enum import Enum
from typing import Any, Protocol

from pydantic import BaseModel, Field

QRCODE_PATH = "/passport/web/get_qrcode/"
CHECK_PATH = "/passport/web/check_qrconnect/"

QRCODE_PARAMS: dict[str, Any] = {
    "next": "https://www.douyin.com/",
    "need_logo": "false",
    "need_short_url": "true",
    "aid": 6383,
    "account_sdk_source": "web",
    "sdk_version": "2.2.4",
    "language": "zh",
}


class QRStatus(str, Enum):
    CREATED = "created"
    SCANNED = "scanned"
    CONFIRMED = "confirmed"
    EXPIRED = "expired"
    CANCELLED = "cancelled"
    FAILED = "failed"


TERMINAL = {QRStatus.CONFIRMED, QRStatus.EXPIRED, QRStatus.CANCELLED, QRStatus.FAILED}

# Upstream check_qrconnect status codes.
STATUS_MAP = {
    0: QRStatus.CREATED,
    1: QRStatus.CREATED,
    2: QRStatus.SCANNED,
    3: QRStatus.CONFIRMED,
    4: QRStatus.EXPIRED,
    5: QRStatus.EXPIRED,
}


class QRStart(BaseModel):
    qr_id: str
    image_base64: str
    qr_url: str
    status: QRStatus
    expires_in_seconds: int
    poll_interval_seconds: int = 2


class QRState(BaseModel):
    qr_id: str
    status: QRStatus
    redirect_url: str | None = None
    message: str | None = None


class JsonHTTP(Protocol):
    async def get_json(self, path: str, params: dict[str, Any] | None = None, headers: dict[str, str] | None = None) -> dict[str, Any]: ...


class _Record:
    __slots__ = ("token", "expires_at", "status", "redirect_url")

    def __init__(self, token: str, expires_at: float):
        self.token = token
        self.expires_at = expires_at
        self.status = QRStatus.CREATED
        self.redirect_url: str | None = None


def _render_qr_png(url: str) -> str:
    """Render the qr URL locally when upstream returns no image payload."""
    import qrcode  # imported lazily so the core has no hard dependency at import time

    img = qrcode.make(url)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("ascii")


class QRLoginManager:
    """Tracks pending QR logins; one manager per process."""

    def __init__(self, http: JsonHTTP, *, clock=time.time):
        self.http = http
        self.clock = clock
        self._records: dict[str, _Record] = {}

    async def start(self) -> QRStart:
        payload = await self.http.get_json(QRCODE_PATH, QRCODE_PARAMS)
        data = payload.get("data") or {}
        token = data.get("token") or ""
        if not token:
            raise ValueError("get_qrcode returned no token")
        qr_url = data.get("qrcode_index_url") or data.get("qrcode_url") or ""
        image = data.get("qrcode") or ""
        if not image and qr_url:
            image = _render_qr_png(qr_url)
        expire = int(data.get("expire_time") or 300)
        qr_id = uuid.uuid4().hex
        self._records[qr_id] = _Record(token, self.clock() + expire)
        return QRStart(
            qr_id=qr_id,
            image_base64=image,
            qr_url=qr_url,
            status=QRStatus.CREATED,
            expires_in_seconds=expire,
        )

    async def poll(self, qr_id: str) -> QRState:
        record = self._records[qr_id]
        if record.status in TERMINAL:
            return QRState(qr_id=qr_id, status=record.status, redirect_url=record.redirect_url)
        if self.clock() > record.expires_at:
            record.status = QRStatus.EXPIRED
            return QRState(qr_id=qr_id, status=QRStatus.EXPIRED, message="qr token expired")
        try:
            payload = await self.http.get_json(
                CHECK_PATH,
                {"token": record.token, "aid": 6383, "account_sdk_source": "web"},
            )
        except Exception as exc:  # transport failure is a state, not a crash
            record.status = QRStatus.FAILED
            return QRState(qr_id=qr_id, status=QRStatus.FAILED, message=str(exc))
        data = payload.get("data") or {}
        code = data.get("status")
        status = STATUS_MAP.get(int(code) if isinstance(code, (int, str)) and str(code).isdigit() else -1)
        if status is None:
            record.status = QRStatus.FAILED
            return QRState(qr_id=qr_id, status=QRStatus.FAILED, message=f"unknown status {code!r}")
        record.status = status
        if status == QRStatus.CONFIRMED:
            record.redirect_url = data.get("redirect_url")
        return QRState(qr_id=qr_id, status=status, redirect_url=record.redirect_url)

    async def cancel(self, qr_id: str) -> QRState:
        record = self._records.pop(qr_id)
        record.status = QRStatus.CANCELLED
        return QRState(qr_id=qr_id, status=QRStatus.CANCELLED)

    def pending(self) -> list[str]:
        return list(self._records)