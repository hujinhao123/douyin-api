from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request

from douyin_api.adapters.page import normalize_aweme, pick_list
from douyin_api.adapters.request_profile import PROFILES
from douyin_api.deps import require_active
from douyin_api.models import FeedResponse

router = APIRouter(prefix="/api/feed", tags=["feed"])


async def _feed(request: Request, profile_key: str, count: int, cursor: int, extra: dict[str, Any]) -> FeedResponse:
    deps = request.app.state.deps
    require_active(deps.session_store)
    params = {"count": count, "cursor": cursor, **extra}
    data = await deps.client.get(profile_key, params)
    items = [normalize_aweme(x) for x in pick_list(data, PROFILES[profile_key].response_key) if isinstance(x, dict)]
    return FeedResponse(
        items=items,
        cursor=int(data.get("cursor") or cursor or 0),
        has_more=bool(data.get("has_more")),
    )


@router.get("/featured", response_model=FeedResponse)
async def featured(request: Request, count: int = 10, cursor: int = 0) -> FeedResponse:
    return await _feed(request, "feed.featured", count, cursor, {"refresh_index": 1, "feed_source": 0})


@router.get("/recommend", response_model=FeedResponse)
async def recommend(request: Request, count: int = 10, cursor: int = 0) -> FeedResponse:
    return await _feed(request, "feed.recommend", count, cursor, {"refresh_index": 1, "feed_source": 1})


@router.get("/hot-search")
async def hot_search(request: Request, limit: int = 30) -> dict:
    """Public hot board; also the cheapest live check that signing works."""
    deps = request.app.state.deps
    data = await deps.client.get(
        "feed.hot_search", {"detail_list": 1, "source": 6, "board_type": 0, "board_sub_type": ""}
    )
    words = ((data.get("data") or {}).get("word_list")) or []
    return {
        "items": [
            {
                "word": w.get("word"),
                "hot_value": w.get("hot_value"),
                "position": w.get("position"),
                "sentence_id": w.get("sentence_id"),
            }
            for w in words[: max(1, min(limit, 100))]
            if isinstance(w, dict)
        ],
        "total": len(words),
    }


@router.get("/following", response_model=FeedResponse)
async def following(request: Request, count: int = 10, cursor: int = 0) -> FeedResponse:
    return await _feed(request, "feed.following", count, cursor, {"level": 1})

@router.get("/recommend/batch")
async def recommend_batch(
    request: Request,
    want: int = 10,
    rounds: int = 8,
    count: int = 10,
) -> dict:
    """Accumulate the recommendation stream across refreshes.

    The recommend tab returns only a couple of items per call. Upstream selects
    the next slice by ``refresh_index``, so several calls are required to build a
    usable page. Items are de-duplicated by ``aweme_id``; the loop stops as soon
    as ``want`` unique videos are collected or ``rounds`` is exhausted.
    """
    deps = request.app.state.deps
    require_active(deps.session_store)
    want = max(1, min(want, 60))
    rounds = max(1, min(rounds, 20))
    seen: dict[str, dict] = {}
    used = 0
    for round_no in range(1, rounds + 1):
        used = round_no
        if len(seen) >= want:
            break
        data = await deps.client.get(
            "feed.recommend", {"count": count, "refresh_index": round_no, "feed_source": 1}
        )
        for item in pick_list(data, PROFILES["feed.recommend"].response_key):
            if not isinstance(item, dict):
                continue
            vid = item.get("aweme_id") or item.get("id")
            if not vid or vid in seen:
                continue
            seen[vid] = normalize_aweme(item)
            if len(seen) >= want:
                break
    return {"items": list(seen.values()), "rounds_used": used, "count": len(seen)}
