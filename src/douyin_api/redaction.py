"""Helpers that keep session material out of logs, docs and fixtures."""

from __future__ import annotations

import logging
from typing import Any, Mapping

SENSITIVE_KEYS = frozenset(
    {
        "sessionid",
        "sessionid_ss",
        "sid_tt",
        "sid_guard",
        "uid_tt",
        "uid_tt_ss",
        "odin_tt",
        "passport_csrf_token",
        "passport_csrf_token_default",
        "ttwid",
        "msToken",
        "ms_token",
        "a_bogus",
        "X-Bogus",
        "x-bogus",
        "cookie",
        "Cookie",
        "authorization",
        "Authorization",
        "ticket",
    }
)

MASK = "***"


def _is_sensitive(key: str) -> bool:
    return key in SENSITIVE_KEYS or key.lower() in {k.lower() for k in SENSITIVE_KEYS}


def redact_mapping(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Return a copy with sensitive values replaced by a mask."""
    out: dict[str, Any] = {}
    for key, value in payload.items():
        if _is_sensitive(key):
            out[key] = MASK
        elif isinstance(value, Mapping):
            out[key] = redact_mapping(value)
        else:
            out[key] = value
    return out


def redact_cookie_string(raw: str) -> str:
    """Keep cookie names, drop every value."""
    parts = []
    for chunk in raw.split(";"):
        chunk = chunk.strip()
        if not chunk:
            continue
        name = chunk.split("=", 1)[0].strip()
        parts.append(f"{name}={MASK}")
    return "; ".join(parts)


class RedactingFilter(logging.Filter):
    """Logging filter that strips cookie/token values from formatted records."""

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            message = record.getMessage()
        except Exception:
            return True
        if "sessionid=" in message or "ttwid=" in message or "msToken=" in message:
            record.msg = redact_cookie_string(message)
            record.args = ()
        return True