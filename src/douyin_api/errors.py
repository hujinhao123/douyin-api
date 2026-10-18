"""Typed errors shared by transport, adapters and the HTTP layer."""

from __future__ import annotations

from typing import Any


class DouyinApiError(Exception):
    """A failure that maps to a documented API error code."""

    def __init__(self, code: str, message: str, *, status: int = 502, detail: Any = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status
        self.detail = detail

    def payload(self) -> dict[str, Any]:
        body: dict[str, Any] = {"code": self.code, "message": self.message}
        if self.detail is not None:
            body["detail"] = self.detail
        return body


class SessionMissing(DouyinApiError):
    def __init__(self, message: str = "no active <PRIVATE_ACCOUNT_NUMBER_b90765981cdba8db> session; run QR login first"):
        super().__init__("SESSION_MISSING", message, status=401)


class SessionExpired(DouyinApiError):
    def __init__(self, message: str = "session rejected by upstream; re-run QR login"):
        super().__init__("SESSION_EXPIRED", message, status=401)


class ConfirmRequired(DouyinApiError):
    def __init__(self, message: str = "write action requires confirm=true"):
        super().__init__("CONFIRM_REQUIRED", message, status=409)


class RateLimited(DouyinApiError):
    def __init__(self, message: str = "upstream rate limited the request"):
        super().__init__("RATE_LIMITED", message, status=429)


class FieldChanged(DouyinApiError):
    def __init__(self, message: str = "response shape changed; adapter needs refresh"):
        super().__init__("FIELD_CHANGED", message, status=502)


class Blocked(DouyinApiError):
    def __init__(self, message: str = "upstream blocked the request"):
        super().__init__("BLOCKED", message, status=403)


class PrivacyHidden(DouyinApiError):
    def __init__(self, message: str = "hidden by the user's privacy settings"):
        super().__init__("PRIVACY_HIDDEN", message, status=403)


class BadParams(DouyinApiError):
    def __init__(self, message: str = "upstream rejected required parameters"):
        super().__init__("BAD_PARAMS", message, status=400)


class UpstreamError(DouyinApiError):
    def __init__(self, message: str = "upstream error"):
        super().__init__("UPSTREAM_ERROR", message, status=502)