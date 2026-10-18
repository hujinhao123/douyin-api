"""Thin Python client for the local <PRIVATE_ACCOUNT_NUMBER_b90765981cdba8db> API.

This is what application code should import. It never touches <PRIVATE_ACCOUNT_NUMBER_b90765981cdba8db> directly:
the local service owns the session, the signer, and the request profiles.
"""

from __future__ import annotations

from typing import Any

import httpx


class DouyinApiClient:
    def __init__(
        self,
        base_url: str = "http://127.0.0.1:8787",
        timeout: float = 60.0,
        transport: httpx.BaseTransport | None = None,
    ):
        self.base_url = base_url.rstrip("/")
        self._http = httpx.Client(base_url=self.base_url, timeout=timeout, transport=transport)

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> "DouyinApiClient":
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()

    # -- low level ---------------------------------------------------------
    def _get(self, path: str, **params: Any) -> Any:
        r = self._http.get(path, params={k: v for k, v in params.items() if v is not None})
        r.raise_for_status()
        return r.json()

    def _post(self, path: str, json: dict | None = None, **params: Any) -> Any:
        r = self._http.post(path, json=json or {}, params={k: v for k, v in params.items() if v is not None})
        r.raise_for_status()
        return r.json()

    # -- system ------------------------------------------------------------
    def health(self) -> dict:
        return self._get("/health")

    def openapi(self) -> dict:
        return self._get("/openapi.json")

    def diagnostics(self) -> dict:
        """Drift probe: which endpoint profiles still behave as recorded."""
        return self._get("/diagnostics/probe")

    def version(self) -> dict:
        return self._get("/diagnostics/version")

    # -- auth --------------------------------------------------------------
    def start_qr(self) -> dict:
        return self._post("/auth/qr/start")

    def qr_status(self, qr_id: str) -> dict:
        return self._get(f"/auth/qr/{qr_id}/status")

    def qr_image(self, qr_id: str) -> bytes:
        r = self._http.get(f"/auth/qr/{qr_id}/image")
        r.raise_for_status()
        return r.content

    def cancel_qr(self, qr_id: str) -> dict:
        return self._post(f"/auth/qr/{qr_id}/cancel")

    def session(self) -> dict:
        return self._get("/auth/session")

    def issue_export_ticket(self) -> dict:
        return self._post("/auth/session/export")

    def redeem_export_ticket(self, ticket: str) -> dict:
        return self._post("/auth/session/export/redeem", {"ticket": ticket})

    def revoke_session(self) -> dict:
        return self._post("/auth/session/revoke")

    # -- feed --------------------------------------------------------------
    def featured(self, count: int = 10) -> dict:
        return self._get("/api/feed/featured", count=count)

    def recommend(self, count: int = 10) -> dict:
        return self._get("/api/feed/recommend", count=count)

    def following_feed(self, count: int = 10) -> dict:
        return self._get("/api/feed/following", count=count)

    def recommend_batch(self, want: int = 10, rounds: int = 8, count: int = 10) -> dict:
        """Accumulate and deduplicate several small recommendation pages."""
        return self._get("/api/feed/recommend/batch", want=want, rounds=rounds, count=count)

    def hot_search(self, limit: int = 30) -> dict:
        return self._get("/api/feed/hot-search", limit=limit)

    # -- search ------------------------------------------------------------
    def search(self, keyword: str, cursor: int = 0, count: int = 10, **filters: Any) -> dict:
        return self._get("/api/search", keyword=keyword, cursor=cursor, count=count, **filters)

    def search_users(self, keyword: str, offset: int = 0, count: int = 10, search_id: str | None = None) -> dict:
        return self._get(
            "/api/search/users",
            keyword=keyword,
            offset=offset,
            count=count,
            search_id=search_id,
        )

    # -- video -------------------------------------------------------------
    def video(self, video_id: str) -> dict:
        return self._get(f"/api/video/{video_id}")

    def video_author(self, video_id: str) -> dict:
        return self._get(f"/api/video/{video_id}/author")

    def video_comments(self, video_id: str, cursor: int = 0, count: int = 20) -> dict:
        return self._get(f"/api/video/{video_id}/comments", cursor=cursor, count=count)

    def video_media(self, video_id: str) -> dict:
        return self._get(f"/api/video/{video_id}/media")

    # -- user --------------------------------------------------------------
    def user(self, sec_user_id: str) -> dict:
        return self._get(f"/api/user/{sec_user_id}")

    def user_videos(self, sec_user_id: str, cursor: int = 0, count: int = 20) -> dict:
        return self._get(f"/api/user/{sec_user_id}/videos", cursor=cursor, count=count)

    def user_following(self, sec_user_id: str, cursor: int = 0, count: int = 20) -> dict:
        return self._get(f"/api/user/{sec_user_id}/following", cursor=cursor, count=count)

    def user_followers(self, sec_user_id: str, cursor: int = 0, count: int = 20) -> dict:
        return self._get(f"/api/user/{sec_user_id}/followers", cursor=cursor, count=count)

    # -- current account / local-like collections ------------------------
    def me(self) -> dict:
        return self._get("/api/me")

    def my_collection(self, cursor: int = 0, count: int = 18) -> dict:
        return self._get("/api/me/collection", cursor=cursor, count=count)

    def my_history(self, cursor: int = 0, count: int = 20) -> dict:
        return self._get("/api/me/history", cursor=cursor, count=count)

    def my_watch_later(self, cursor: int = 0, count: int = 20) -> dict:
        return self._get("/api/me/watch-later", cursor=cursor, count=count)

    def my_mixes(self, cursor: int = 0, count: int = 20) -> dict:
        return self._get("/api/me/mixes", cursor=cursor, count=count)

    # -- comments / collections -------------------------------------------
    def comment_replies(self, comment_id: str, *, item_id: str, cursor: int = 0, count: int = 10) -> dict:
        return self._get(
            f"/api/comment/{comment_id}/replies",
            item_id=item_id,
            cursor=cursor,
            count=count,
        )

    def mix_videos(self, mix_id: str, cursor: int = 0, count: int = 20) -> dict:
        return self._get(f"/api/mix/{mix_id}", cursor=cursor, count=count)

    # -- social (write) ----------------------------------------------------
    def like(self, video_id: str, *, dry_run: bool = True, confirm: bool = False, key: str | None = None) -> dict:
        return self._post(f"/api/video/{video_id}/like", self._write(dry_run, confirm, key))

    def unlike(self, video_id: str, *, dry_run: bool = True, confirm: bool = False, key: str | None = None) -> dict:
        r = self._http.request("DELETE", f"/api/video/{video_id}/like", json=self._write(dry_run, confirm, key))
        r.raise_for_status()
        return r.json()

    def favorite(self, video_id: str, *, dry_run: bool = True, confirm: bool = False, key: str | None = None) -> dict:
        return self._post(f"/api/video/{video_id}/favorite", self._write(dry_run, confirm, key))

    def unfavorite(self, video_id: str, *, dry_run: bool = True, confirm: bool = False, key: str | None = None) -> dict:
        r = self._http.request("DELETE", f"/api/video/{video_id}/favorite", json=self._write(dry_run, confirm, key))
        r.raise_for_status()
        return r.json()

    def follow(self, sec_user_id: str, *, dry_run: bool = True, confirm: bool = False, key: str | None = None) -> dict:
        return self._post(f"/api/user/{sec_user_id}/follow", self._write(dry_run, confirm, key))

    def unfollow(self, sec_user_id: str, *, dry_run: bool = True, confirm: bool = False, key: str | None = None) -> dict:
        r = self._http.request("DELETE", f"/api/user/{sec_user_id}/follow", json=self._write(dry_run, confirm, key))
        r.raise_for_status()
        return r.json()

    def comment(self, video_id: str, text: str, *, dry_run: bool = True, confirm: bool = False, key: str | None = None) -> dict:
        return self._post(f"/api/video/{video_id}/comment", self._write(dry_run, confirm, key), text=text)

    @staticmethod
    def _write(dry_run: bool, confirm: bool, key: str | None) -> dict:
        return {"dry_run": dry_run, "confirm": confirm, "idempotency_key": key}
