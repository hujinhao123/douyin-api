"""Import an existing browser login into the local session store.

Why this exists: the QR bridge covers the normal path, but sometimes you already
have a logged-in browser and re-scanning is pointless. This endpoint lets a page
you control hand its own cookies to the local service.

Safety rails (all required):
  * disabled unless DOUYIN_IMPORT_TOKEN is set
  * request must come from 127.0.0.1 / ::1
  * must present X-Import-Token matching the env value (constant-time compare)
  * single use: the token is burned after a successful import
  * cookie values are never logged
"""

from __future__ import annotations

import hmac
import json
import os
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from douyin_api.auth.session import SessionState

router = APIRouter(prefix="/auth/session", tags=["auth"])

# "testclient" only appears through the in-process ASGI transport, never over a socket.
_LOOPBACK = {"127.0.0.1", "::1", "localhost", "testclient"}
_burned = False


class ImportRequest(BaseModel):
    cookies: dict[str, str]


def _reset_for_tests() -> None:
    global _burned
    _burned = False


async def _read_body(request: Request) -> dict:
    """Accept application/json or text/plain (text/plain avoids a CORS preflight,
    so a page can hand over its own cookies without extra CORS configuration)."""
    raw = await request.body()
    if not raw:
        return {}
    try:
        return json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return {}


@router.post("/import")
async def import_session(request: Request) -> dict:
    global _burned

    expected = os.environ.get("DOUYIN_IMPORT_TOKEN")
    if not expected:
        raise HTTPException(status_code=404, detail={"code": "IMPORT_DISABLED"})

    client_host = request.client.host if request.client else ""
    if client_host not in _LOOPBACK:
        raise HTTPException(status_code=403, detail={"code": "LOOPBACK_ONLY"})

    supplied = request.headers.get("x-import-token", "")
    if not hmac.compare_digest(supplied, expected):
        raise HTTPException(status_code=403, detail={"code": "IMPORT_TOKEN_INVALID"})

    if _burned:
        raise HTTPException(status_code=409, detail={"code": "IMPORT_TOKEN_USED"})

    payload = await _read_body(request)
    raw_cookies = payload.get("cookies") if isinstance(payload, dict) else None
    if not isinstance(raw_cookies, dict):
        raise HTTPException(status_code=400, detail={"code": "COOKIES_REQUIRED"})
    cookies = {str(k): str(v) for k, v in raw_cookies.items() if k and v}
    if not any(k in cookies for k in ("sessionid", "sessionid_ss", "sid_tt")):
        raise HTTPException(status_code=400, detail={"code": "NO_SESSION_COOKIE"})

    deps = request.app.state.deps
    deps.session_store.save(
        SessionState(
            cookies=cookies,
            created_at=datetime.now(timezone.utc),
            expires_at=datetime.now(timezone.utc) + timedelta(days=30),
            adapter_version=deps.extra.get("adapter_version", "2026.10.17"),
            signer=deps.extra.get("signer", "browser"),
        )
    )
    _burned = True
    return {"status": "imported", "cookie_count": len(cookies), "session": deps.session_store.status()}
