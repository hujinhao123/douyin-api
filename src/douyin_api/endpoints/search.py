from __future__ import annotations

from fastapi import APIRouter, Query, Request

from douyin_api.adapters.page import normalize_aweme, pick_list
from douyin_api.adapters.request_profile import PROFILES
from douyin_api.deps import require_active
from douyin_api.models import SearchResponse

router = APIRouter(prefix="/api", tags=["search"])


@router.get("/search", response_model=SearchResponse)
async def search(
    request: Request,
    keyword: str = Query(..., min_length=1, description="search keyword"),
    cursor: int = 0,
    count: int = 10,
    sort_type: int = 0,
    publish_time: int = 0,
    filter_duration: str = "0",
    search_channel: str = "aweme_general",
) -> SearchResponse:
    deps = request.app.state.deps
    require_active(deps.session_store)
    params = {
        "keyword": keyword,
        "cursor": cursor,
        "count": count,
        "sort_type": sort_type,
        "publish_time": publish_time,
        "filter_duration": filter_duration,
        "search_channel": search_channel,
        "search_source": "normal_search",
        "query_correct_type": 1,
        "is_filter_search": 0,
    }
    data = await deps.client.get("search.general", params)
    raw = pick_list(data, PROFILES["search.general"].response_key)
    items = []
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        aweme = entry.get("aweme_info") or entry
        items.append(normalize_aweme(aweme) if isinstance(aweme, dict) else {"raw": aweme})
    return SearchResponse(
        items=items,
        cursor=int(data.get("cursor") or cursor or 0),
        has_more=bool(data.get("has_more")),
        search_id=data.get("extra", {}).get("search_id") if isinstance(data.get("extra"), dict) else None,
    )

@router.get("/search/users")
async def search_users(
    request: Request,
    keyword: str = Query(..., min_length=1, description="search keyword"),
    offset: int = 0,
    count: int = 10,
    search_id: str | None = None,
) -> dict:
    """User (author) search.

    Upstream requires ``search_channel=aweme_user_web`` and paginates with
    ``offset`` (not cursor). ``search_id`` is echoed back after the first page.
    """
    deps = request.app.state.deps
    require_active(deps.session_store)
    params: dict = {
        "keyword": keyword,
        "search_channel": "aweme_user_web",
        "search_source": "normal_search",
        "query_correct_type": 1,
        "is_filter_search": 0,
        "disable_rs": 0,
        "offset": offset,
        "count": count,
        "need_filter_settings": 1 if offset == 0 else 0,
        "list_type": "single",
        "pc_search_top_1_params": '{"enable_ai_search_top_1":1}',
    }
    if search_id:
        params["search_id"] = search_id
    data = await deps.client.get("search.user", params)
    raw = pick_list(data, PROFILES["search.user"].response_key)
    items = []
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        user = entry.get("user_info") or entry.get("user") or entry
        if not isinstance(user, dict):
            continue
        items.append(
            {
                "uid": user.get("uid"),
                "sec_uid": user.get("sec_uid"),
                "nickname": user.get("nickname"),
                "unique_id": user.get("unique_id"),
                "signature": user.get("signature"),
                "avatar": ((user.get("avatar_thumb") or {}).get("url_list") or [None])[0],
                "follower_count": user.get("follower_count"),
                "aweme_count": user.get("aweme_count"),
                "is_verified": user.get("is_verified"),
                "verify_info": user.get("verify_info") or entry.get("verify_info"),
            }
        )
    extra = data.get("extra") or {}
    return {
        "items": items,
        "offset": offset + len(items),
        "has_more": bool(data.get("has_more")),
        "search_id": extra.get("search_id") if isinstance(extra, dict) else None,
    }
