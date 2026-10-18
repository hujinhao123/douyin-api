"""Live QR smoke test: start a QR session and render it to a PNG.

Usage:
    set PLAYWRIGHT_BROWSERS_PATH=D:\\Codex\\Caches\\ms-playwright
    python scripts/smoke_qr.py
"""

from __future__ import annotations

import asyncio
import base64
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from douyin_api.auth.qr_bridge import PageQRBridge

OUT = Path(__file__).resolve().parents[1] / "evidence"


async def main() -> int:
    OUT.mkdir(exist_ok=True)
    bridge = PageQRBridge(Path(__file__).parent / ".qr-profile", headless=True, timeout=60)
    try:
        start = await bridge.start()
        print("qr_id:", start.qr_id, "| status:", start.status.value, "| ttl:", start.expires_in_seconds)
        print("image bytes:", len(base64.b64decode(start.image_base64)))
        (OUT / "qr.png").write_bytes(base64.b64decode(start.image_base64))
        state = await bridge.poll(start.qr_id)
        print("poll ->", state.status.value, state.message or "")
        return 0
    finally:
        await bridge.close()


raise SystemExit(asyncio.run(main()))
