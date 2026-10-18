"""Signer chain: browser bridge first, static snapshot second.

`X-Bogus` is produced by the page runtime (`window.byted_acrawler.frontierSign`).
The browser signer always reflects the live page, so it survives bundle updates.
The static signer is an offline fallback for when no browser is available.
"""

from __future__ import annotations

import asyncio
import shutil
from pathlib import Path
from typing import Awaitable, Callable

SignFn = Callable[[str], Awaitable[str]]


class SignError(Exception):
    def __init__(self, code: str, detail: str):
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail


class SignerRegistry:
    """Ordered signer chain; falls back on failure and reports every reason."""

    def __init__(self) -> None:
        self._chain: list[tuple[str, SignFn]] = []

    def register(self, name: str, fn: SignFn) -> "SignerRegistry":
        self._chain.append((name, fn))
        return self

    @property
    def names(self) -> list[str]:
        return [name for name, _ in self._chain]

    async def sign(self, url: str) -> str:
        errors: list[str] = []
        for name, fn in self._chain:
            try:
                token = await fn(url)
            except SignError as exc:
                errors.append(f"{name}: {exc.detail}")
                continue
            except Exception as exc:  # any signer failure degrades to the next one
                errors.append(f"{name}: {exc}")
                continue
            if token:
                return token
            errors.append(f"{name}: empty token")
        raise SignError("SIGN_FAILED", "; ".join(errors) or "no signer registered")


class StaticSigner:
    """Runs an extracted signing bundle with Node: `node sign.js <url>` -> token."""

    def __init__(self, bundle: Path, node_binary: str = "node", timeout: float = 20.0):
        self.bundle = Path(bundle)
        self.node_binary = node_binary
        self.timeout = timeout

    async def __call__(self, url: str) -> str:
        if not self.bundle.exists():
            raise SignError("SIGNER_UNAVAILABLE", f"bundle missing: {self.bundle}")
        node = shutil.which(self.node_binary) or self.node_binary
        proc = await asyncio.create_subprocess_exec(
            node,
            str(self.bundle),
            url,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            out, err = await asyncio.wait_for(proc.communicate(), timeout=self.timeout)
        except asyncio.TimeoutError:
            proc.kill()
            raise SignError("SIGN_FAILED", "static signer timed out")
        if proc.returncode != 0:
            raise SignError("SIGN_FAILED", err.decode("utf-8", "replace").strip()[:300])
        token = out.decode("utf-8", "replace").strip()
        if not token:
            raise SignError("SIGN_FAILED", "static signer returned empty token")
        return token


class BrowserSigner:
    """Calls the live page runtime through Playwright.

    A single warm page is kept; `frontierSign` is evaluated per URL. Because the
    token comes from the page that is loaded today, a bundle update is picked up
    automatically on the next navigation - no extracted SDK to maintain.
    """

    ORIGIN = "https://www.douyin.com/"
    USER_AGENT = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    )
    STEALTH = "Object.defineProperty(navigator,'webdriver',{get:()=>undefined});"
    SDK_READY = (
        "() => !!window.byted_acrawler && "
        "typeof window.byted_acrawler.frontierSign === 'function'"
    )

    def __init__(self, *, headless: bool = True, timeout: float = 45.0, page_provider=None):
        self.headless = headless
        self.timeout = timeout
        # When a BrowserTransport owns the page, reuse it: one browser, one
        # cookie jar, one warm page. Two browsers double the startup cost and
        # can fight over the session.
        self.page_provider = page_provider
        self._pw = None
        self._browser = None
        self._context = None
        self._page = None
        self._lock = asyncio.Lock()

    async def _new_page(self):
        from playwright.async_api import async_playwright

        if self._pw is None:
            self._pw = await async_playwright().start()
        if self._browser is None or not self._browser.is_connected():
            self._browser = await self._pw.chromium.launch(
                headless=self.headless,
                args=["--disable-blink-features=AutomationControlled", "--no-sandbox"],
            )
        if self._context is None:
            self._context = await self._browser.new_context(
                locale="zh-CN",
                timezone_id="Asia/Shanghai",
                viewport={"width": 1440, "height": 900},
                user_agent=self.USER_AGENT,
            )
            await self._context.add_init_script(self.STEALTH)
        page = await self._context.new_page()
        await page.goto(self.ORIGIN, wait_until="domcontentloaded", timeout=int(self.timeout * 1000))
        try:
            await page.wait_for_function(self.SDK_READY, timeout=int(self.timeout * 1000))
        except Exception:
            # One reload: the SDK sometimes initialises only after the first paint.
            await page.reload(wait_until="domcontentloaded", timeout=int(self.timeout * 1000))
            await page.wait_for_function(self.SDK_READY, timeout=int(self.timeout * 1000))
        return page

    async def _ensure_page(self):
        if self.page_provider is not None:
            return await self.page_provider()
        if self._page is not None and not self._page.is_closed():
            return self._page
        self._page = await self._new_page()
        return self._page

    async def __call__(self, url: str) -> str:
        async with self._lock:
            page = await self._ensure_page()
            try:
                token = await page.evaluate(
                    "u => window.byted_acrawler.frontierSign({url: u})['X-Bogus']", url
                )
            except Exception:
                self._page = None
                page = await self._ensure_page()
                token = await page.evaluate(
                    "u => window.byted_acrawler.frontierSign({url: u})['X-Bogus']", url
                )
            if not token:
                raise SignError("SIGN_FAILED", "browser signer returned empty token")
            return token

    async def probe(self) -> dict:
        """Report what the live page currently exposes (used by /health/detail)."""
        page = await self._ensure_page()
        return await page.evaluate(
            """() => ({
                href: location.href,
                title: document.title,
                hasFrontierSign: typeof window.byted_acrawler?.frontierSign,
                keys: Object.keys(window.byted_acrawler || {}),
                scripts: [...document.scripts].map(s => s.src).filter(s => /webmssdk|acrawler|secsdk/i.test(s)),
            })"""
        )

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
