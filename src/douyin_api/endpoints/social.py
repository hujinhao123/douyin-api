"""Write endpoints: like, favourite, follow, comment.

Payload placement matters and was measured against the live site:

* ``/aweme/v1/web/commit/item/digg/`` takes ``aweme_id``, ``item_type`` and
  ``type`` in an urlencoded **body**. Sending them as query parameters answers
  ``status_code: 0`` with ``status_msg: "url doesn't match"`` and changes
  nothing -- a silent no-op that looks like success.
* ``item_type=0`` means "video"; omitting it also fails.

Every write is dry-run by default and needs ``confirm=true`` to reach upstream.
"""

from __future__ import annotations

from fastapi import APIRouter, Request

from douyin_api.deps import require_active
from douyin_api.models import WriteRequest

router = APIRouter(prefix="/api", tags=["social"])


async def _write(
    request: Request,
    profile_key: str,
    form: dict,
    body: WriteRequest,
    *,
    query: dict | None = None,
) -> dict:
    deps = request.app.state.deps
    require_active(deps.session_store)
    return await deps.ensure_writer().execute(profile_key, query or {}, body, form=form)


@router.post("/video/{video_id}/like")
async def like(request: Request, video_id: str, body: WriteRequest) -> dict:
    return await _write(
        request, "social.digg", {"aweme_id": video_id, "item_type": 0, "type": 1}, body
    )


@router.delete("/video/{video_id}/like")
async def unlike(request: Request, video_id: str, body: WriteRequest) -> dict:
    return await _write(
        request, "social.digg", {"aweme_id": video_id, "item_type": 0, "type": 0}, body
    )


@router.post("/video/{video_id}/favorite")
async def favorite(request: Request, video_id: str, body: WriteRequest) -> dict:
    return await _write(
        request, "social.favorite", {"aweme_id": video_id, "aweme_type": 0, "action": 1}, body
    )


@router.delete("/video/{video_id}/favorite")
async def unfavorite(request: Request, video_id: str, body: WriteRequest) -> dict:
    return await _write(
        request, "social.favorite", {"aweme_id": video_id, "aweme_type": 0, "action": 0}, body
    )


@router.post("/user/{user_id}/follow")
async def follow(request: Request, user_id: str, body: WriteRequest) -> dict:
    return await _write(
        request, "social.follow", {"sec_user_id": user_id, "type": 1, "from": 0}, body
    )


@router.delete("/user/{user_id}/follow")
async def unfollow(request: Request, user_id: str, body: WriteRequest) -> dict:
    return await _write(
        request, "social.follow", {"sec_user_id": user_id, "type": 0, "from": 0}, body
    )


@router.post("/video/{video_id}/comment")
async def comment(request: Request, video_id: str, body: WriteRequest, text: str = "") -> dict:
    return await _write(
        request,
        "social.comment",
        {"aweme_id": video_id, "text": text, "text_extra": "[]", "comment_type": 1},
        body,
    )

