"""Live smoke test: prove the browser signer + signed client work end to end.

Usage:
    set PLAYWRIGHT_BROWSERS_PATH=D:/Codex/Caches/ms-playwright
    python scripts/smoke_live.py
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from douyin_api.adapters.signature import BrowserSigner, SignerRegistry
from douyin_api.transport.browser import BrowserTransport
from douyin_api.auth.session import SessionStore
from douyin_api.storage.secrets import PlainProtector
from douyin_api.transport.client import DouyinClient


async def main() -> int:
    store = SessionStore(Path(__file__).parent / ".smoke-session.bin", protector=PlainProtector())
    browser = BrowserTransport(
        headless=True,
        timeout=45,
        profile_dir=Path(os.environ.get("DOUYIN_API_DATA", Path(__file__).parent)) / "browser-profile",
    )
    registry = SignerRegistry().register(
        "browser", BrowserSigner(headless=True, timeout=45, page_provider=browser.page)
    )
    client = DouyinClient(store, registry, mode="browser", browser=browser, timeout=45)
    try:
        token = await registry.sign("https://www.douyin.com/aweme/v1/web/hot/search/list/?aid=6383")
        print("X-Bogus:", token, "len:", len(token))
        data = await client.get("feed.hot_search", {"detail_list": 1, "source": 6, "board_type": 0})
        words = (data.get("data") or {}).get("word_list") or []
        print("status_code:", data.get("status_code"))
        print("hot words:", len(words))
        for w in words[:5]:
            print("  -", w.get("word"), w.get("hot_value"))
        return 0 if words else 1
    finally:
        await client.aclose()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
