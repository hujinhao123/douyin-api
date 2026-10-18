"""Self-scoped endpoints: my profile, favourites, history, watch later."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from douyin_api.adapters.page import normalize_aweme, normalize_user, pick_list
from douyin_api.adapters.request_profile import PROFILES
from douyin_api.deps import require_active
from douyin_api.models import FeedResponse

router = APIRouter(prefix="/api/me", tags=["me"])


async def _self_sec_uid(request: Request) -> str:
    """Resolve the logged-in account's sec_uid (cached on the app state)."""
    deps = request.app.state.deps
    cached = deps.extra.get("self_sec_uid")
    if cached:
        return cached
    data = await deps.client.get("user.self", {"publish_video_strategy_type": 2})
    user = data.get("user") or {}
    sec = user.get("sec_uid") or ""
    if not sec:
        raise HTTPException(status_code=502, detail={"code": "SELF_LOOKUP_FAILED"})
    deps.extra["self_sec_uid"] = sec
    deps.extra["self_user"] = user
    return sec


@router.get("")
async def me(request: Request) -> dict:
    deps = request.app.state.deps
    require_active(deps.session_store)
    data = await deps.client.get("user.self", {"publish_video_strategy_type": 2})
    user = data.get("user") or {}
    if not user:
        raise HTTPException(status_code=502, detail={"code": "SELF_LOOKUP_FAILED"})
    deps.extra["self_sec_uid"] = user.get("sec_uid")
    deps.extra["self_user"] = user
    collect = data.get("user_collect_count") or {}
    counts = {}
    for entry in collect.get("collect_count_list") or []:
        if isinstance(entry, dict):
            counts[str(entry.get("item_type"))] = entry.get("collect_count")
    return {
        "user": normalize_user(user),
        "counts": {
            "collect": counts,
            "watch_later": data.get("user_watchlater_count"),
            "favoriting": user.get("favoriting_count"),
            "following": user.get("following_count"),
            "followers": user.get("follower_count"),
            "works": user.get("aweme_count"),
        },
    }


@router.get("/collection", response_model=FeedResponse)
async def my_collection(request: Request, cursor: int = 0, count: int = 18) -> FeedResponse:
    deps = request.app.state.deps
    require_active(deps.session_store)
    sec = await _self_sec_uid(request)
    data = await deps.client.get(
        "user.collection",
        {
            "sec_user_id": sec,
            "max_cursor": cursor,
            "min_cursor": 0,
            "cut_version": 1,
            "count": count,
            "publish_video_strategy_type": 2,
        },
    )
    raw = pick_list(data, PROFILES["user.collection"].response_key)
    return FeedResponse(
        items=[normalize_aweme(x) for x in raw if isinstance(x, dict)],
        cursor=int(data.get("max_cursor") or cursor or 0),
        has_more=bool(data.get("has_more")),
    )


@router.get("/history", response_model=FeedResponse)
async def my_history(request: Request, cursor: int = 0, count: int = 20) -> FeedResponse:
    deps = request.app.state.deps
    require_active(deps.session_store)
    data = await deps.client.get("user.history", {"count": count, "cursor": cursor})
    raw = pick_list(data, PROFILES["user.history"].response_key)
    return FeedResponse(
        items=[normalize_aweme(x) for x in raw if isinstance(x, dict)],
        cursor=int(data.get("max_cursor") or cursor or 0),
        has_more=bool(data.get("has_more")),
    )


@router.get("/watch-later", response_model=FeedResponse)
async def my_watch_later(request: Request, cursor: int = 0, count: int = 20) -> FeedResponse:
    deps = request.app.state.deps
    require_active(deps.session_store)
    data = await deps.client.get("user.watchlater", {"count": count, "cursor": cursor})
    raw = pick_list(data, PROFILES["user.watchlater"].response_key)
    return FeedResponse(
        items=[normalize_aweme(x) for x in raw if isinstance(x, dict)],
        cursor=int(data.get("offset") or cursor or 0),
        has_more=bool(data.get("has_more")),
    )


@router.get("/mixes")
async def my_mixes(request: Request, cursor: int = 0, count: int = 20) -> dict:
    deps = request.app.state.deps
    require_active(deps.session_store)
    data = await deps.client.get("mix.collection", {"cursor": cursor, "count": count})
    raw = pick_list(data, PROFILES["mix.collection"].response_key)
    items = []
    for mix in raw:
        if not isinstance(mix, dict):
            continue
        info = mix.get("mix_info") or mix
        stat = mix.get("statis") or {}
        items.append(
            {
                "mix_id": info.get("mix_id"),
                "name": info.get("mix_name"),
                "desc": info.get("desc"),
                "cover": ((info.get("cover_url") or {}).get("url_list") or [None])[0],
                "item_count": stat.get("updated_to_episode") or info.get("statis", {}).get("collect_vv"),
                "create_time": info.get("create_time"),
                "is_union_video": info.get("is_union_video"),
            }
        )
    return {"items": items, "cursor": int(data.get("cursor") or cursor or 0), "has_more": bool(data.get("has_more"))}

