from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from douyin_api.adapters.page import normalize_aweme, normalize_user, pick_list
from douyin_api.adapters.request_profile import PROFILES
from douyin_api.deps import require_active
from douyin_api.models import FeedResponse

router = APIRouter(prefix="/api/user", tags=["user"])


@router.get("/{user_id}")
async def user_profile(request: Request, user_id: str) -> dict:
    deps = request.app.state.deps
    require_active(deps.session_store)
    data = await deps.client.get(
        "user.profile", {"sec_user_id": user_id, "publish_video_strategy_type": 2}
    )
    user = data.get("user") or {}
    if not user:
        raise HTTPException(status_code=404, detail={"code": "USER_NOT_FOUND"})
    return {"user": normalize_user(user)}


@router.get("/{user_id}/videos", response_model=FeedResponse)
async def user_videos(request: Request, user_id: str, cursor: int = 0, count: int = 20) -> FeedResponse:
    deps = request.app.state.deps
    require_active(deps.session_store)
    data = await deps.client.get(
        "user.posts",
        {"sec_user_id": user_id, "cursor": cursor, "count": count, "publish_video_strategy_type": 2},
    )
    raw = pick_list(data, PROFILES["user.posts"].response_key)
    # Verified: this endpoint paginates with max_cursor (ms timestamp), not cursor.
    next_cursor = data.get("max_cursor")
    if next_cursor is None:
        next_cursor = data.get("cursor", cursor)
    return FeedResponse(
        items=[normalize_aweme(x) for x in raw if isinstance(x, dict)],
        cursor=int(next_cursor or 0),
        has_more=bool(data.get("has_more")),
    )


@router.get("/{user_id}/following")
async def user_following(request: Request, user_id: str, cursor: int = 0, count: int = 20) -> dict:
    deps = request.app.state.deps
    require_active(deps.session_store)
    data = await deps.client.get(
        "user.following",
        {"sec_user_id": user_id, "cursor": cursor, "count": count, "source_type": 1},
    )
    raw = pick_list(data, PROFILES["user.following"].response_key)
    return {
        "items": [normalize_user(x) for x in raw if isinstance(x, dict)],
        "cursor": int(data.get("cursor") or cursor or 0),
        "has_more": bool(data.get("has_more")),
        "total": int(data.get("total") or 0),
    }


@router.get("/{user_id}/followers")
async def user_followers(request: Request, user_id: str, cursor: int = 0, count: int = 20) -> dict:
    deps = request.app.state.deps
    require_active(deps.session_store)
    data = await deps.client.get(
        "user.followers",
        {"sec_user_id": user_id, "cursor": cursor, "count": count},
    )
    raw = pick_list(data, PROFILES["user.followers"].response_key)
    return {
        "items": [normalize_user(x) for x in raw if isinstance(x, dict)],
        "cursor": int(data.get("cursor") or cursor or 0),
        "has_more": bool(data.get("has_more")),
        "total": int(data.get("total") or 0),
    }