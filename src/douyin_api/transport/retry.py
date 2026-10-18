"""Response classification: one place that decides what a failure means."""

from __future__ import annotations

from enum import Enum
from typing import Any


class ErrorKind(str, Enum):
    SESSION_EXPIRED = "SESSION_EXPIRED"
    PRIVACY_HIDDEN = "PRIVACY_HIDDEN"
    BAD_PARAMS = "BAD_PARAMS"
    RATE_LIMITED = "RATE_LIMITED"
    FIELD_CHANGED = "FIELD_CHANGED"
    UPSTREAM_ERROR = "UPSTREAM_ERROR"
    BLOCKED = "BLOCKED"
    SIGN_FAILED = "SIGN_FAILED"


# Verified against live responses on 2026-10-17.
# 8      -> not logged in / token invalid
# 2154   -> login required
# 10232  -> login expired
# 2096   -> "由于该用户隐私设置，列表不可见" (NOT a session problem)
# 5      -> missing required parameter
SESSION_EXPIRED_CODES = {8, 2154, 10232}
PRIVACY_CODES = {2096, 2097}
BAD_PARAM_CODES = {5}

RETRYABLE = {ErrorKind.RATE_LIMITED, ErrorKind.UPSTREAM_ERROR}


def classify_response(status_code: int, body: bytes, json_body: Any) -> ErrorKind | None:
    if status_code == 429:
        return ErrorKind.RATE_LIMITED
    if status_code in (403, 412):
        return ErrorKind.BLOCKED
    if status_code >= 500:
        return ErrorKind.UPSTREAM_ERROR
    if not body:
        return ErrorKind.FIELD_CHANGED
    if json_body is None:
        return ErrorKind.FIELD_CHANGED
    if isinstance(json_body, dict):
        code = json_body.get("status_code")
        if isinstance(code, int):
            if code in SESSION_EXPIRED_CODES:
                return ErrorKind.SESSION_EXPIRED
            if code in PRIVACY_CODES:
                return ErrorKind.PRIVACY_HIDDEN
            if code in BAD_PARAM_CODES:
                return ErrorKind.BAD_PARAMS
    return None


def should_retry(kind: ErrorKind | None) -> bool:
    return kind in RETRYABLE