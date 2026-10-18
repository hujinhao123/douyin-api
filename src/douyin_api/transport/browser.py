"""Browser-backed transport.

Why this exists: httpx requests to the aweme API are rejected with

    403 Blocked by ArgusSecurityPlugin Uifid Not Found

even when every header, cookie and signature matches the page byte for byte.
The rejection is decided from the TLS/HTTP2 fingerprint (JA3), not from the
request headers, so no amount of header tweaking fixes it.

The page itself, however, is accepted. So requests are issued by the page:
`page.evaluate` runs a `fetch` with `credentials: 'include'`, the response text
comes back as a string, and Python parses it. The signature is produced by the
same page runtime, so signing and transport stay consistent.

Trade-off: this needs a warm browser (already required for signing) and is a
few ms slower per call than a raw socket. In exchange it survives the TLS
fingerprinting that makes a pure-Python client unusable.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

from douyin_api.adapters.signature import SignError

# Runs inside the page. Returns a compact envelope so large bodies survive.
# `body` is a form-encoded string for POST writes; the page sends those as
# application/x-www-form-urlencoded, and the signature covers only the URL.
FETCH_JS = """
async ({url, token, timeoutMs, method, body}) => {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const init = {
      credentials: 'include',
      signal: controller.signal,
      headers: token ? {'X-Bogus': token} : {},
      method: method || 'GET',
    };
    if (body) {
      init.body = body;
      init.headers['Content-Type'] = 'application/x-www-form-urlencoded';
    }
    const response = await fetch(url, init);
    const text = await response.text();
    return {status: response.status, contentType: response.headers.get('content-type') || '', text};
  } catch (error) {
    return {status: 0, contentType: '', text: '', error: String(error)};
  } finally {
    clearTimeout(timer);
  }
}
"""


class BrowserTransport:
    """Issues signed requests from a live page so the TLS fingerprint is genuine."""

    ORIGIN = "https://www.douyin.com/"
    SDK_READY = (
        "() => !!window.byted_acrawler && "
        "typeof window.byted_acrawler.frontierSign === 'function'"
    )

    def __init__(
        self,
        *,
        headless: bool = True,
        timeout: float = 30.0,
        profile_dir: Path | None = None,
        cdp_url: str | None = None,
        executable_path: Path | None = None,
    ):
        self.headless = headless
        self.timeout = timeout
        # A persistent profile keeps the visitor fingerprint, msToken chain and
        # bd_ticket_guard state across restarts. A fresh incognito context is
        # measurably worse: the search endpoint hangs instead of answering.
        self.profile_dir = Path(profile_dir) if profile_dir else None
        # Attach to an already-running Chromium/Edge over CDP (recommended when
        # the user is logged in there); otherwise launch our own.
        self.cdp_url = cdp_url
        self.executable_path = Path(executable_path) if executable_path else None
        self._pw = None
        self._browser = None
        self._context = None
        self._page = None
        self._lock = asyncio.Lock()
        self._fetch_lock = asyncio.Lock()

    async def _new_page(self):
        from playwright.async_api import async_playwright

        if self._pw is None:
            self._pw = await async_playwright().start()
        if self.cdp_url:
            if self._browser is None or not self._browser.is_connected():
                self._browser = await self._pw.chromium.connect_over_cdp(self.cdp_url)
            if self._context is None:
                self._context = self._browser.contexts[0] if self._browser.contexts else await self._browser.new_context()
            page = await self._context.new_page()
            await page.goto(self.ORIGIN, wait_until="domcontentloaded", timeout=int(self.timeout * 1000))
            try:
                await page.wait_for_function(self.SDK_READY, timeout=int(self.timeout * 1000))
            except Exception:
                pass
            return page

        if self._browser is None or not self._browser.is_connected():
            if self.profile_dir is not None:
                self.profile_dir.mkdir(parents=True, exist_ok=True)
                self._context = await self._pw.chromium.launch_persistent_context(
                    str(self.profile_dir),
                    headless=self.headless,
                    executable_path=str(self.executable_path) if self.executable_path else None,
                    args=["--disable-blink-features=AutomationControlled", "--no-sandbox"],
                    locale="zh-CN",
                    timezone_id="Asia/Shanghai",
                    viewport={"width": 1440, "height": 900},
                    user_agent=(
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                        "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
                    ),
                )
                await self._context.add_init_script(
                    "Object.defineProperty(navigator,'webdriver',{get:()=>undefined});"
                )
            else:
                self._browser = await self._pw.chromium.launch(
                    headless=self.headless,
                    executable_path=str(self.executable_path) if self.executable_path else None,
                    args=["--disable-blink-features=AutomationControlled", "--no-sandbox"],
                )
        if self._context is None:
            self._context = await self._browser.new_context(
                locale="zh-CN",
                timezone_id="Asia/Shanghai",
                viewport={"width": 1440, "height": 900},
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
                ),
            )
            await self._context.add_init_script(
                "Object.defineProperty(navigator,'webdriver',{get:()=>undefined});"
            )
        page = await self._context.new_page()
        await page.goto(self.ORIGIN, wait_until="domcontentloaded", timeout=int(self.timeout * 1000))
        try:
            await page.wait_for_function(self.SDK_READY, timeout=int(self.timeout * 1000))
        except Exception:
            await page.reload(wait_until="domcontentloaded", timeout=int(self.timeout * 1000))
            await page.wait_for_function(self.SDK_READY, timeout=int(self.timeout * 1000))
        return page

    async def page(self):
        async with self._lock:
            if self._page is not None and not self._page.is_closed():
                return self._page
            self._page = await self._new_page()
            return self._page

    async def set_cookies(self, cookies: dict[str, str]) -> None:
        """Install a session cookie jar so page fetches are authenticated.

        Cookies must be in place *before* the page runs its own bootstrap,
        otherwise the anonymous visitor cookies it already wrote win and the
        API answers 403. So: add cookies, then reload once.
        """
        page = await self.page()
        assert self._context is not None
        fingerprint = tuple(sorted(cookies.items()))
        if getattr(self, "_cookie_fingerprint", None) == fingerprint:
            return
        payload = [
            {"name": k, "value": v, "domain": ".douyin.com", "path": "/"}
            for k, v in cookies.items()
            if k and v
        ]
        if payload:
            await self._context.add_cookies(payload)
            await page.reload(wait_until="domcontentloaded", timeout=int(self.timeout * 1000))
            try:
                await page.wait_for_function(self.SDK_READY, timeout=int(self.timeout * 1000))
            except Exception:
                pass
            await self._warm_up(page)
        self._cookie_fingerprint = fingerprint

    async def _warm_up(self, page) -> None:
        """Give the signing runtime a moment to settle.

        Observed: a fetch issued in the same tick as the post-reload SDK check
        intermittently answers `403 Blocked by ArgusSecurityPlugin Sign Invalid`,
        while the identical request succeeds a moment later. This is page
        bootstrap timing, not a request-shape problem, so we absorb it here
        instead of leaking it to callers.
        """
        try:
            await page.wait_for_timeout(1200)
            await page.evaluate(
                "() => window.byted_acrawler.frontierSign({url: location.origin + '/aweme/v1/web/hot/search/list/?aid=6383'})['X-Bogus']"
            )
        except Exception:
            pass

    async def _reset_page(self) -> None:
        """Drop the cached page so the next call builds a fresh one.

        A long-lived page eventually answers `TypeError: Failed to fetch`
        (renderer reclaimed / network context broken). Rebuilding the page
        restores transport without restarting the whole service.
        """
        page = self._page
        self._page = None
        if page is not None:
            try:
                await page.close()
            except Exception:
                pass

    async def fetch(
        self,
        url: str,
        token: str | None = None,
        *,
        method: str = "GET",
        form: str | None = None,
    ) -> dict[str, Any]:
        payload = {
            "url": url,
            "token": token or "",
            "timeoutMs": int(self.timeout * 1000),
            "method": method,
            "body": form or "",
        }
        envelope = await self._fetch_once(payload)
        if envelope.get("error"):
            # Self-heal once: rebuild the page and retry the same request.
            # A rebuild failure must not mask the original transport error.
            try:
                await self._reset_page()
                envelope = await self._fetch_once(payload)
            except Exception:
                pass
        if envelope.get("error"):
            raise SignError("TRANSPORT_FAILED", str(envelope["error"])[:200])
        text = envelope.get("text") or ""
        try:
            body = json.loads(text) if text else None
        except json.JSONDecodeError:
            body = None
        return {
            "status": envelope.get("status") or 0,
            "content_type": envelope.get("contentType") or "",
            "text": text,
            "json": body,
        }

    async def _fetch_once(self, payload: dict[str, Any]) -> dict[str, Any]:
        async with self._fetch_lock:
            page = await self.page()
            try:
                return await page.evaluate(FETCH_JS, payload)
            except Exception as exc:
                return {"status": 0, "contentType": "", "text": "", "error": str(exc)}

    async def close(self) -> None:
        for attr in ("_page", "_context", "_browser"):
            obj = getattr(self, attr)
            if obj is not None:
                try:
                    await obj.close()
                except Exception:
                    pass
                setattr(self, attr, None)
        if self._pw is not None:
            await self._pw.stop()
            self._pw = None

