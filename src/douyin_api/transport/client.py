"""Signed HTTP client for the aweme web API."""

from __future__ import annotations

import json
from typing import Any
from urllib.parse import urlencode

import httpx

from douyin_api.adapters.request_profile import PROFILES, EndpointProfile, build_query
from douyin_api.adapters.signature import SignerRegistry, SignError
from douyin_api.errors import (
    BadParams,
    Blocked,
    DouyinApiError,
    FieldChanged,
    PrivacyHidden,
    RateLimited,
    SessionExpired,
    UpstreamError,
)
from douyin_api.transport.browser import BrowserTransport
from douyin_api.transport.headers import build_headers
from douyin_api.transport.retry import ErrorKind, classify_response, should_retry
from douyin_api.transport.throttle import Throttle

BASE_URL = "https://www.douyin.com"

_ERROR_MAP = {
    ErrorKind.SESSION_EXPIRED: SessionExpired,
    ErrorKind.RATE_LIMITED: RateLimited,
    ErrorKind.FIELD_CHANGED: FieldChanged,
    ErrorKind.BLOCKED: Blocked,
    ErrorKind.UPSTREAM_ERROR: UpstreamError,
    ErrorKind.PRIVACY_HIDDEN: PrivacyHidden,
    ErrorKind.BAD_PARAMS: BadParams,
}


class DouyinClient:
    def __init__(
        self,
        session_store,
        signer: SignerRegistry | None = None,
        *,
        base_url: str = BASE_URL,
        timeout: float = 15.0,
        transport: httpx.AsyncBaseTransport | None = None,
        max_retries: int = 2,
        mode: str = "browser",
        browser: BrowserTransport | None = None,
        throttle: Throttle | None = None,
    ):
        self.session_store = session_store
        self.signer = signer or SignerRegistry()
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries
        # "browser" routes the actual request through a live page, because a raw
        # socket is rejected on TLS fingerprint. "http" is kept for tests.
        self.mode = mode
        self.browser = browser
        self.throttle = throttle or Throttle()
        self._browser_cookie_fingerprint: tuple[tuple[str, str], ...] | None = None
        self._session_rejected_fingerprint: tuple[tuple[str, str], ...] | None = None
        self._http = httpx.AsyncClient(timeout=timeout, transport=transport, follow_redirects=False)

    async def aclose(self) -> None:
        await self._http.aclose()
        if self.browser is not None:
            await self.browser.close()

    def _cookies(self) -> dict[str, str]:
        state = self.session_store.load()
        return dict(state.cookies) if state else {}

    async def get(self, profile_key: str, params: dict[str, Any] | None = None, **_: Any) -> dict[str, Any]:
        return await self._send(self._profile(profile_key), params or {}, "GET")

    async def post(
        self,
        profile_key: str,
        params: dict[str, Any] | None = None,
        *,
        form: dict[str, Any] | None = None,
        **_: Any,
    ) -> dict[str, Any]:
        # Write endpoints carry their payload as an urlencoded body (verified:
        # like sends aweme_id=..&item_type=0&type=1). Sending it in the query
        # answers status_code 0 with status_msg "url does not match" and no effect.
        return await self._send(self._profile(profile_key), params or {}, "POST", form)

    @staticmethod
    def _profile(key: str) -> EndpointProfile:
        try:
            return PROFILES[key]
        except KeyError as exc:
            raise DouyinApiError("UNKNOWN_PROFILE", f"no request profile named {key!r}", status=500) from exc

    async def _send(
        self,
        profile: EndpointProfile,
        params: dict[str, Any],
        method: str,
        form: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        cookies = self._cookies()
        cookie_fingerprint = tuple(sorted(cookies.items()))
        if profile.requires_auth and self._session_rejected_fingerprint == cookie_fingerprint:
            raise SessionExpired("session is already marked rejected; refresh the login session before retrying")

        query = build_query(params)
        ms_token = cookies.get("msToken")
        if ms_token:
            query.setdefault("msToken", ms_token)
        url = f"{self.base_url}{profile.path}?{urlencode(query)}"

        attempt = 0
        while True:
            attempt += 1
            await self.throttle.acquire()
            try:
                if self.mode == "browser":
                    if self.browser is None:
                        self.browser = BrowserTransport(timeout=self.timeout)
                    # Install the session before signing, and only once per
                    # cookie jar. Reinstalling reloads the page and discards
                    # the live login state.
                    if self._browser_cookie_fingerprint != cookie_fingerprint:
                        await self.browser.set_cookies(cookies)
                        self._browser_cookie_fingerprint = cookie_fingerprint

                try:
                    token = await self.signer.sign(url)
                except SignError as exc:
                    raise DouyinApiError("SIGN_FAILED", exc.detail, status=502) from exc

                if self.mode == "browser":
                    form_body = urlencode(form) if form else None
                    envelope = await self.browser.fetch(
                        url, token, method=method, form=form_body
                    )
                    status_code = envelope["status"]
                    body = (envelope["text"] or "").encode("utf-8")
                    payload = envelope["json"]
                else:
                    headers = build_headers(cookies)
                    headers["X-Bogus"] = token
                    headers["x-secsdk-csrf-token"] = cookies.get("passport_csrf_token", "")
                    if method == "POST":
                        response = await self._http.post(url, headers=headers, content=urlencode(form or {}))
                    else:
                        response = await self._http.get(url, headers=headers)
                    status_code = response.status_code
                    body = response.content
                    try:
                        payload = json.loads(body.decode("utf-8")) if body else None
                    except (UnicodeDecodeError, json.JSONDecodeError):
                        payload = None

                kind = classify_response(status_code, body, payload)
                if kind is None:
                    if not isinstance(payload, dict):
                        raise FieldChanged("upstream returned a non-object payload")
                    self.throttle.reward()
                    return payload

                if kind is ErrorKind.SESSION_EXPIRED and profile.requires_auth:
                    self._session_rejected_fingerprint = cookie_fingerprint
                    raise SessionExpired(f"{kind.value} (HTTP {status_code})")

                if kind in (ErrorKind.BLOCKED, ErrorKind.RATE_LIMITED):
                    retry_after = None
                    if isinstance(payload, dict):
                        retry_after = payload.get("retry_after") or payload.get("retry_after_seconds")
                    self.throttle.penalise(retry_after)
                    raise _ERROR_MAP.get(kind, UpstreamError)(f"{kind.value} (HTTP {status_code})")

                if should_retry(kind) and attempt <= self.max_retries:
                    continue
                error_cls = _ERROR_MAP.get(kind, UpstreamError)
                raise error_cls(f"{kind.value} (HTTP {status_code})")
            finally:
                self.throttle.release()




