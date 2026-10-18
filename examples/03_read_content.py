"""Read content with an existing session; demonstrate write dry-run."""

from douyin_api.sdk import DouyinApiClient

with DouyinApiClient("http://127.0.0.1:8787") as dy:
    feed = dy.featured(count=5)
    print("featured items:", len(feed["items"]))
    if not feed["items"]:
        raise SystemExit("empty feed")

    video_id = feed["items"][0]["id"]
    detail = dy.video(video_id)
    print("video:", detail["video"]["desc"][:40])
    print("author:", detail["video"]["author"]["nickname"])

    comments = dy.video_comments(video_id, count=3)
    print("comments:", len(comments["items"]), "of", comments["total"])

    media = dy.video_media(video_id)
    print("play urls:", len(media["media"]["play_addr"]))
    print("bitrates:", [b["gear_name"] for b in media["media"]["bit_rates"]])

    # Writes default to dry_run and never touch <PRIVATE_ACCOUNT_NUMBER_b90765981cdba8db>.
    preview = dy.like(video_id)
    print("like preview (no request sent):", preview["dry_run"], preview["action"])
