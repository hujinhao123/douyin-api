"""Mix (collection) browsing."""

from __future__ import annotations

from fastapi import APIRouter, Request

from douyin_api.adapters.page import normalize_aweme, pick_list
from douyin_api.adapters.request_profile import PROFILES
from douyin_api.deps import require_active
from douyin_api.models import FeedResponse

router = APIRouter(prefix="/api/mix", tags=["mix"])


@router.get("/{mix_id}", response_model=FeedResponse)
async def mix_videos(request: Request, mix_id: str, cursor: int = 0, count: int = 20) -> FeedResponse:
    deps = request.app.state.deps
    require_active(deps.session_store)
    data = await deps.client.get("mix.detail", {"mix_id": mix_id, "cursor": cursor, "count": count})
    raw = pick_list(data, PROFILES["mix.detail"].response_key)
    return FeedResponse(
        items=[normalize_aweme(x) for x in raw if isinstance(x, dict)],
        cursor=int(data.get("cursor") or cursor or 0),
        has_more=bool(data.get("has_more")),
    )
