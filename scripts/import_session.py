"""Import a session from a local JSON file, then delete the file.

This is the offline counterpart to the HTTP import endpoint: useful when a
cross-origin POST is blocked but you can write the cookie jar to disk yourself.

Usage:
    python scripts/import_session.py <path-to-json>
    (the file is removed on success)
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from douyin_api.auth.session import SessionState, SessionStore


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: python scripts/import_session.py <cookies.json>")
        return 2
    path = Path(argv[1])
    raw = json.loads(path.read_text(encoding="utf-8"))
    cookies = raw.get("cookies") if isinstance(raw, dict) else None
    if not isinstance(cookies, dict):
        print("expected {\"cookies\": {...}}")
        return 2
    cookies = {str(k): str(v) for k, v in cookies.items() if k and v}
    if not any(k in cookies for k in ("sessionid", "sessionid_ss", "sid_tt")):
        print("no session cookie present")
        return 2

    store = SessionStore(Path(__file__).parent / ".login-session.bin")
    store.save(SessionState(cookies=cookies, adapter_version="2026.10.17", signer="browser"))
    path.unlink(missing_ok=True)
    print(f"imported {len(cookies)} cookies -> {store.path}")
    print(f"status: {store.status()}")
    return 0


raise SystemExit(main(sys.argv))
