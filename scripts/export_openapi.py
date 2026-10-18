from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from douyin_api.server import create_app

out = Path(__file__).resolve().parents[1] / "openapi.json"
app = create_app()
schema = app.openapi()
out.write_text(json.dumps(schema, ensure_ascii=False, indent=2), encoding="utf-8")
print("routes:", len(schema["paths"]), "->", out)
for path in sorted(schema["paths"]):
    methods = ",".join(sorted(m.upper() for m in schema["paths"][path]))
    print(f"  {methods:12} {path}")
