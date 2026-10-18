from __future__ import annotations

import base64
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response

from douyin_api.auth.session import SessionState
from douyin_api.models import QRStartResponse, QRStateResponse, RedeemRequest

router = APIRouter(prefix="/auth", tags=["auth"])

CONFIRMED = "confirmed"


async def _adopt_if_confirmed(request: Request, qr_id: str, state) -> None:
    """Persist cookies exactly once, right after the QR is confirmed."""
    if state.status.value != CONFIRMED:
        return
    deps = request.app.state.deps
    if deps.session_store.status() == "active":
        return
    collect = getattr(deps.qr_manager, "collect_cookies", None)
    if collect is None:
        return
    try:
        cookies = await collect(qr_id)
    except (KeyError, PermissionError):
        return
    if not cookies:
        return
    deps.session_store.save(
        SessionState(
            cookies=cookies,
            created_at=datetime.now(timezone.utc),
            expires_at=datetime.now(timezone.utc) + timedelta(days=30),
            adapter_version=deps.extra.get("adapter_version", "2026.10.17"),
            signer=deps.extra.get("signer", "browser"),
        )
    )


@router.post("/qr/start", response_model=QRStartResponse)
async def qr_start(request: Request) -> QRStartResponse:
    deps = request.app.state.deps
    try:
        start = await deps.qr_manager.start()
    except Exception as exc:
        raise HTTPException(status_code=502, detail={"code": "QR_START_FAILED", "message": str(exc)[:300]})
    return QRStartResponse(**start.model_dump())


@router.get("/qr/{qr_id}/status", response_model=QRStateResponse)
async def qr_status(request: Request, qr_id: str) -> QRStateResponse:
    deps = request.app.state.deps
    try:
        state = await deps.qr_manager.poll(qr_id)
    except KeyError:
        raise HTTPException(status_code=404, detail={"code": "QR_NOT_FOUND"})
    except Exception as exc:
        raise HTTPException(status_code=502, detail={"code": "QR_POLL_FAILED", "message": str(exc)[:300]})
    await _adopt_if_confirmed(request, qr_id, state)
    return QRStateResponse(**state.model_dump())


@router.get("/qr/{qr_id}/image", response_class=Response)
async def qr_image(request: Request, qr_id: str) -> Response:
    """Return the QR as a real PNG so any client can render it."""
    deps = request.app.state.deps
    records = getattr(deps.qr_manager, "_records", {})
    record = records.get(qr_id)
    if record is None:
        raise HTTPException(status_code=404, detail={"code": "QR_NOT_FOUND"})
    image = getattr(record, "image_base64", None) or getattr(record, "image", None)
    if not image:
        raise HTTPException(status_code=409, detail={"code": "QR_IMAGE_UNAVAILABLE"})
    return Response(content=base64.b64decode(image), media_type="image/png")


@router.post("/qr/{qr_id}/cancel", response_model=QRStateResponse)
async def qr_cancel(request: Request, qr_id: str) -> QRStateResponse:
    deps = request.app.state.deps
    try:
        state = await deps.qr_manager.cancel(qr_id)
    except KeyError:
        raise HTTPException(status_code=404, detail={"code": "QR_NOT_FOUND"})
    return QRStateResponse(**state.model_dump())


@router.get("/session")
async def session_summary(request: Request) -> dict:
    deps = request.app.state.deps
    return deps.session_store.summary()


@router.post("/session/export")
async def session_export(request: Request) -> dict:
    deps = request.app.state.deps
    try:
        ticket = deps.export_service.issue()
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail={"code": "NO_ACTIVE_SESSION", "message": str(exc)})
    return ticket.model_dump(mode="json")


@router.post("/session/export/redeem")
async def session_export_redeem(request: Request, body: RedeemRequest) -> dict:
    deps = request.app.state.deps
    try:
        cookies = deps.export_service.redeem(body.ticket)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail={"code": "EXPORT_DENIED", "message": str(exc)})
    return {"cookies": cookies}


@router.post("/session/revoke")
async def session_revoke(request: Request) -> dict:
    deps = request.app.state.deps
    deps.export_service.invalidate_all()
    deps.session_store.revoke()
    return {"status": "revoked"}
