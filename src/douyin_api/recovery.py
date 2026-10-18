"""Drift detection: the mechanism that makes page changes recoverable in minutes.

When <PRIVATE_ACCOUNT_NUMBER_b90765981cdba8db> ships a new bundle, one or more of these break:

  * a request path starts answering 404            -> PATH_CHANGED
  * the response loses a key the adapter reads     -> FIELD_CHANGED
  * the signer stops producing a token             -> SIGN_FAILED
  * cookies are no longer accepted                 -> AUTH_CHANGED
  * pagination field changes (cursor <-> max_cursor) -> PAGINATION_CHANGED

`probe_all` runs every profile against the live API and diffs the result with a
recorded baseline. The report names the exact profile to fix, so recovery is
"edit one adapter entry, rerun the probe", not "re-reverse the whole client".
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from douyin_api.adapters.request_profile import PROFILES, EndpointProfile

# Minimal parameters that make each profile answer without a target object.
MINIMAL_PARAMS: dict[str, dict[str, Any]] = {
    "feed.featured": {"count": 5, "refresh_index": 1, "feed_source": 0},
    "feed.recommend": {"count": 5, "refresh_index": 1, "feed_source": 1},
    "feed.following": {"count": 5, "level": 1},
    "feed.hot_search": {"detail_list": 1, "source": 6, "board_type": 0},
    "search.general": {
        "keyword": "test",
        "cursor": 0,
        "count": 5,
        "search_channel": "aweme_general",
        "search_source": "normal_search",
        "query_correct_type": 1,
        "sort_type": 0,
        "publish_time": 0,
        "filter_duration": "0",
    },
}

PAGINATION_FIELDS = ("cursor", "max_cursor", "min_cursor", "has_more", "total")


@dataclass
class ProfileProbe:
    profile: str
    path: str
    http: int | None = None
    status_code: Any = None
    status_msg: str | None = None
    top_level_keys: list[str] = field(default_factory=list)
    list_key_present: bool | None = None
    list_len: int | None = None
    pagination: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    verdict: str = "UNKNOWN"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _diff_keys(baseline: list[str], current: list[str]) -> dict[str, list[str]]:
    base, cur = set(baseline), set(current)
    return {"missing": sorted(base - cur), "added": sorted(cur - base)}


def classify_probe(
    probe: ProfileProbe,
    baseline: dict[str, Any] | None,
) -> str:
    """Turn one probe into a verdict the operator can act on."""
    if probe.error:
        if "SIGN" in probe.error.upper():
            return "SIGN_FAILED"
        return "TRANSPORT_ERROR"
    if probe.http == 404:
        return "PATH_CHANGED"
    if probe.http in (401, 403) or probe.status_code in (8, 2154, 10232):
        return "AUTH_CHANGED"
    if probe.status_code in (5,):
        return "PARAMS_CHANGED"
    if baseline:
        baseline_keys = baseline.get("top_level") or baseline.get("top_level_keys") or []
        if baseline_keys:
            diff = _diff_keys(baseline_keys, probe.top_level_keys)
            if diff["missing"]:
                return "FIELD_CHANGED"
        expected_list = baseline.get("list_key") or baseline.get("object_key")
        if expected_list and probe.list_key_present is False:
            return "FIELD_CHANGED"
    if probe.http == 200 and probe.status_code == 0:
        return "OK"
    if probe.http == 200 and probe.status_code is None:
        return "FIELD_CHANGED"
    return "UNKNOWN"


async def probe_profile(client: Any, key: str) -> ProfileProbe:
    profile: EndpointProfile = PROFILES[key]
    params = MINIMAL_PARAMS.get(key, {})
    probe = ProfileProbe(profile=key, path=profile.path)
    try:
        data = await client.get(key, params)
    except Exception as exc:  # noqa: BLE001 - every failure becomes a verdict
        probe.error = f"{type(exc).__name__}: {exc}"[:300]
        return probe
    probe.http = 200
    probe.status_code = data.get("status_code")
    probe.status_msg = data.get("status_msg") or None
    probe.top_level_keys = sorted(data.keys())
    if profile.response_key:
        value = data.get(profile.response_key)
        probe.list_key_present = value is not None
        if isinstance(value, list):
            probe.list_len = len(value)
        elif isinstance(value, dict):
            probe.list_len = len(value)
    probe.pagination = {k: data.get(k) for k in PAGINATION_FIELDS if k in data}
    return probe


async def probe_all(client: Any, keys: list[str] | None = None) -> list[ProfileProbe]:
    targets = keys or [
        k
        for k in PROFILES
        if k in MINIMAL_PARAMS  # only profiles with a safe minimal parameter set
    ]
    return [await probe_profile(client, k) for k in targets]


def build_report(probes: list[ProfileProbe], baseline: dict[str, Any] | None = None) -> dict[str, Any]:
    baseline = baseline or {}
    rows = []
    for probe in probes:
        base = (baseline.get("responses") or {}).get(_baseline_key(probe.profile))
        probe.verdict = classify_probe(probe, base)
        rows.append(probe.to_dict())
    counts: dict[str, int] = {}
    for row in rows:
        counts[row["verdict"]] = counts.get(row["verdict"], 0) + 1
    return {
        "healthy": all(r["verdict"] == "OK" for r in rows),
        "counts": counts,
        "profiles": rows,
        "next_action": _next_action(rows),
    }


def _baseline_key(profile_key: str) -> str:
    return {
        "feed.featured": "feed_tab",
        "feed.recommend": "feed_tab",
        "video.detail": "video_detail",
        "video.comments": "video_comments",
        "user.profile": "user_profile",
        "user.posts": "user_posts",
        "search.general": "search_general",
        "user.following": "user_following",
        "user.followers": "user_followers",
        "feed.hot_search": "hot_search",
    }.get(profile_key, profile_key)


def _next_action(rows: list[dict[str, Any]]) -> str:
    verdicts = {r["verdict"] for r in rows}
    if verdicts == {"OK"}:
        return "none"
    if "AUTH_CHANGED" in verdicts:
        return "re-run QR login (POST /auth/qr/start), then rerun the probe"
    if "SIGN_FAILED" in verdicts:
        return "check the signer: open https://www.douyin.com and confirm window.byted_acrawler.frontierSign exists"
    if "PATH_CHANGED" in verdicts:
        return "one or more paths moved: search the page bundle for the new /aweme/v1/web/... path and update PROFILES"
    if "FIELD_CHANGED" in verdicts:
        return "a response key changed: update the matching normalize_* function and live_contract.json"
    if "PARAMS_CHANGED" in verdicts:
        return "a required parameter changed: capture one request from DevTools and update MINIMAL_PARAMS"
    return "inspect profiles with non-OK verdicts"


def load_baseline(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))
