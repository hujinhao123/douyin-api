"""FastAPI entrypoint.

Run locally:      python -m douyin_api.server
Run with uvicorn: uvicorn douyin_api.server:create_app --factory --port 8787
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from douyin_api.adapters.signature import BrowserSigner, SignerRegistry, StaticSigner
from douyin_api.auth.export import ExportService
from douyin_api.auth.qr_bridge import PageQRBridge
from douyin_api.auth.qr_login import QRLoginManager
from douyin_api.auth.session import SessionStore
from douyin_api.config import Settings
from douyin_api.deps import AppDeps, WriteCoordinator
from douyin_api.endpoints import (
    auth_routes,
    comment,
    diagnostics,
    feed,
    me,
    media,
    mix,
    search,
    session_import,
    social,
    user,
    video,
)
from douyin_api.errors import DouyinApiError
from douyin_api.redaction import RedactingFilter
from douyin_api.storage.secrets import default_protector
from douyin_api.security import install_auth_middleware
from douyin_api.transport.browser import BrowserTransport
from douyin_api.transport.client import DouyinClient

__all__ = ["AppDeps", "create_app", "main"]

logger = logging.getLogger("douyin_api")
logger.addFilter(RedactingFilter())


class PassportHTTP:
    """Minimal JSON transport used by the QR login state machine."""

    def __init__(self, base_url: str = "https://www.douyin.com", timeout: float = 15.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._client = httpx.AsyncClient(timeout=timeout, follow_redirects=False)

    async def get_json(self, path: str, params: dict[str, Any] | None = None, headers: dict[str, str] | None = None) -> dict[str, Any]:
        response = await self._client.get(
            f"{self.base_url}{path}",
            params=params or {},
            headers=headers or {"User-Agent": "Mozilla/5.0", "Referer": f"{self.base_url}/"},
        )
        response.raise_for_status()
        return response.json()


def build_signers(settings: Settings, page_provider=None) -> SignerRegistry:
    registry = SignerRegistry()
    if settings.signer_mode == "browser":
        registry.register(
            "browser",
            BrowserSigner(
                headless=settings.browser_headless,
                timeout=settings.request_timeout * 2,
                page_provider=page_provider,
            ),
        )
    if settings.signer_mode in {"browser", "static"}:
        bundle = settings.signer_bundle or (settings.data_dir / "signer" / "sign.js")
        registry.register("static", StaticSigner(bundle))
    return registry


def build_default_deps(settings: Settings) -> AppDeps:
    settings.ensure_dirs()
    master_key = settings.master_key_file or (settings.data_dir / "master.key")
    store = SessionStore(settings.session_path, protector=default_protector(master_key))
    if settings.login_mode == "page":
        qr_manager = PageQRBridge(
            settings.data_dir / "browser-profile",
            headless=settings.browser_headless,
            timeout=settings.request_timeout * 3,
        )
    else:
        qr_manager = QRLoginManager(PassportHTTP(timeout=settings.request_timeout))
    browser = BrowserTransport(
        headless=settings.browser_headless,
        timeout=settings.request_timeout * 3,
        profile_dir=settings.browser_profile or (settings.data_dir / "browser-profile"),
        cdp_url=settings.browser_cdp,
        executable_path=settings.browser_executable,
    )

    return AppDeps(
        session_store=store,
        export_service=ExportService(store, ttl_seconds=settings.export_ttl_seconds),
        qr_manager=qr_manager,
        client=DouyinClient(
            store,
            build_signers(settings, page_provider=browser.page),
            timeout=settings.request_timeout,
            mode=settings.transport_mode,
            browser=browser,
        ),
        writer=None,
        extra={
            "adapter_version": "2026.10.17",
            "signer": settings.signer_mode,
            "baseline_path": Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "live_contract.json",
        },
    )


def create_app(settings: Settings | None = None, *, deps: AppDeps | None = None) -> FastAPI:
    settings = settings or Settings()
    settings.validate()
    if deps is None:
        deps = build_default_deps(settings)
    deps.ensure_writer()

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        yield
        client = deps.client
        if hasattr(client, "aclose"):
            await client.aclose()
        signer = getattr(client, "signer", None)
        if signer is not None:
            for _, fn in getattr(signer, "_chain", []):
                close = getattr(fn, "close", None)
                if close is not None:
                    await close()

    app = FastAPI(
        lifespan=lifespan,
        title="<PRIVATE_ACCOUNT_NUMBER_b90765981cdba8db> Local API",
        version="0.1.0",
        description="Local <PRIVATE_ACCOUNT_NUMBER_b90765981cdba8db> web adapter: QR session bridge, signed aweme API, explicit cookie export.",
    )
    app.state.deps = deps
    app.state.settings = settings
    install_auth_middleware(app, settings)

    for module in (
        auth_routes,
        session_import,
        feed,
        search,
        video,
        media,
        user,
        social,
        comment,
        mix,
        me,
        diagnostics,
    ):
        app.include_router(module.router)

    @app.get("/health", tags=["system"])
    async def health() -> dict[str, Any]:
        return {
            "status": "ok",
            "version": "0.1.0",
            "session": deps.session_store.status(),
            "signers": getattr(getattr(deps.client, "signer", None), "names", []),
        }

    @app.exception_handler(DouyinApiError)
    async def douyin_error_handler(_: Request, exc: DouyinApiError) -> JSONResponse:
        return JSONResponse(status_code=exc.status, content=exc.payload())

    @app.exception_handler(Exception)
    async def unhandled_error_handler(_: Request, exc: Exception) -> JSONResponse:
        # A bare 500 hides the real cause from the device UI. Surface the class
        # and a trimmed message so a broken page/transport is diagnosable from
        # the client without tailing the server console.
        logger.exception("unhandled request error")
        return JSONResponse(
            status_code=500,
            content={
                "detail": {
                    "code": "UNHANDLED",
                    "type": type(exc).__name__,
                    "message": str(exc)[:300],
                }
            },
        )

    return app


def main() -> None:
    import uvicorn

    settings = Settings()
    uvicorn.run(
        create_app(settings),
        host=settings.host if not settings.allow_lan else "0.0.0.0",
        port=settings.port,
        log_level="info",
    )


if __name__ == "__main__":
    main()




