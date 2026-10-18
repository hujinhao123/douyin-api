from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from douyin_api.security import StreamTicketStore


def test_stream_ticket_is_bound_to_video_and_single_use():
    store = StreamTicketStore(secret="s" * 32, ttl_seconds=60)
    ticket = store.issue("video-1")
    assert store.redeem("video-1", ticket) is True
    assert store.redeem("video-1", ticket) is False


def test_stream_ticket_rejects_other_video():
    store = StreamTicketStore(secret="s" * 32, ttl_seconds=60)
    ticket = store.issue("video-1")
    assert store.redeem("video-2", ticket) is False


def test_stream_ticket_expires():
    store = StreamTicketStore(secret="s" * 32, ttl_seconds=-1)
    ticket = store.issue("video-1")
    assert store.redeem("video-1", ticket) is False
