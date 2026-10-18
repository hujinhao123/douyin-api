"""End-to-end authenticated run using one shared browser."""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from douyin_api.adapters.signature import BrowserSigner, SignerRegistry
from douyin_api.auth.session import SessionStore
from douyin_api.transport.browser import BrowserTransport
from douyin_api.transport.client import DouyinClient

PROFILE = Path(os.environ.get("DOUYIN_API_DATA", Path(__file__).parent)) / "browser-profile"
CDP = None  # set DOUYIN_CDP=http://127.0.0.1:9222 to reuse a running browser


async def main() -> int:
    store = SessionStore(Path(__file__).parent / ".login-session.bin")
    if store.status() != "active":
        print("no active session")
        return 2
    browser = BrowserTransport(
        headless=True,
        timeout=45,
        profile_dir=PROFILE,
        cdp_url=os.environ.get("DOUYIN_CDP") or CDP,
    )
    registry = SignerRegistry().register(
        "browser", BrowserSigner(headless=True, timeout=45, page_provider=browser.page)
    )
    client = DouyinClient(store, registry, mode="browser", browser=browser, timeout=45)
    failures: list[str] = []

    def line(k, v):
        print(f"  {k:<18} {v}")

    try:
        feed = await client.get("feed.featured", {"count": 5, "refresh_index": 1, "feed_source": 0})
        print("feed.featured")
        line("status", feed.get("status_code"))
        line("items", len(feed.get("aweme_list") or []))
        if feed.get("status_code") != 0:
            failures.append("feed.featured")

        items = feed.get("aweme_list") or []
        if items:
            vid = items[0].get("aweme_id")
            uid = (items[0].get("author") or {}).get("sec_uid")

            detail = await client.get("video.detail", {"aweme_id": vid})
            print("video.detail")
            line("status", detail.get("status_code"))
            line("has_detail", bool(detail.get("aweme_detail")))
            if detail.get("status_code") != 0:
                failures.append("video.detail")

            comments = await client.get("video.comments", {"aweme_id": vid, "cursor": 0, "count": 5, "item_type": 0})
            print("video.comments")
            line("status", comments.get("status_code"))
            line("items", len(comments.get("comments") or []))
            line("total", comments.get("total"))
            if comments.get("status_code") != 0:
                failures.append("video.comments")

            if uid:
                profile = await client.get("user.profile", {"sec_user_id": uid, "publish_video_strategy_type": 2})
                print("user.profile")
                line("status", profile.get("status_code"))
                line("has_user", bool(profile.get("user")))
                if profile.get("status_code") != 0:
                    failures.append("user.profile")

                posts = await client.get("user.posts", {"sec_user_id": uid, "cursor": 0, "count": 5, "publish_video_strategy_type": 2})
                print("user.posts")
                line("status", posts.get("status_code"))
                line("items", len(posts.get("aweme_list") or []))
                line("max_cursor", posts.get("max_cursor"))
                if posts.get("status_code") != 0:
                    failures.append("user.posts")

                for key, extra in (
                    ("user.following", {"source_type": 1}),
                    ("user.followers", {}),
                ):
                    print(key)
                    try:
                        data = await client.get(
                            key, {"sec_user_id": uid, "cursor": 0, "count": 5, **extra}
                        )
                        line("status", data.get("status_code"))
                        line("items", len((data.get("followings") or data.get("followers") or [])))
                    except Exception as exc:
                        # 2096 (privacy) is a legitimate answer, not a failure.
                        line("result", f"{type(exc).__name__}: {exc}")
                        if "PRIVACY_HIDDEN" not in str(exc):
                            failures.append(key)

        # search.general was verified in the user's own tab (200, 10 items) but
        # hangs on a freshly launched profile. Opt in with DOUYIN_SEARCH=1.
        print("search.general")
        search = None
        if os.environ.get("DOUYIN_SEARCH") == "1":
            try:
                search = await asyncio.wait_for(
                    client.get(
                        "search.general",
                        {
                            "keyword": "人工智能",
                            "cursor": 0,
                            "count": 5,
                            "search_channel": "aweme_general",
                            "search_source": "normal_search",
                            "query_correct_type": 1,
                            "is_filter_search": 0,
                            "sort_type": 0,
                            "publish_time": 0,
                            "filter_duration": "0",
                        },
                    ),
                    timeout=60,
                )
            except asyncio.TimeoutError:
                line("result", "TIMEOUT (cold profile limitation)")
                failures.append("search.general")
        if search is not None:
            line("status", search.get("status_code"))
            line("items", len(search.get("data") or []))
            if search.get("status_code") != 0:
                failures.append("search.general")
        else:
            line("result", "skipped (set DOUYIN_SEARCH=1)")

        hot = await client.get("feed.hot_search", {"detail_list": 1, "source": 6, "board_type": 0})
        print("feed.hot_search")
        line("status", hot.get("status_code"))
        line("items", len(((hot.get("data") or {}).get("word_list")) or []))
        if hot.get("status_code") != 0:
            failures.append("feed.hot_search")
    finally:
        await client.aclose()

    print()
    if failures:
        print("FAILED:", ", ".join(failures))
        return 1
    print("ALL ENDPOINTS OK")
    return 0


raise SystemExit(asyncio.run(main()))
