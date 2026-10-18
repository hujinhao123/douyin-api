"""QR login through the real web page.

Verified facts (live capture, 2026-10-17):

* ``/passport/web/get_qrcode/`` returns ``error_code: 4031`` when called cold.
  It only succeeds after the page has completed ``/passport/web/challenge/``,
  ``/passport/ticket_guard/get_client_cert/`` and the ``mssdk`` token exchange.
* Once the login modal is opened by the page itself, the QR arrives as a
  ``data:image/png;base64,...`` <img> inside ``.douyin_login_new_class``.
* ``/passport/web/check_qrconnect/`` answers ``status: "new" | "scan" | "confirmed"``.

So the bridge drives the real modal instead of re-implementing the challenge
handshake. That keeps it working across passport SDK updates.
"""

from __future__ import annotations

import asyncio
import base64
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

from douyin_api.auth.qr_login import QRStart, QRState, QRStatus

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)
STEALTH = "Object.defineProperty(navigator,'webdriver',{get:()=>undefined});"

LOGIN_BUTTON_SELECTORS = (
    '[data-e2e="login-button"]',
    'button:has-text("登录")',
    'text=登录',
)
PANEL_SELECTOR = ".douyin_login_new_class"

# Reads the modal: QR image, visible copy, and whether the QR is still loading.
PANEL_PROBE = """
() => {
  const panel = document.querySelector('.douyin_login_new_class');
  if (!panel) return {present: false};
  const imgs = [...panel.querySelectorAll('img')]
    .map(i => ({src: i.src, w: i.naturalWidth || i.width, h: i.naturalHeight || i.height}))
    .filter(i => i.src.startsWith('data:image/png;base64,') && i.w > 100);
  const qr = imgs[0] || null;
  return {
    present: true,
    qr: qr ? qr.src : null,
    text: panel.innerText.slice(0, 400),
  };
}
"""


@dataclass
class _Record:
    qr_id: str
    expires_at: float
    status: QRStatus = QRStatus.CREATED
    redirect_url: str | None = None
    cookies: dict[str, str] = field(default_factory=dict)
    message: str | None = None
    image_base64: str = ""


class PageQRBridge:
    """Drives the real <PRIVATE_ACCOUNT_NUMBER_b90765981cdba8db> login modal in a persistent Chromium profile."""

    def __init__(
        self,
        profile_dir,
        *,
        headless: bool = True,
        timeout: float = 45.0,
        ttl_seconds: int = 300,
        clock=time.time,
    ):
        self.profile_dir = profile_dir
        self.headless = headless
        self.timeout = timeout
        self.ttl_seconds = ttl_seconds
        self.clock = clock
        self._pw = None
        self._context = None
        self._page = None
        self._records: dict[str, _Record] = {}
        self._lock = asyncio.Lock()

    # -- browser lifecycle -------------------------------------------------
    async def _ensure_context(self):
        from playwright.async_api import async_playwright

        if self._context is not None:
            return self._context
        if self._pw is None:
            self._pw = await async_playwright().start()
        self._context = await self._pw.chromium.launch_persistent_context(
            str(self.profile_dir),
            headless=self.headless,
            args=["--disable-blink-features=AutomationControlled", "--no-sandbox"],
            locale="zh-CN",
            timezone_id="Asia/Shanghai",
            viewport={"width": 1440, "height": 900},
            user_agent=USER_AGENT,
        )
        await self._context.add_init_script(STEALTH)
        return self._context

    async def _ensure_page(self):
        ctx = await self._ensure_context()
        if self._page is not None and not self._page.is_closed():
            return self._page
        self._page = ctx.pages[0] if ctx.pages else await ctx.new_page()
        if not self._page.url.startswith("https://www.douyin.com"):
            await self._page.goto(
                "https://www.douyin.com/", wait_until="domcontentloaded", timeout=int(self.timeout * 1000)
            )
        try:
            await self._page.wait_for_load_state("networkidle", timeout=15000)
        except Exception:
            pass  # long-polling keeps the network busy; a paint wait is enough
        return self._page

    async def _open_modal(self, page) -> None:
        """Click the header login entry; retries because the SPA paints late."""
        deadline = self.clock() + self.timeout
        last_error = "no login selector matched"
        while self.clock() < deadline:
            for selector in LOGIN_BUTTON_SELECTORS:
                try:
                    locator = page.locator(selector).first
                    if await locator.count() and await locator.is_visible():
                        await locator.click(timeout=4000)
                        await asyncio.sleep(0.8)
                        if await page.evaluate("() => !!document.querySelector('.douyin_login_new_class')"):
                            return
                        last_error = f"clicked {selector} but modal did not open"
                except Exception as exc:
                    last_error = f"{selector}: {type(exc).__name__}"
            # The header sometimes needs a scroll/paint cycle before the button is hit-testable.
            await asyncio.sleep(1.0)
        raise RuntimeError(f"login entry point not found on page ({last_error})")

    async def _wait_for_qr(self, page) -> str:
        deadline = self.clock() + self.timeout
        while self.clock() < deadline:
            probe = await page.evaluate(PANEL_PROBE)
            if probe.get("qr"):
                return probe["qr"].split(",", 1)[1]
            await asyncio.sleep(0.5)
        raise RuntimeError("QR image never appeared in the login modal")

    # -- public API --------------------------------------------------------
    async def start(self) -> QRStart:
        async with self._lock:
            page = await self._ensure_page()
            if await page.evaluate("() => !!document.querySelector('.douyin_login_new_class')") is False:
                await self._open_modal(page)
            image = await self._wait_for_qr(page)
            qr_id = uuid.uuid4().hex
            self._records[qr_id] = _Record(
                qr_id=qr_id, expires_at=self.clock() + self.ttl_seconds, image_base64=image
            )
            return QRStart(
                qr_id=qr_id,
                image_base64=image,
                qr_url="",
                status=QRStatus.CREATED,
                expires_in_seconds=self.ttl_seconds,
                poll_interval_seconds=2,
            )

    async def poll(self, qr_id: str) -> QRState:
        record = self._records[qr_id]
        if record.status in {QRStatus.CONFIRMED, QRStatus.CANCELLED, QRStatus.FAILED}:
            return QRState(qr_id=qr_id, status=record.status, redirect_url=record.redirect_url)
        if self.clock() > record.expires_at:
            record.status = QRStatus.EXPIRED
            return QRState(qr_id=qr_id, status=QRStatus.EXPIRED, message="QR expired")
        page = await self._ensure_page()
        try:
            probe = await page.evaluate(PANEL_PROBE)
        except Exception as exc:
            record.status = QRStatus.FAILED
            record.message = str(exc)
            return QRState(qr_id=qr_id, status=QRStatus.FAILED, message=record.message)
        if not probe.get("present"):
            # Modal closed: either the login completed or the user dismissed it.
            cookies = await self._cookies()
            if self._has_session_cookie(cookies):
                record.status = QRStatus.CONFIRMED
                record.cookies = cookies
                return QRState(qr_id=qr_id, status=QRStatus.CONFIRMED)
            record.status = QRStatus.CANCELLED
            return QRState(qr_id=qr_id, status=QRStatus.CANCELLED, message="login modal closed")
        text = probe.get("text") or ""
        if "扫码成功" in text or "请在手机上确认" in text:
            record.status = QRStatus.SCANNED
            return QRState(qr_id=qr_id, status=QRStatus.SCANNED)
        cookies = await self._cookies()
        if self._has_session_cookie(cookies):
            record.status = QRStatus.CONFIRMED
            record.cookies = cookies
            return QRState(qr_id=qr_id, status=QRStatus.CONFIRMED)
        record.status = QRStatus.CREATED
        return QRState(qr_id=qr_id, status=QRStatus.CREATED)

    async def cancel(self, qr_id: str) -> QRState:
        record = self._records.pop(qr_id, None)
        if record is None:
            raise KeyError(qr_id)
        page = await self._ensure_page()
        try:
            await page.keyboard.press("Escape")
        except Exception:
            pass
        return QRState(qr_id=qr_id, status=QRStatus.CANCELLED)

    async def collect_cookies(self, qr_id: str) -> dict[str, str]:
        record = self._records.get(qr_id)
        if record is None:
            raise KeyError(qr_id)
        if record.cookies:
            return dict(record.cookies)
        cookies = await self._cookies()
        if not self._has_session_cookie(cookies):
            raise PermissionError("login not completed yet")
        record.cookies = cookies
        return dict(cookies)

    # -- helpers -----------------------------------------------------------
    async def _cookies(self) -> dict[str, str]:
        ctx = await self._ensure_context()
        raw = await ctx.cookies("https://www.douyin.com")
        return {c["name"]: c["value"] for c in raw if c.get("name")}

    @staticmethod
    def _has_session_cookie(cookies: dict[str, str]) -> bool:
        return any(name in cookies for name in ("sessionid", "sessionid_ss", "sid_tt"))

    async def close(self) -> None:
        if self._context is not None:
            try:
                await self._context.close()
            except Exception:
                pass
            self._context = None
        if self._pw is not None:
            await self._pw.stop()
            self._pw = None
        self._page = None
