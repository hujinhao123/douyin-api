# 接口文档

Base URL：`http://127.0.0.1:8787`
交互式文档：`/docs`（Swagger）· `/redoc` · `/openapi.json`

所有错误响应统一为：

```json
{"detail": {"code": "SESSION_MISSING", "message": "...", "detail": {}}}
```

---

## 系统

### `GET /health`

```json
{"status": "ok", "version": "0.1.0", "session": "missing", "signers": ["browser", "static"]}
```

`session` 取值：`active` | `expired` | `revoked` | `missing`。

---

## 认证

### `POST /auth/qr/start`

打开真实登录弹窗并抓取二维码。无参数。

```json
{
  "qr_id": "49f6f7e6989747869eca086bcde7b430",
  "status": "created",
  "image_base64": "iVBORw0KGgo...",
  "qr_url": "",
  "expires_in_seconds": 300,
  "poll_interval_seconds": 2
}
```

失败：`502 QR_START_FAILED`（例如页面没加载出登录入口）。

### `GET /auth/qr/{qr_id}/image`

直接返回 `image/png`，用于 `<img src>` 或扫码窗口。

失败：`404 QR_NOT_FOUND` · `409 QR_IMAGE_UNAVAILABLE`。

### `GET /auth/qr/{qr_id}/status`

```json
{"qr_id": "...", "status": "scanned", "redirect_url": null, "message": null}
```

`status` 状态机：

```
created ──scan──> scanned ──confirm──> confirmed
   │                  │
   └──── timeout ─────┴──> expired
   └──── cancel ──────────> cancelled
   └──── error ───────────> failed
```

`confirmed` 时服务端自动把 cookie 写入本地会话（DPAPI 加密），无需额外调用。

### `POST /auth/qr/{qr_id}/cancel`

关闭弹窗并把状态置为 `cancelled`。

### `GET /auth/session`

```json
{
  "status": "active",
  "created_at": "2026-10-17T09:12:00+00:00",
  "expires_at": "2026-11-16T09:12:00+00:00",
  "adapter_version": "2026.10.17",
  "signer": "browser",
  "user": null,
  "cookie_names": ["sessionid", "ttwid", "msToken"]
}
```

**只返回 cookie 名称，不返回值。**

### `POST /auth/session/export`

签发一次性导出票据。

```json
{"ticket": "Wq3...", "issued_at": "...", "expires_at": "..."}
```

无有效会话：`403 NO_ACTIVE_SESSION`。

### `POST /auth/session/export/redeem`

```json
// 请求
{"ticket": "Wq3..."}
// 响应（仅此一次）
{"cookies": {"sessionid": "...", "ttwid": "..."}}
```

票据已用过 / 已过期 / 已 revoke：`403 EXPORT_DENIED`。

### `POST /auth/session/revoke`

清空会话文件并作废所有未使用票据。

```json
{"status": "revoked"}
```

---

## 内容

### `GET /api/feed/hot-search?limit=30`

**无需登录。** 用于健康检查与签名自检。

```json
{
  "items": [{"word": "北京大雨", "hot_value": 11760079, "position": 2, "sentence_id": "..."}],
  "total": 51
}
```

### `GET /api/feed/featured?count=10`

精选流。

```json
{"items": [{"id": "...", "desc": "...", "author": {...}, "stats": {...}, "video": {...}}], "cursor": 0, "has_more": false}
```

### `GET /api/feed/recommend?count=10`

推荐流，结构同上。

### `GET /api/feed/following?count=10`

关注流，结构同上。

### `GET /api/search?keyword=xxx&cursor=0&count=10`

可选参数：`sort_type`（0综合/1最新）、`publish_time`（0不限/1一天/7一周/180半年）、`filter_duration`、`search_channel`。

```json
{"items": [...], "cursor": 10, "has_more": true, "search_id": "..."}
```

### `GET /api/video/{video_id}`

```json
{"video": {"id": "...", "desc": "...", "author": {...}, "stats": {...}, "video": {...}}}
```

`video_id` 是 `aweme_id`（19 位数字字符串）。不存在：`404 VIDEO_NOT_FOUND`。

### `GET /api/video/{video_id}/author`

```json
{"author": {"uid": "...", "sec_uid": "MS4wLj...", "nickname": "...", "unique_id": "...", "signature": "...", "avatar": "https://...", "follower_count": 123, "following_count": 4, "aweme_count": 56, "is_follow": false}}
```

### `GET /api/video/{video_id}/comments?cursor=0&count=20`

```json
{"items": [{"id": "cid", "text": "...", "create_time": 1700000000, "digg_count": 12, "reply_comment_total": 3, "user": {...}}], "cursor": 5, "total": 573, "has_more": true}
```

`cursor` 是整数偏移量，翻页时把上次的 `cursor` 传回去。

### `GET /api/video/{video_id}/media`

```json
{
  "media": {
    "aweme_id": "...",
    "duration_ms": 15000,
    "cover": "https://...",
    "dynamic_cover": "https://...",
    "play_addr": ["https://...", "https://..."],
    "download_addr": ["https://..."],
    "bit_rates": [{"gear_name": "1080p", "bit_rate": 3000, "quality_type": 1, "width": 1920, "height": 1080, "urls": ["https://..."], "data_size": 1234567}],
    "music": {"title": "...", "play_url": "https://..."}
  }
}
```

地址带签名和过期时间，**不要缓存超过几小时**。

### `GET /api/user/{sec_user_id}`

`sec_user_id` 是 `MS4wLjABAAAA...` 形式的字符串（不是数字 uid）。

```json
{"user": {"uid": "...", "sec_uid": "...", "nickname": "...", "unique_id": "...", "signature": "...", "avatar": "...", "follower_count": 0, "following_count": 0, "aweme_count": 0, "is_follow": false}}
```

### `GET /api/user/{sec_user_id}/videos?cursor=0&count=20`

```json
{"items": [...], "cursor": 1791594000000, "has_more": true}
```

**注意**：`cursor` 这里是毫秒时间戳（来自上游 `max_cursor`），不是整数偏移。

### `GET /api/user/{sec_user_id}/following?cursor=0&count=20`

```json
{"items": [...], "cursor": 20, "has_more": true, "total": 0}
```

对方设置了隐私：`403 PRIVACY_HIDDEN`（`status_code: 2096`）。**这不是登录失效，不要提示用户重新扫码。**

### `GET /api/user/{sec_user_id}/followers?cursor=0&count=20`

结构同上。

---

## 写操作

所有写操作请求体：

```json
{"dry_run": true, "confirm": false, "idempotency_key": "my-op-1"}
```

| 方法 | 路径 | 说明 |
|---|---|---|
| `POST` | `/api/video/{video_id}/like` | 点赞 |
| `DELETE` | `/api/video/{video_id}/like` | 取消点赞 |
| `POST` | `/api/video/{video_id}/favorite` | 收藏 |
| `DELETE` | `/api/video/{video_id}/favorite` | 取消收藏 |
| `POST` | `/api/user/{sec_user_id}/follow` | 关注 |
| `DELETE` | `/api/user/{sec_user_id}/follow` | 取关 |
| `POST` | `/api/video/{video_id}/comment?text=...` | 评论（文本走 query） |

行为：

- `dry_run=true`（默认）→ 返回预览，**不请求上游**：`{"dry_run": true, "action": "social.digg", "params": {...}}`
- `dry_run=false` 且 `confirm=false` → `409 CONFIRM_REQUIRED`
- `dry_run=false` 且 `confirm=true` → 真正执行
- 同一 `idempotency_key` 第二次 → 返回首次结果并带 `"replayed": true`

---

## 诊断

### `GET /diagnostics/probe`

跑所有安全可探测的 profile，给出漂移结论。

```json
{
  "healthy": true,
  "counts": {"OK": 5},
  "profiles": [
    {"profile": "feed.featured", "path": "/aweme/v1/web/tab/feed/", "http": 200, "status_code": 0, "top_level_keys": [...], "list_key_present": true, "list_len": 2, "pagination": {...}, "verdict": "OK", "error": null}
  ],
  "next_action": "none"
}
```

`verdict` 见交接文档第 7 节。

### `GET /diagnostics/version`

```json
{"adapter_version": "2026.10.17", "signer": "browser", "signers_available": ["browser", "static"], "session": "active"}
```

---

## 错误码总表

| HTTP | code | 含义 |
|---|---|---|
| 400 | `BAD_PARAMS` | 上游认为缺参数（`status_code: 5`） |
| 401 | `SESSION_MISSING` | 没有登录会话 |
| 401 | `SESSION_EXPIRED` | 上游判定登录失效（8/2154/10232） |
| 403 | `PRIVACY_HIDDEN` | 对方隐私设置（2096） |
| 403 | `NO_ACTIVE_SESSION` | 导出时会话不可用 |
| 403 | `EXPORT_DENIED` | 票据无效/已用/已过期 |
| 403 | `BLOCKED` | 上游风控（HTTP 403/412） |
| 404 | `VIDEO_NOT_FOUND` / `USER_NOT_FOUND` / `QR_NOT_FOUND` | 对象不存在 |
| 409 | `CONFIRM_REQUIRED` | 写操作缺少确认 |
| 409 | `QR_IMAGE_UNAVAILABLE` | 二维码图片不可用 |
| 429 | `RATE_LIMITED` | 上游限流 |
| 502 | `FIELD_CHANGED` | 响应结构变了（需要更新适配器） |
| 502 | `SIGN_FAILED` | 签名生成失败 |
| 502 | `UPSTREAM_ERROR` | 上游 5xx |

---

## 环境变量

服务启动前可用环境变量覆盖默认配置（见 `src/douyin_api/config.py`）：

| 变量 | 默认 | 说明 |
|---|---|---|
| `DOUYIN_API_DATA` | `%LOCALAPPDATA%/douyin-api` | 数据目录（会话、浏览器 profile、证据） |
| `DOUYIN_PORT` | `8787` | 监听端口 |
| `DOUYIN_ALLOW_LAN` | `false` | 允许非本机访问 |
| `DOUYIN_HEADLESS` | `true` | 浏览器是否无头；`0/false/no/off` 关闭 |
| `DOUYIN_BROWSER_CDP` | 空 | 连接已运行的浏览器，如 `http://127.0.0.1:9222` |
| `DOUYIN_BROWSER_PROFILE` | `<data>/browser-profile` | 持久化 profile 目录 |
| `DOUYIN_SIGNER` | `browser` | `browser` / `static` / `off` |
| `DOUYIN_LOGIN` | `page` | `page`（真实弹窗）/ `http`（纯 HTTP 状态机） |
| `DOUYIN_TRANSPORT` | `browser` | `browser`（默认）/ `http`（仅测试） |
| `DOUYIN_TIMEOUT` | `15` | 请求超时秒数 |
| `DOUYIN_EXPORT_TTL` | `120` | cookie 导出票据有效期秒数 |
| `DOUYIN_IMPORT_TOKEN` | 空 | 启用 `/auth/session/import` 时的一次性令牌 |


---

## 我自己的账号（`/api/me`）

这一组接口操作的是**当前登录账号**，不需要传 sec_uid。

### `GET /api/me`

```json
{
  "user": {"uid": "...", "sec_uid": "MS4wLjABAAAA...", "nickname": "...", "unique_id": "..."},
  "counts": {
    "collect": {"2": 435},
    "watch_later": 2,
    "favoriting": 31509,
    "following": 2810,
    "followers": 467,
    "works": 6
  }
}
```

`counts.collect` 的 key 是 `item_type`（`2` = 视频收藏）。

### `GET /api/me/collection`

我的收藏列表。上游是 `/aweme/v1/web/aweme/favorite/`。

| 参数 | 默认 | 说明 |
|---|---|---|
| `cursor` | 0 | 传上一次返回的 `cursor`（上游字段名 `max_cursor`） |
| `count` | 18 | 每页条数 |

必须带 `cut_version=1`，否则上游不回数据。

### `GET /api/me/history`

观看历史。上游 `/aweme/v1/web/history/read/`，分页用 `max_cursor`。

### `GET /api/me/watch-later`

稍后再看。上游 `/aweme/v1/web/watchlater/list/`。
**注意**：响应键是 `items`（不是 `aweme_list`），游标字段是 `offset`（不是 `cursor`），本接口已做归一化。

### `GET /api/me/mixes`

我收藏的合集。上游 `/aweme/v1/web/mix/listcollection/`，响应键是 `mix_infos`。

```json
{
  "items": [{"mix_id": "...", "name": "...", "cover": "...", "item_count": 12}],
  "cursor": 0,
  "has_more": true
}
```

---

## 评论回复

### `GET /api/comment/{comment_id}/replies`

楼中楼（二级回复）。

| 参数 | 必填 | 说明 |
|---|---|---|
| `item_id` | ✅ | 所属视频的 aweme_id。评论 id 不跨视频唯一，必须显式给 |
| `cursor` | | 默认 0 |
| `count` | | 默认 10 |

上游 `/aweme/v1/web/comment/list/reply/`，必须带 `cut_version=1` 且 URL 里要有 `a_bogus`，否则上游**挂住不返回**（既不是 4xx 也不是 5xx，就是没有响应）。

---

## 搜索用户

### `GET /api/search/users`

| 参数 | 默认 | 说明 |
|---|---|---|
| `keyword` | 必填 | |
| `offset` | 0 | 上游用 offset 分页，不是 cursor |
| `count` | 10 | |
| `search_id` | | 第二页起带上第一页返回的 `search_id` |

上游 `/aweme/v1/web/discover/search/`，必须 `search_channel=aweme_user_web`。

---

## 合集

### `GET /api/mix/{mix_id}`

某个合集里的视频列表。上游 `/aweme/v1/web/mix/aweme/`。

---

## Python SDK 对齐层

`src/douyin_api/sdk.py` 提供和 B 站页面模块相同的按业务分组调用方式，调用方不需要自己拼接路径：

| 页面能力 | SDK 方法 |
|---|---|
| 首页精选/推荐/关注 | `featured()` / `recommend()` / `following_feed()` |
| 推荐流累积 | `recommend_batch(want=10, rounds=8, count=10)` |
| 热搜与搜索 | `hot_search()` / `search()` / `search_users()` |
| 视频详情/作者/评论/媒体 | `video()` / `video_author()` / `video_comments()` / `video_media()` |
| 当前账号 | `me()` |
| 我的收藏/历史/稍后看/合集 | `my_collection()` / `my_history()` / `my_watch_later()` / `my_mixes()` |
| 用户主页/作品/关注/粉丝 | `user()` / `user_videos()` / `user_following()` / `user_followers()` |
| 评论回复/合集视频 | `comment_replies()` / `mix_videos()` |
| 点赞/收藏/关注/评论 | `like()` / `favorite()` / `follow()` / `comment()`，默认 `dry_run=True` |

媒体返回的 `play_addr` 和 `download_addr` 是上游原始播放/下载地址列表。它们带有短时签名和过期时间，调用方应即时使用，不要长期缓存或写入日志。

完整读取链路见 `examples/05_bili_aligned_reading.py`。该示例只读，不会改变账号状态。

---

## 推荐流累积

### `GET /api/feed/recommend/batch`

推荐 tab 每次只回 2 条左右，靠递增 `refresh_index` 取下一批。这个接口内部循环多次并去重，对前端表现为「一次拿到 N 条」。

| 参数 | 默认 | 说明 |
|---|---|---|
| `want` | 10 | 想要的条数（上限 60） |
| `rounds` | 8 | 最多请求几轮（上限 20） |
| `count` | 10 | 每轮向上游要几条 |

```json
{"items": [...], "rounds_used": 5, "count": 10}
```

---

## 写接口的载荷位置（重要）

写接口的字段放在 **urlencoded body**，不是 query。放 query 会返回
`status_code: 0` + `status_msg: "url doesn't match"`，看起来成功但什么都没发生。

| 接口 | 上游路径 | body 字段 |
|---|---|---|
| `POST /api/video/{id}/like` | `/aweme/v1/web/commit/item/digg/` | `aweme_id`, `item_type=0`, `type=1` |
| `DELETE /api/video/{id}/like` | 同上 | `type=0` |
| `POST /api/video/{id}/favorite` | `/aweme/v1/web/aweme/collect/` | `aweme_id`, `aweme_type=0`, `action=1` |
| `DELETE /api/video/{id}/favorite` | 同上 | `action=0` |
| `POST /api/user/{sec_uid}/follow` | `/aweme/v1/web/commit/follow/user/` | `user_id`（数字）, `type=1` |
| `DELETE /api/user/{sec_uid}/follow` | 同上 | `type=0` |

三个写接口都已用真实账号往返验证（点赞 58106→58107→58106，收藏 25723→25724→25723）。
关注接口路径已从 bundle 确认，但实测返回 `status_code: 8 用户未登录`，标记为 `candidate`。
