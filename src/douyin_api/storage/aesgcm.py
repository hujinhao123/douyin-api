"""AES-GCM protection for session files on non-Windows hosts."""

from __future__ import annotations

import base64
import os
from pathlib import Path

from cryptography.hazmat.primitives.ciphers.aead import AESGCM


class AesGcmProtector:
    PREFIX = "AESGCM1:"
    KEY_BYTES = 32
    NONCE_BYTES = 12

    def __init__(self, key_path: Path):
        self.key_path = Path(key_path)
        self._key = self._load_or_create_key()

    def _load_or_create_key(self) -> bytes:
        if self.key_path.exists():
            key = self.key_path.read_bytes()
            if len(key) != self.KEY_BYTES:
                raise ValueError("AES-GCM master key must be exactly 32 bytes")
            return key
        self.key_path.parent.mkdir(parents=True, exist_ok=True)
        key = os.urandom(self.KEY_BYTES)
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        try:
            fd = os.open(self.key_path, flags, 0o600)
        except FileExistsError:
            return self._load_or_create_key()
        with os.fdopen(fd, "wb") as handle:
            handle.write(key)
        try:
            os.chmod(self.key_path, 0o600)
        except OSError:
            pass
        return key

    def protect(self, data: bytes) -> str:
        nonce = os.urandom(self.NONCE_BYTES)
        sealed = AESGCM(self._key).encrypt(nonce, data, None)
        payload = base64.b64encode(nonce + sealed).decode("ascii")
        return self.PREFIX + payload

    def unprotect(self, token: str) -> bytes:
        if not token.startswith(self.PREFIX):
            raise ValueError("token is not AES-GCM sealed")
        raw = base64.b64decode(token[len(self.PREFIX) :])
        if len(raw) <= self.NONCE_BYTES:
            raise ValueError("AES-GCM token is truncated")
        nonce, sealed = raw[: self.NONCE_BYTES], raw[self.NONCE_BYTES :]
        return AESGCM(self._key).decrypt(nonce, sealed, None)
