"""API boundary security helpers."""

from __future__ import annotations

import hmac

from fastapi import Request
from fastapi.responses import JSONResponse

PUBLIC_PATHS = {"/health", "/openapi.json", "/docs", "/redoc"}


def install_auth_middleware(app, settings) -> None:
    @app.middleware("http")
    async def require_bearer(request: Request, call_next):
        if request.url.path in PUBLIC_PATHS:
            return await call_next(request)
        if not settings.api_token:
            return JSONResponse(
                status_code=401,
                content={"detail": {"code": "API_TOKEN_MISSING"}},
            )
        supplied = request.headers.get("authorization", "")
        ticket = request.query_params.get("ticket", "")
        if ticket and request.url.path.endswith("/stream"):
            store = getattr(request.app.state, "stream_tickets", None)
            video_id = request.path_params.get("video_id", "")
            if store is not None and store.redeem(video_id, ticket):
                return await call_next(request)
        expected = f"Bearer {settings.api_token}"
        if not hmac.compare_digest(supplied, expected):
            return JSONResponse(
                status_code=401,
                content={"detail": {"code": "API_TOKEN_INVALID"}},
            )
        return await call_next(request)

import base64
import hashlib
import hmac
import secrets
import time


class StreamTicketStore:
    def __init__(self, secret: str, ttl_seconds: int = 300):
        self.secret = secret.encode("utf-8")
        self.ttl_seconds = ttl_seconds
        self._issued: dict[str, tuple[str, float]] = {}

    def _sign(self, video_id: str, nonce: str, expires: int) -> str:
        message = f"{video_id}.{nonce}.{expires}".encode("utf-8")
        return hmac.new(self.secret, message, hashlib.sha256).hexdigest()

    def issue(self, video_id: str) -> str:
        nonce = secrets.token_urlsafe(12)
        expires = int(time.time()) + self.ttl_seconds
        signature = self._sign(video_id, nonce, expires)
        raw = f"{nonce}.{expires}.{signature}".encode("utf-8")
        ticket = base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")
        self._issued[ticket] = (video_id, float(expires))
        return ticket

    def redeem(self, video_id: str, ticket: str) -> bool:
        record = self._issued.pop(ticket, None)
        if record is None:
            return False
        expected_video, expires = record
        if expected_video != video_id or expires < time.time():
            return False
        try:
            padded = ticket + "=" * (-len(ticket) % 4)
            raw = base64.urlsafe_b64decode(padded.encode("ascii")).decode("utf-8")
            nonce, expires_text, signature = raw.split(".", 2)
        except Exception:
            return False
        if int(expires_text) != int(expires):
            return False
        expected = self._sign(video_id, nonce, int(expires_text))
        return hmac.compare_digest(signature, expected)

