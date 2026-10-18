# B 站页面能力对齐表

这份表把计算器里的 B 站页面能力映射到抖音本机 API。它描述的是已经存在的抖音服务端路由和 Python SDK，不把尚未接入的前端页面写成已完成。

| B 站页面能力 | 抖音对应能力 | 状态 | 入口 |
|---|---|---|---|
| 首页推荐/分区流 | 精选、推荐、关注、推荐批量 | 已实现 | `/api/feed/*`、`featured()`、`recommend_batch()` |
| 搜索视频 | 关键词搜索、筛选参数 | 已实现 | `/api/search`、`search()` |
| 搜索 UP 主 | 搜索用户 | 已实现 | `/api/search/users`、`search_users()` |
| 视频详情 | 详情、作者、媒体、评论 | 已实现 | `/api/video/{id}/*` |
| 原播放地址 | `play_addr` 原始地址列表、清晰度列表 | 已实现 | `/api/video/{id}/media`、`video_media()` |
| 评论与楼中楼 | 评论分页、评论回复 | 已实现 | `/api/video/{id}/comments`、`/api/comment/{id}/replies` |
| 我的收藏 | 当前账号收藏 | 已实现 | `/api/me/collection`、`my_collection()` |
| 历史记录 | 当前账号观看历史 | 已实现 | `/api/me/history`、`my_history()` |
| 稍后看 | 当前账号稍后看 | 已实现 | `/api/me/watch-later`、`my_watch_later()` |
| 收藏合集 | 合集列表与合集视频 | 已实现 | `/api/me/mixes`、`/api/mix/{id}` |
| 登录 | 网页二维码桥接、持久化会话 | 已实现 | `/auth/qr/*`、`/auth/session` |
| 点赞/收藏/关注/评论 | 受控写操作 | 已实现 | `/api/...`，默认 `dry_run=true` |
| 弹幕 | 抖音网页读取链路未纳入当前范围 | 未接入 | — |
| 分 P 播放器控制 | 抖音单视频媒体地址已提供，播放器由调用方负责 | 调用方能力 | `video_media()` |

## 调用约定

1. 一个 API 进程复用一个浏览器 profile。
2. 调用方只使用 SDK，不自行拼接上游 URL 或重复生成签名。
3. `play_addr` / `download_addr` 是短时签名地址，拿到后立即使用，不写日志、不长期缓存。
4. 写接口先 `dry_run`，真正执行需要 `confirm=true` 和幂等键。
5. 遇到 403/412/429 或 `status_code=8`，服务端进入冷却/会话锁存，不继续突发重试。

## 仍需单独验证的部分

- 关注/粉丝列表是否可读，取决于目标账号隐私设置。
- 关注写操作在当前样本上仍是 `candidate`，未标成已验证。
- 推荐流、搜索和媒体地址在不同页面版本上的字段稳定性由漂移探测持续检查。
