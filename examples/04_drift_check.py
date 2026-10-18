"""Detect drift after a page update and print the fix to apply."""

from douyin_api.sdk import DouyinApiClient

with DouyinApiClient("http://127.0.0.1:8787") as dy:
    report = dy.diagnostics()
    print("healthy:", report["healthy"])
    print("counts:", report["counts"])
    for row in report["profiles"]:
        print(f"  {row['profile']:<18} {row['verdict']:<16} {row['path']}")
    print("next action:", report["next_action"])
