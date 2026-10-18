"""Normalizers that keep upstream shape changes contained in one place."""

from __future__ import annotations

from typing import Any


def pick_list(payload: dict[str, Any], response_key: str | None, fallback: str = "items") -> list[Any]:
    if response_key:
        value = payload.get(response_key)
        if isinstance(value, list):
            return value
    for key in (fallback, "data", "aweme_list", "comments", "followings", "followers"):
        value = payload.get(key)
        if isinstance(value, list):
            return value
    return []


def _id_str(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)


def normalize_aweme(item: dict[str, Any]) -> dict[str, Any]:
    author = item.get("author") or {}
    stats = item.get("statistics") or {}
    video = item.get("video") or {}
    return {
        "id": _id_str(item.get("aweme_id") or item.get("id")),
        "desc": item.get("desc"),
        "create_time": item.get("create_time"),
        "author": {
            "uid": _id_str(author.get("uid")),
            "sec_uid": author.get("sec_uid"),
            "nickname": author.get("nickname"),
            "unique_id": author.get("unique_id"),
            "signature": author.get("signature"),
        }
        if author
        else None,
        "stats": {
            "digg_count": stats.get("digg_count"),
            "comment_count": stats.get("comment_count"),
            "share_count": stats.get("share_count"),
            "collect_count": stats.get("collect_count"),
            "play_count": stats.get("play_count"),
        },
        "video": {
            "duration_ms": video.get("duration"),
            "ratio": video.get("ratio"),
            "width": video.get("width"),
            "height": video.get("height"),
            "cover": ((video.get("cover") or {}).get("url_list") or [None])[0],
            "play_addr": ((video.get("play_addr") or {}).get("url_list") or [None])[0],
        }
        if video
        else None,
        "is_top": item.get("is_top"),
    }


def normalize_comment(item: dict[str, Any]) -> dict[str, Any]:
    user = item.get("user") or {}
    return {
        "id": _id_str(item.get("cid")),
        "text": item.get("text"),
        "create_time": item.get("create_time"),
        "digg_count": item.get("digg_count"),
        "reply_comment_total": item.get("reply_comment_total"),
        "user": {
            "uid": _id_str(user.get("uid")),
            "sec_uid": user.get("sec_uid"),
            "nickname": user.get("nickname"),
        }
        if user
        else None,
    }


def normalize_user(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "uid": _id_str(item.get("uid")),
        "sec_uid": item.get("sec_uid"),
        "nickname": item.get("nickname"),
        "unique_id": item.get("unique_id"),
        "signature": item.get("signature"),
        "avatar": ((item.get("avatar_thumb") or {}).get("url_list") or [None])[0],
        "follower_count": item.get("follower_count"),
        "following_count": item.get("following_count"),
        "aweme_count": item.get("aweme_count"),
        "is_follow": item.get("is_follow"),
    }


def extract_media(detail: dict[str, Any]) -> dict[str, Any]:
    video = detail.get("video") or {}
    play = video.get("play_addr") or {}
    bit_rates = []
    for rate in video.get("bit_rate") or []:
        addr = rate.get("play_addr") or {}
        bit_rates.append(
            {
                "gear_name": rate.get("gear_name"),
                "bit_rate": rate.get("bit_rate"),
                "quality_type": rate.get("quality_type"),
                "width": rate.get("width"),
                "height": rate.get("height"),
                "urls": addr.get("url_list") or [],
                "data_size": addr.get("data_size"),
            }
        )
    # Geometry: the top-level video object carries width/height for most items,
    # but some responses only populate them on bit_rate entries. Fall back to the
    # largest gear so callers always get a usable orientation.
    width = video.get("width")
    height = video.get("height")
    if not width or not height:
        for rate in bit_rates:
            rw, rh = rate.get("width"), rate.get("height")
            if rw and rh and (not width or (rw * rh) > (width * height)):
                width, height = rw, rh

    return {
        "aweme_id": _id_str(detail.get("aweme_id")),
        "duration_ms": video.get("duration"),
        "width": width,
        "height": height,
        "ratio": video.get("ratio"),
        "cover": ((video.get("cover") or {}).get("url_list") or [None])[0],
        "dynamic_cover": ((video.get("dynamic_cover") or {}).get("url_list") or [None])[0],
        "play_addr": play.get("url_list") or [],
        "download_addr": ((video.get("download_addr") or {}).get("url_list") or []),
        "bit_rates": bit_rates,
        "music": {
            "title": ((detail.get("music") or {}).get("title")),
            "play_url": (((detail.get("music") or {}).get("play_url") or {}).get("url_list") or [None])[0],
        }
        if detail.get("music")
        else None,
    }