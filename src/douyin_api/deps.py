"""Composition root: everything the HTTP layer needs, injectable for tests."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from fastapi import HTTPException

from douyin_api.auth.export import ExportService
from douyin_api.auth.qr_login import QRLoginManager
from douyin_api.auth.session import SessionStore
from douyin_api.models import WriteRequest


def require_active(store: SessionStore) -> None:
    status = store.status()
    if status != "active":
        raise HTTPException(
            status_code=401,
            detail={"code": "SESSION_MISSING" if status == "missing" else "SESSION_EXPIRED", "session_status": status},
        )


class WriteCoordinator:
    """Dry-run by default, explicit confirm, idempotent replay."""

    def __init__(self, client: Any):
        self.client = client
        self._cache: dict[str, dict[str, Any]] = {}

    async def execute(
        self,
        profile_key: str,
        params: dict[str, Any],
        body: WriteRequest,
        *,
        form: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if body.dry_run:
            return {
                "dry_run": True,
                "action": profile_key,
                "params": params,
                "form": form or {},
                "replayed": False,
            }
        if not body.confirm:
            raise HTTPException(
                status_code=409,
                detail={"code": "CONFIRM_REQUIRED", "action": profile_key, "params": params},
            )
        key = body.idempotency_key
        if key and key in self._cache:
            return {**self._cache[key], "replayed": True}
        result = await self.client.post(profile_key, params, form=form)
        payload = {
            "dry_run": False,
            "action": profile_key,
            "params": params,
            "form": form or {},
            "result": result,
            "replayed": False,
        }
        if key:
            self._cache[key] = payload
        return payload


@dataclass
class AppDeps:
    session_store: SessionStore
    export_service: ExportService
    qr_manager: QRLoginManager
    client: Any
    writer: WriteCoordinator | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    def ensure_writer(self) -> WriteCoordinator:
        if self.writer is None:
            self.writer = WriteCoordinator(self.client)
        return self.writer
