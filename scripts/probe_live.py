"""Live drift probe against the real API (public profiles only)."""

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
from douyin_api.recovery import build_report, load_baseline, probe_all
from douyin_api.storage.secrets import PlainProtector
from douyin_api.transport.client import DouyinClient


async def main() -> int:
    store = SessionStore(Path(__file__).parent / ".probe-session.bin", protector=PlainProtector())
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
        probes = await probe_all(client, ["feed.hot_search"])
        baseline = load_baseline(Path(__file__).resolve().parents[1] / "tests/fixtures/live_contract.json")
        report = build_report(probes, baseline)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0 if report["healthy"] else 1
    finally:
        await client.aclose()


raise SystemExit(asyncio.run(main()))
