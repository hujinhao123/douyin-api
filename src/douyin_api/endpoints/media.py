from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator

import httpx
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from douyin_api.adapters.page import extract_media
from douyin_api.deps import require_active

router = APIRouter(prefix="/api/video", tags=["media"])


MEDIA_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/138.0.0.0 Safari/537.36",
    "Referer": "https://www.douyin.com/",
    "Origin": "https://www.douyin.com",
}
PASSTHROUGH_HEADERS = {
    "content-type",
    "content-length",
    "content-range",
    "accept-ranges",
    "cache-control",
    "etag",
    "last-modified",
}
# Signed CDN URLs stay valid for a while; caching them avoids a browser
# round-trip on every Range request (which made seeking take seconds).
_media_cache: dict[str, tuple[float, list[str]]] = {}
_MEDIA_CACHE_TTL = 600.0
_resolve_locks: dict[str, asyncio.Lock] = {}


def _media_headers(request: Request) -> dict[str, str]:
    headers = dict(MEDIA_HEADERS)
    if request.headers.get("range"):
        headers["Range"] = request.headers["range"]
    return headers


def _pick_headers(response: httpx.Response) -> dict[str, str]:
    return {
        key: value
        for key, value in response.headers.items()
        if key.lower() in PASSTHROUGH_HEADERS
    }


def _remember_working(video_id: str, url: str) -> None:
    import time

    cached = _media_cache.get(video_id)
    candidates = list(cached[1]) if cached else []
    ordered = [url] + [item for item in candidates if item != url]
    _media_cache[video_id] = (time.monotonic(), ordered)


async def _resolve_urls(deps, video_id: str, *, refresh: bool = False) -> list[str]:
    import time

    cached = _media_cache.get(video_id)
    if cached and not refresh and time.monotonic() - cached[0] < _MEDIA_CACHE_TTL:
        return cached[1]
    lock = _resolve_locks.setdefault(video_id, asyncio.Lock())
    async with lock:
        # Another request may have filled the cache while we waited.
        cached = _media_cache.get(video_id)
        if cached and not refresh and time.monotonic() - cached[0] < _MEDIA_CACHE_TTL:
            return cached[1]
        data = await deps.client.get("video.media", {"aweme_id": video_id})
        detail = data.get("aweme_detail") or {}
        media = extract_media(detail) if detail else {}
        urls = list(media.get("play_addr") or []) + list(media.get("download_addr") or [])
        candidates = [str(item) for item in urls if str(item).startswith("http")]
        if candidates:
            _media_cache[video_id] = (time.monotonic(), candidates)
        return candidates


async def _open_upstream(urls: list[str], headers: dict[str, str]):
    """Return (client, response) for the first CDN URL that accepts us.

    One upstream request per device request. The caller closes the client.
    """
    last_status = 0
    for url in urls:
        client = httpx.AsyncClient(timeout=30.0, follow_redirects=True)
        try:
            request = client.build_request("GET", url, headers=headers)
            response = await client.send(request, stream=True)
        except Exception:
            await client.aclose()
            continue
        if response.status_code in (200, 206):
            return client, response, url
        last_status = response.status_code
        await response.aclose()
        await client.aclose()
    raise HTTPException(
        status_code=last_status if last_status in (403, 404) else 502,
        detail={"code": "MEDIA_UPSTREAM_REJECTED"},
    )


async def _relay(client: httpx.AsyncClient, response: httpx.Response) -> AsyncIterator[bytes]:
    try:
        async for chunk in response.aiter_bytes():
            yield chunk
    finally:
        await response.aclose()
        await client.aclose()


@router.get("/{video_id}/media")
async def video_media(request: Request, video_id: str) -> dict:
    deps = request.app.state.deps
    require_active(deps.session_store)
    data = await deps.client.get("video.media", {"aweme_id": video_id})
    detail = data.get("aweme_detail") or {}
    if not detail:
        raise HTTPException(status_code=404, detail={"code": "VIDEO_NOT_FOUND"})
    return {"media": extract_media(detail)}


@router.get("/{video_id}/stream")
async def video_stream(request: Request, video_id: str) -> StreamingResponse:
    """Local Range-capable relay for device playback.

    The device connects to this LAN endpoint instead of the signed CDN URL.
    The signed URL is cached for reuse so seeking does not pay a browser
    round-trip; only a rejected/expired URL triggers a refresh.
    """
    deps = request.app.state.deps
    require_active(deps.session_store)
    headers = _media_headers(request)
    import logging
    logging.getLogger("douyin_api.media").info(
        "stream %s range=%s ua=%s", video_id, headers.get("Range"), request.headers.get("user-agent", "")[:60]
    )

    urls = await _resolve_urls(deps, video_id)
    if not urls:
        raise HTTPException(status_code=404, detail={"code": "MEDIA_URL_MISSING"})
    try:
        client, upstream, used_url = await _open_upstream(urls, headers)
    except HTTPException as exc:
        if exc.status_code not in (403, 404):
            raise
        urls = await _resolve_urls(deps, video_id, refresh=True)
        if not urls:
            raise HTTPException(status_code=404, detail={"code": "MEDIA_URL_MISSING"})
        client, upstream, used_url = await _open_upstream(urls, headers)
    # Remember which candidate worked so seeks do not retry blocked edges.
    if urls and urls[0] != used_url:
        _remember_working(video_id, used_url)

    response_headers = _pick_headers(upstream)
    return StreamingResponse(
        _relay(client, upstream),
        status_code=upstream.status_code,
        headers=response_headers,
        media_type=response_headers.get("content-type", "video/mp4"),
    )
