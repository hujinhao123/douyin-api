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
        expected = f"Bearer {settings.api_token}"
        if not hmac.compare_digest(supplied, expected):
            return JSONResponse(
                status_code=401,
                content={"detail": {"code": "API_TOKEN_INVALID"}},
            )
        return await call_next(request)
