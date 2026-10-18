"""Local session persistence: one active <PRIVATE_ACCOUNT_NUMBER_b90765981cdba8db> login at a time."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field

from douyin_api.storage.secrets import Protector, default_protector

SessionStatus = Literal["active", "expired", "revoked", "missing"]


class SessionState(BaseModel):
    cookies: dict[str, str] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: datetime | None = None
    adapter_version: str = "unknown"
    signer: str = "unknown"
    status: Literal["active", "revoked"] = "active"
    user: dict[str, Any] | None = None


class SessionStore:
    def __init__(self, path: Path, protector: Protector | None = None):
        self.path = Path(path)
        self.protector = protector or default_protector()
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def _read_raw(self) -> dict[str, Any] | None:
        if not self.path.exists():
            return None
        try:
            token = self.path.read_text(encoding="utf-8").strip()
            return json.loads(self.protector.unprotect(token).decode("utf-8"))
        except Exception:
            return None

    def _write_raw(self, payload: dict[str, Any]) -> None:
        data = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        token = self.protector.protect(data)
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp.write_text(token, encoding="utf-8")
        tmp.replace(self.path)

    def save(self, state: SessionState) -> None:
        self._write_raw(state.model_dump(mode="json"))

    def load(self) -> SessionState | None:
        raw = self._read_raw()
        if not raw:
            return None
        state = SessionState(**raw)
        if state.status != "active":
            return None
        return state

    def status(self) -> SessionStatus:
        raw = self._read_raw()
        if not raw:
            return "missing"
        if raw.get("status") == "revoked":
            return "revoked"
        expires = raw.get("expires_at")
        if expires:
            try:
                if datetime.fromisoformat(expires.replace("Z", "+00:00")) <= datetime.now(timezone.utc):
                    return "expired"
            except ValueError:
                pass
        return "active"

    def revoke(self) -> None:
        self._write_raw({"status": "revoked", "cookies": {}, "revoked_at": datetime.now(timezone.utc).isoformat()})

    def summary(self) -> dict[str, Any]:
        raw = self._read_raw() or {}
        return {
            "status": self.status(),
            "created_at": raw.get("created_at"),
            "expires_at": raw.get("expires_at"),
            "adapter_version": raw.get("adapter_version"),
            "signer": raw.get("signer"),
            "user": raw.get("user"),
            "cookie_names": sorted((raw.get("cookies") or {}).keys()),
        }