"""Second-level comment replies."""

from __future__ import annotations

from fastapi import APIRouter, Request

from douyin_api.adapters.page import normalize_comment, pick_list
from douyin_api.adapters.request_profile import PROFILES
from douyin_api.deps import require_active
from douyin_api.models import CommentResponse

router = APIRouter(prefix="/api/comment", tags=["comment"])


@router.get("/{comment_id}/replies", response_model=CommentResponse)
async def comment_replies(
    request: Request,
    comment_id: str,
    item_id: str,
    cursor: int = 0,
    count: int = 10,
) -> CommentResponse:
    """Replies under one comment.

    ``item_id`` (the aweme id) is required by upstream and is passed explicitly
    rather than inferred, because a comment id is not globally unique across
    videos.
    """
    deps = request.app.state.deps
    require_active(deps.session_store)
    data = await deps.client.get(
        "comment.replies",
        {
            "item_id": item_id,
            "comment_id": comment_id,
            "cut_version": 1,
            "cursor": cursor,
            "count": count,
            "item_type": 0,
        },
    )
    raw = pick_list(data, PROFILES["comment.replies"].response_key)
    return CommentResponse(
        items=[normalize_comment(c) for c in raw if isinstance(c, dict)],
        cursor=int(data.get("cursor") or cursor or 0),
        total=int(data.get("total") or 0),
        has_more=bool(data.get("has_more")),
    )
