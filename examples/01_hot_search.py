"""Minimal SDK example: public hot search (no login required)."""

from douyin_api.sdk import DouyinApiClient

with DouyinApiClient("http://127.0.0.1:8787") as dy:
    print("health:", dy.health())
    board = dy.hot_search(limit=5)
    print("hot items:", board["total"])
    for item in board["items"]:
        print(f"  {item['position']}. {item['word']}  ({item['hot_value']})")
