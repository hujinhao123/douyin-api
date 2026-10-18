"""B 站模块风格的抖音读取示例。

这个示例只调用读接口，不点赞、不收藏、不关注、不评论，也不导出 cookie。
服务端负责登录态、页面签名、请求节奏与冷却；调用方只使用稳定的 SDK 方法。
"""

from __future__ import annotations

from douyin_api.sdk import DouyinApiClient


def main() -> int:
    with DouyinApiClient("http://127.0.0.1:8787") as dy:
        session = dy.session()
        if session.get("status") != "active":
            print("先完成二维码登录，再运行本示例。")
            return 2

        home = dy.recommend_batch(want=10, rounds=8, count=10)
        print("推荐视频:", len(home["items"]), "轮数:", home["rounds_used"])
        if not home["items"]:
            print("推荐流为空。")
            return 0

        first = home["items"][0]
        video_id = first["id"]
        print("首条:", video_id, first.get("desc", "")[:40])

        detail = dy.video(video_id)
        media = dy.video_media(video_id)
        print("作者:", (detail["video"].get("author") or {}).get("nickname"))
        print("原播放地址数量:", len(media["media"].get("play_addr") or []))
        print("原下载地址数量:", len(media["media"].get("download_addr") or []))

        comments = dy.video_comments(video_id, count=10)
        print("评论:", len(comments["items"]), "/", comments["total"])

        me = dy.me()
        print("当前账号:", (me.get("user") or {}).get("nickname"))
        print("收藏数:", (me.get("counts") or {}).get("collect"))
        print("我的收藏条数:", len(dy.my_collection(count=5)["items"]))
        print("历史条数:", len(dy.my_history(count=5)["items"]))
        print("稍后看条数:", len(dy.my_watch_later(count=5)["items"]))
        print("合集条数:", len(dy.my_mixes(count=5)["items"]))

        keyword = (first.get("desc") or "抖音")[:8]
        print("搜索视频:", len(dy.search(keyword, count=5)["items"]))
        print("搜索用户:", len(dy.search_users(keyword, count=5)["items"]))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
