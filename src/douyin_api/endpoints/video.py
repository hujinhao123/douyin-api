from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from douyin_api.adapters.page import normalize_aweme, normalize_comment, normalize_user, pick_list
from douyin_api.adapters.request_profile import PROFILES
from douyin_api.deps import require_active
from douyin_api.models import CommentResponse

router = APIRouter(prefix="/api/video", tags=["video"])


def _detail(payload: dict) -> dict:
    detail = payload.get("aweme_detail") or payload.get("aweme") or {}
    if not detail:
        raise HTTPException(status_code=404, detail={"code": "VIDEO_NOT_FOUND"})
    return detail


@router.get("/{video_id}")
async def video_detail(request: Request, video_id: str) -> dict:
    deps = request.app.state.deps
    require_active(deps.session_store)
    data = await deps.client.get("video.detail", {"aweme_id": video_id})
    return {"video": normalize_aweme(_detail(data))}


@router.get("/{video_id}/author")
async def video_author(request: Request, video_id: str) -> dict:
    deps = request.app.state.deps
    require_active(deps.session_store)
    data = await deps.client.get("video.detail", {"aweme_id": video_id})
    detail = _detail(data)
    author = detail.get("author") or {}
    if not author:
        raise HTTPException(status_code=404, detail={"code": "AUTHOR_NOT_FOUND"})
    return {"author": normalize_user(author)}


@router.get("/{video_id}/comments", response_model=CommentResponse)
async def video_comments(request: Request, video_id: str, cursor: int = 0, count: int = 20) -> CommentResponse:
    deps = request.app.state.deps
    require_active(deps.session_store)
    data = await deps.client.get(
        "video.comments", {"aweme_id": video_id, "cursor": cursor, "count": count, "item_type": 0}
    )
    raw = pick_list(data, PROFILES["video.comments"].response_key)
    return CommentResponse(
        items=[normalize_comment(c) for c in raw if isinstance(c, dict)],
        cursor=int(data.get("cursor") or cursor or 0),
        total=int(data.get("total") or 0),
        has_more=bool(data.get("has_more")),
    )