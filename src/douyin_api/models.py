"""Request/response models exposed through OpenAPI."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class WriteRequest(BaseModel):
    dry_run: bool = Field(True, description="Preview the action without touching upstream.")
    confirm: bool = Field(False, description="Must be true to actually perform a write.")
    idempotency_key: str | None = Field(
        None, description="Replays with the same key return the first result and do not re-send."
    )


class WriteResult(BaseModel):
    dry_run: bool
    action: str
    params: dict[str, Any]
    result: dict[str, Any] | None = None
    replayed: bool = False


class ExportTicketModel(BaseModel):
    ticket: str
    issued_at: str
    expires_at: str


class RedeemRequest(BaseModel):
    ticket: str


class FeedResponse(BaseModel):
    items: list[dict[str, Any]]
    cursor: int = 0
    has_more: bool = False


class SearchResponse(BaseModel):
    items: list[dict[str, Any]]
    cursor: int = 0
    has_more: bool = False
    search_id: str | None = None


class CommentResponse(BaseModel):
    items: list[dict[str, Any]]
    cursor: int = 0
    total: int = 0
    has_more: bool = False


class SessionSummary(BaseModel):
    status: Literal["active", "expired", "revoked", "missing"]
    created_at: str | None = None
    expires_at: str | None = None
    adapter_version: str | None = None
    signer: str | None = None
    user: dict[str, Any] | None = None
    cookie_names: list[str] = Field(default_factory=list)


class QRStartResponse(BaseModel):
    qr_id: str
    status: str
    image_base64: str
    qr_url: str
    expires_in_seconds: int
    poll_interval_seconds: int


class QRStateResponse(BaseModel):
    qr_id: str
    status: str
    redirect_url: str | None = None
    message: str | None = None