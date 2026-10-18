"""At-rest protection for the local session file.

On Windows the payload is sealed with DPAPI (current-user scope) so the
session file is not readable by another account or after being copied to a
different machine. Other platforms fall back to base64 with a warning.
"""

from __future__ import annotations

import base64
import ctypes
import sys
from ctypes import wintypes
from pathlib import Path
from typing import Protocol

from douyin_api.storage.aesgcm import AesGcmProtector


class Protector(Protocol):
    def protect(self, data: bytes) -> str: ...
    def unprotect(self, token: str) -> bytes: ...


class PlainProtector:
    """Reversible encoding used for tests and non-Windows hosts."""

    def __init__(self, prefix: str = ""):
        self.prefix = prefix

    def protect(self, data: bytes) -> str:
        return self.prefix + base64.b64encode(data).decode("ascii")

    def unprotect(self, token: str) -> bytes:
        if self.prefix and not token.startswith(self.prefix):
            raise ValueError("token prefix mismatch")
        raw = token[len(self.prefix) :] if self.prefix else token
        return base64.b64decode(raw.encode("ascii"))


class _DataBlob(ctypes.Structure):
    _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]


def _blob(data: bytes) -> _DataBlob:
    buf = ctypes.create_string_buffer(data, len(data))
    return _DataBlob(len(data), ctypes.cast(buf, ctypes.POINTER(ctypes.c_char)))


class DpapiProtector:
    """Windows DPAPI wrapper (current user scope)."""

    PREFIX = "DPAPI1:"
    CRYPTPROTECT_UI_FORBIDDEN = 0x1

    def protect(self, data: bytes) -> str:
        blob_in = _blob(data)
        blob_out = _DataBlob()
        ok = ctypes.windll.crypt32.CryptProtectData(
            ctypes.byref(blob_in),
            None,
            None,
            None,
            None,
            self.CRYPTPROTECT_UI_FORBIDDEN,
            ctypes.byref(blob_out),
        )
        if not ok:
            raise OSError(ctypes.GetLastError(), "CryptProtectData failed")
        try:
            sealed = ctypes.string_at(blob_out.pbData, blob_out.cbData)
        finally:
            ctypes.windll.kernel32.LocalFree(blob_out.pbData)
        return self.PREFIX + base64.b64encode(sealed).decode("ascii")

    def unprotect(self, token: str) -> bytes:
        if not token.startswith(self.PREFIX):
            raise ValueError("token is not DPAPI sealed")
        sealed = base64.b64decode(token[len(self.PREFIX) :])
        blob_in = _blob(sealed)
        blob_out = _DataBlob()
        ok = ctypes.windll.crypt32.CryptUnprotectData(
            ctypes.byref(blob_in),
            None,
            None,
            None,
            None,
            self.CRYPTPROTECT_UI_FORBIDDEN,
            ctypes.byref(blob_out),
        )
        if not ok:
            raise OSError(ctypes.GetLastError(), "CryptUnprotectData failed")
        try:
            return ctypes.string_at(blob_out.pbData, blob_out.cbData)
        finally:
            ctypes.windll.kernel32.LocalFree(blob_out.pbData)


def default_protector(master_key_file: Path | None = None) -> Protector:
    if sys.platform == "win32":
        try:
            probe = DpapiProtector()
            probe.unprotect(probe.protect(b"probe"))
            return probe
        except Exception:
            pass
    if master_key_file is None:
        raise RuntimeError("non-Windows hosts require DOUYIN_MASTER_KEY_FILE")
    return AesGcmProtector(master_key_file)
