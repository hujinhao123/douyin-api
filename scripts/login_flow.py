"""End-to-end: QR login, then call authenticated APIs with the stored session.

Usage:
    set PLAYWRIGHT_BROWSERS_PATH=D:\\Codex\\Caches\\ms-playwright
    python scripts/login_flow.py
"""

from __future__ import annotations

import asyncio
import base64
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from douyin_api.auth.qr_bridge import PageQRBridge
from douyin_api.auth.session import SessionState, SessionStore

OUT = Path(__file__).resolve().parents[1] / "evidence"


async def main() -> int:
    OUT.mkdir(exist_ok=True)
    store = SessionStore(Path(__file__).parent / ".login-session.bin")
    bridge = PageQRBridge(Path(__file__).parent / ".login-profile", headless=True, timeout=60)
    try:
        start = await bridge.start()
        (OUT / "login_qr.png").write_bytes(base64.b64decode(start.image_base64))
        print(f"QR saved to evidence/login_qr.png (qr_id={start.qr_id})")
        print("scan with the <PRIVATE_ACCOUNT_NUMBER_b90765981cdba8db> app; waiting up to 5 minutes...")

        deadline = time.time() + 300
        last = None
        while time.time() < deadline:
            state = await bridge.poll(start.qr_id)
            if state.status.value != last:
                print(f"  status -> {state.status.value}")
                last = state.status.value
            if state.status.value == "confirmed":
                cookies = await bridge.collect_cookies(start.qr_id)
                store.save(
                    SessionState(
                        cookies=cookies,
                        adapter_version="2026.10.17",
                        signer="browser",
                    )
                )
                print(f"session saved ({len(cookies)} cookies) -> {store.path}")
                return 0
            if state.status.value in {"expired", "cancelled", "failed"}:
                print(f"login ended: {state.status.value} {state.message or ''}")
                return 1
            await asyncio.sleep(2)
        print("timed out waiting for scan")
        return 1
    finally:
        await bridge.close()


raise SystemExit(asyncio.run(main()))
