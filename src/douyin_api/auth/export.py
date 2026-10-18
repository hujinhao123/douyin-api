"""One-time, audited cookie export tickets."""

from __future__ import annotations

import secrets
import time
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel

from douyin_api.auth.session import SessionStore


class ExportTicket(BaseModel):
    ticket: str
    issued_at: datetime
    expires_at: datetime


class ExportService:
    """Issues single-use tickets; the raw cookie is only returned once."""

    def __init__(self, store: SessionStore, ttl_seconds: int = 120):
        self.store = store
        self.ttl_seconds = ttl_seconds
        self._tickets: dict[str, float] = {}

    def issue(self) -> ExportTicket:
        if self.store.status() != "active":
            raise PermissionError("no active session")
        self._purge()
        ticket = secrets.token_urlsafe(24)
        expires = time.time() + self.ttl_seconds
        self._tickets[ticket] = expires
        return ExportTicket(
            ticket=ticket,
            issued_at=datetime.now(timezone.utc),
            expires_at=datetime.fromtimestamp(expires, tz=timezone.utc),
        )

    def redeem(self, ticket: str) -> dict[str, Any]:
        expires = self._tickets.pop(ticket, None)
        if expires is None:
            raise PermissionError("unknown or already used export ticket")
        if expires < time.time():
            raise PermissionError("export ticket expired")
        if self.store.status() != "active":
            raise PermissionError("no active session")
        state = self.store.load()
        if state is None:
            raise PermissionError("no active session")
        return dict(state.cookies)

    def invalidate_all(self) -> None:
        self._tickets.clear()

    def _purge(self) -> None:
        now = time.time()
        for key in [k for k, v in self._tickets.items() if v < now]:
            self._tickets.pop(key, None)