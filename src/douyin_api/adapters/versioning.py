"""Detect the live page build so adapter changes are traceable."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone

_BUILD_RE = re.compile(r"runtime~client-entry\.([0-9a-f]{8})\.js")
_ANY_RE = re.compile(r"\.([0-9a-f]{8})\.js")


@dataclass(frozen=True)
class PageVersion:
    build: str
    script_count: int
    captured_at: str


def detect_version(script_urls: list[str]) -> PageVersion:
    build = "unknown"
    for url in script_urls:
        match = _BUILD_RE.search(url)
        if match:
            build = match.group(1)
            break
    if build == "unknown":
        for url in script_urls:
            match = _ANY_RE.search(url)
            if match:
                build = match.group(1)
                break
    return PageVersion(
        build=build,
        script_count=len(script_urls),
        captured_at=datetime.now(timezone.utc).isoformat(),
    )