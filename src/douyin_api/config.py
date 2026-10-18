"""Runtime settings. Defaults are loopback-only.

Every field can be overridden with an environment variable so the service can be
started from a shortcut, a service wrapper, or a container without editing code.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


def _env_path(name: str) -> Path | None:
    value = os.environ.get(name)
    return Path(value) if value else None


def _env_bool(name: str, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() not in {"0", "false", "no", "off"}


def _default_data_dir() -> Path:
    override = os.environ.get("DOUYIN_API_DATA")
    if override:
        return Path(override)
    base = os.environ.get("LOCALAPPDATA") or str(Path.home())
    return Path(base) / "douyin-api"


@dataclass
class Settings:
    host: str = "127.0.0.1"
    port: int = field(default_factory=lambda: int(os.environ.get("DOUYIN_PORT", "8787")))
    data_dir: Path = field(default_factory=_default_data_dir)
    signer_mode: str = field(default_factory=lambda: os.environ.get("DOUYIN_SIGNER", "browser"))
    login_mode: str = field(default_factory=lambda: os.environ.get("DOUYIN_LOGIN", "page"))
    transport_mode: str = field(default_factory=lambda: os.environ.get("DOUYIN_TRANSPORT", "browser"))
    browser_profile: Path | None = field(default_factory=lambda: _env_path("DOUYIN_BROWSER_PROFILE"))
    browser_cdp: str | None = field(default_factory=lambda: os.environ.get("DOUYIN_BROWSER_CDP") or None)
    browser_executable: Path | None = field(default_factory=lambda: _env_path("DOUYIN_BROWSER_EXECUTABLE"))
    browser_headless: bool = field(default_factory=lambda: _env_bool("DOUYIN_HEADLESS", True))
    signer_bundle: Path | None = field(default_factory=lambda: _env_path("DOUYIN_SIGNER_BUNDLE"))
    request_timeout: float = field(default_factory=lambda: float(os.environ.get("DOUYIN_TIMEOUT", "15")))
    export_ttl_seconds: int = field(default_factory=lambda: int(os.environ.get("DOUYIN_EXPORT_TTL", "120")))
    allow_lan: bool = field(default_factory=lambda: _env_bool("DOUYIN_ALLOW_LAN", False))
    api_token: str = field(default_factory=lambda: os.environ.get("DOUYIN_API_TOKEN", ""))
    master_key_file: Path | None = field(default_factory=lambda: _env_path("DOUYIN_MASTER_KEY_FILE"))

    @property
    def session_path(self) -> Path:
        return self.data_dir / "session.bin"

    @property
    def evidence_dir(self) -> Path:
        return self.data_dir / "evidence"

    def validate(self) -> None:
        if self.allow_lan and len(self.api_token) < 32:
            raise RuntimeError("DOUYIN_ALLOW_LAN requires DOUYIN_API_TOKEN with at least 32 characters")

    def ensure_dirs(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.evidence_dir.mkdir(parents=True, exist_ok=True)




