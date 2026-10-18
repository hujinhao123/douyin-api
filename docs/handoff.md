# <PRIVATE_ACCOUNT_NUMBER_b90765981cdba8db> 本地 API — 交接文档

> 版本 0.1.0 · 适配器版本 `2026.10.17` · 最后真实验证 2026-10-17

## 1. 这个项目是什么

一个**本机运行的 <PRIVATE_ACCOUNT_NUMBER_b90765981cdba8db> Web API 适配层**。它把网页版抖音的能力（二维码登录、精选/推荐/关注流、搜索、视频详情、评论、用户主页、媒体地址、点赞收藏关注评论）暴露成本地 HTTP + Python SDK。

设计上分三层，任何一层坏掉只改那一层：

| 层 | 位置 | 职责 | 页面变动时 |
|---|---|---|---|
| 会话层 | `src/douyin_api/auth/` | 二维码登录、cookie 保管、导出票据 | 登录弹窗改版 → 改 `qr_bridge.py` |
| 签名层 | `src/douyin_api/adapters/signature.py` | 生成 `X-Bogus` | SDK 改名 → 改 `BrowserSigner.SDK_READY` |
| 请求层 | `adapters/request_profile.py` + `endpoints/` | 路径、参数、响应归一化 | 接口变动 → 改一个 `EndpointProfile` |

## 2. 关键结论（都有实测证据）

### 2.1 加密/签名逻辑

页面用 `window.byted_acrawler.frontierSign({url})` 生成 **`X-Bogus`**，16 字符，每次调用都不同（含随机项），且随 URL 变化：

```
frontierSign({url}) -> {"X-Bogus": "6dpIafFC7LjDvNY1"}   # 16 chars
```

实测：同一 URL 连续两次签名结果不同（有随机因子），换 URL 结果不同（覆盖了 query）。

**签名覆盖范围**：完整 URL 的 query string（含 `msToken`、`device_platform` 等全部参数）。
**请求方式**：`X-Bogus` 放在请求头；`msToken` 同时出现在 query 和 cookie。

**结论等级：`verified`** —— 用浏览器签名 + 真实 cookie 调用热搜接口返回 51 条、调用 feed 返回 2 条、视频详情/评论/用户主页/用户作品全部 `status_code: 0`。

### 2.2 为什么签名必须走浏览器

`frontierSign` 是 `runtime~client-entry.*.js` 里打包的混淆函数（函数体约 6.4 KB），依赖页面运行时的环境指纹（canvas/WebGL/时间/随机种子）。**不要在 Python 里重写它**：它随 bundle 每次发布而变，重写等于给自己制造维护债务。本项目的做法是让真实页面算签名，Python 只负责拼 URL。

同时保留了 `StaticSigner`（`node sign.js <url>`）作为离线后备，接口已定义、测试已覆盖，等你哪天把 SDK 抽成独立文件后直接接上即可。

### 2.3 纯 HTTP 一定被拦（重要）

用 `httpx` 直接请求，即使 cookie、`X-Bogus`、全部请求头与页面逐字节一致，也会返回：

```
HTTP 403  Blocked by ArgusSecurityPlugin Uifid Not Found
```

已做过的排除实验（全部仍然 403）：

| 变量 | 结果 |
|---|---|
| 最小头（cookie + origin + referer + UA） | 403 |
| + `sec-ch-ua` / `sec-fetch-*` | 403 |
| + `priority` / `accept-encoding` | 403 |
| 去掉 session cookie | 403 |
| 只留 `UIFID` + `s_v_web_id` | 403 |
| 换 `www-hj.douyin.com` 域名 | 403 |

而同样请求在页面内 `fetch` 是 200。结论：**拦截依据是 TLS/HTTP2 指纹（JA3），不是请求头**。

因此 `DouyinClient` 默认 `mode="browser"`：签名和请求都由同一个页面完成。`mode="http"` 只用于单元测试。

### 2.4 二维码登录的真实链路（踩过的坑）

冷启动直接请求 `/passport/web/get_qrcode/` 会返回：

```json
{"data": {"error_code": 4031, "description": "您正在尝试访问的网站存在安全风险…"}}
```

原因：passport SDK 要求先完成一整套初始化，实测顺序是

1. `/passport/general/login_guiding_strategy/`
2. `/passport/ticket_guard/get_client_cert/`（拿 ticket guard 证书）
3. `/passport/web/challenge/`（拿 `passportiv`）
4. `mssdk.bytedance.com/web/r/token`（拿 `msToken`）
5. 之后 `/passport/web/get_qrcode/` 才返回 `error_code: 0` 和二维码

**所以本项目不重放这套握手**，而是打开真实登录弹窗（`.douyin_login_new_class`），从 DOM 里取 `data:image/png;base64,...` 的二维码图。这样 SDK 升级、握手参数变化都不影响我们。

**状态轮询**：页面内 `check_qrconnect` 返回 `status: "new" | "scan" | "confirmed"`；登录成功后 `sessionid`/`sessionid_ss`/`sid_tt` 出现在 cookie 里，桥接层据此判定 `confirmed`。

### 2.5 接口契约（真实抓取，见 `tests/fixtures/live_contract.json`）

| 能力 | 路径 | 列表字段 | 分页 |
|---|---|---|---|
| 精选/推荐 | `/aweme/v1/web/tab/feed/` | `aweme_list` | 流式，仅 `has_more` |
| 关注流 | `/aweme/v1/web/feed/follow/` | `data` | `cursor` |
| 搜索 | `/aweme/v1/web/general/search/single/` | `data` | `cursor`（整数偏移） |
| 视频详情 | `/aweme/v1/web/aweme/detail/` | `aweme_detail` | — |
| 评论 | `/aweme/v1/web/comment/list/` | `comments` | `cursor`（整数偏移，实测 5） |
| 用户主页 | `/aweme/v1/web/user/profile/other/` | `user` | — |
| 用户作品 | `/aweme/v1/web/aweme/post/` | `aweme_list` | **`max_cursor`（毫秒时间戳）** |
| 关注列表 | `/aweme/v1/web/user/following/list/` | `followings` | `cursor` |
| 粉丝列表 | `/aweme/v1/web/user/follower/list/` | `followers` | `cursor` |
| 热搜 | `/aweme/v1/web/hot/search/list/` | `data.word_list` | 无需登录 |

**两个已经踩过的坑，别再踩：**

1. 关注/粉丝路径**不是** `/aweme/v1/web/relation/following/list/`（404）。正确的是 `/aweme/v1/web/user/following/list/`。
2. 用户作品分页用 **`max_cursor`**（毫秒时间戳，实测 `1791594000000`），不是 `cursor`。

### 2.6 状态码语义

| code | 含义 | 本项目处理 |
|---|---|---|
| 0 | 成功 | 正常返回 |
| 5 | 缺参数 | `BAD_PARAMS` → HTTP 400 |
| 8 | 未登录/token 失效 | `SESSION_EXPIRED` → HTTP 401 |
| 2096 | **对方隐私设置，列表不可见** | `PRIVACY_HIDDEN` → HTTP 403（**不是登录失效**） |
| 2154 | 需要登录 | `SESSION_EXPIRED` → 401 |
| 10232 | 登录过期 | `SESSION_EXPIRED` → 401 |

把 2096 当登录失效是常见错误，会导致用户被无故要求重新扫码。

### 2.7 复用已登录浏览器（可选）

如果你已经在浏览器里登录了抖音，不想再扫一次码，有两条路：

**A. 让服务接管一个已开启调试端口的浏览器**

`powershell
# 先以调试端口启动 Edge/Chrome（示例）
& 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe' --remote-debugging-port=9222 --user-data-dir=D:\\Codex\\Temp\\edge-douyin
# 然后让服务连它
 = 'http://127.0.0.1:9222'
`

服务会在这个浏览器里开一个标签页，复用它的登录态和指纹。

**B. 把 cookie 交进来（一次性）**

`powershell
# 1) 页面控制台里导出（只在本机）
copy(JSON.stringify({cookies: Object.fromEntries(document.cookie.split('; ').map(c=>{const i=c.indexOf('=');return [c.slice(0,i),c.slice(i+1)]}))}))
# 2) 存成临时文件，交给脚本（成功后自动删除）
python scripts\\import_session.py .\\cookies.json
`

注意：document.cookie 拿不到 HttpOnly 的 sessionid。真实可用的路径是 A，或者直接用本项目的二维码登录。

## 3. 快速开始

```powershell
# 依赖
D:\Codex\Tools\Python313\python.exe -m pip install -r requirements.txt
D:\Codex\Tools\Python313\python.exe -m playwright install chromium
$env:PLAYWRIGHT_BROWSERS_PATH = "D:\Codex\Caches\ms-playwright"

# 启动
cd src
D:\Codex\Tools\Python313\python.exe -m uvicorn douyin_api.server:create_app --factory --port 8787
```

打开 <http://127.0.0.1:8787/docs> 看交互式接口文档。

## 4. 扫码登录

```powershell
# 1) 生成二维码（返回 base64 + qr_id）
curl -X POST http://127.0.0.1:8787/auth/qr/start

# 2) 直接拿 PNG 图片
curl http://127.0.0.1:8787/auth/qr/<qr_id>/image -o qr.png

# 3) 轮询状态：created -> scanned -> confirmed
curl http://127.0.0.1:8787/auth/qr/<qr_id>/status

# 4) 确认后查看会话
curl http://127.0.0.1:8787/auth/session
```

确认后 cookie 自动落到本地会话文件（Windows 上由 DPAPI 加密，换机/换用户不可读）。

## 5. 导出 cookie

两步式，**票据只能用一次**，`revoke` 会让所有未用票据立即失效：

```powershell
curl -X POST http://127.0.0.1:8787/auth/session/export
# -> {"ticket": "...", "expires_at": "..."}

curl -X POST http://127.0.0.1:8787/auth/session/export/redeem -H "Content-Type: application/json" -d "{\"ticket\":\"...\"}"
# -> {"cookies": {...}}   仅此一次
```

## 6. 写操作的安全默认值

所有写接口（点赞/收藏/关注/评论）默认 `dry_run=true`，不会碰抖音。真正执行需要同时给 `dry_run=false` 和 `confirm=true`：

```json
{"dry_run": false, "confirm": true, "idempotency_key": "my-op-1"}
```

同一个 `idempotency_key` 重复提交只会请求上游一次，第二次直接返回缓存结果（`replayed: true`）。缺 `confirm` 返回 409 `CONFIRM_REQUIRED`，不会静默执行。

## 7. 页面变动了怎么办（恢复流程）

```powershell
# 一步定位：哪些 profile 坏了、该怎么修
curl http://127.0.0.1:8787/diagnostics/probe
```

返回里每个 profile 都有 `verdict`，以及一句 `next_action`：

| verdict | 含义 | 修哪里 |
|---|---|---|
| `OK` | 正常 | — |
| `AUTH_CHANGED` | cookie 失效 | 重新扫码 |
| `SIGN_FAILED` | 签名拿不到 | 检查 `window.byted_acrawler.frontierSign` 是否还在 |
| `PATH_CHANGED` | 404，路径搬了 | 在 bundle 里搜新路径，改 `PROFILES` |
| `FIELD_CHANGED` | 响应少了字段 | 改对应 `normalize_*` + `live_contract.json` |
| `PARAMS_CHANGED` | 缺参数 | DevTools 抓一条真实请求，改 `MINIMAL_PARAMS` |

**恢复原则**：一次只改一个 adapter，改完跑 `pytest` + `scripts/probe_live.py`，再更新 `live_contract.json` 的 `captured_at`。

**禁止**：把旧请求包当静默 fallback。旧样本只能用于对比。

## 8. 代码地图

```
src/douyin_api/
  auth/qr_bridge.py      # 真实登录弹窗桥接（推荐，默认启用）
  auth/qr_login.py       # 纯 HTTP 状态机（备用，测试覆盖完整）
  auth/session.py        # 会话持久化 + 过期/撤销判定
  auth/export.py         # 一次性导出票据
  adapters/request_profile.py  # ★ 所有接口路径与参数（改这里）
  adapters/signature.py  # BrowserSigner / StaticSigner / 链式回退
  adapters/page.py       # ★ 响应归一化（改这里）
  transport/client.py    # 签名 + 请求 + 错误分类
  transport/retry.py     # ★ 状态码语义（改这里）
  recovery.py            # ★ 漂移检测
  endpoints/*.py         # HTTP 路由
  sdk.py                 # Python 客户端
  server.py              # 组装
```

打 ★ 的四个文件是页面变动时 95% 情况下唯一需要动的。

## 9. 已知限制（诚实清单）

1. **关注流/写接口未做真实端到端验证**。读接口中 feed/详情/评论/用户/搜索/关注/粉丝/热搜均已实测；`feed.following` 和点赞/收藏/关注/评论只做了契约与 mock 验证，没有在真实账号上执行写操作（避免污染你的账号数据）。
2. **`feed.following` 的响应字段**是按 `/aweme/v1/web/feed/follow/` 的常见结构推断的（`data`），未实测。
3. **二维码登录的 `scanned` 中间态**依赖页面文案（"扫码成功"/"请在手机上确认"）。若文案改版，会跳过 `scanned` 直接从 `created` 到 `confirmed`——不影响最终结果。
4. **静态签名器（`StaticSigner`）未接真实 bundle**。接口和测试就绪，需要你把 SDK 抽成独立 JS 文件后启用。
5. **`X-Bogus` 算法未还原**。这是刻意的：它随 bundle 变化，还原即负债。当前 `verified` 的路径是"用页面算签名"。
6. **`search.general` 在新开的浏览器 profile 上会挂起**（>110s 无响应），但在你已登录的标签页里 1.75s 返回 200、5 条结果。属于 profile 预热/指纹状态差异，不是路径或参数错误。恢复方式：用同一个持久化 profile 多跑几次，或通过 `DOUYIN_CDP` 复用一个已经活跃的浏览器。
6. **Windows DPAPI 之外的平台**使用 base64 占位（`PLAIN1:` 前缀），仅适合本地开发。

## 10. 验证证据

```
pytest                     -> 122 passed
compileall                 -> OK
scripts/smoke_live.py      -> X-Bogus 16 chars, hot words 51
scripts/probe_live.py      -> healthy: true, verdict OK
scripts/smoke_server.ps1   -> /health ok, /api/feed/hot-search total=51, 未登录访问 featured -> 401
scripts/smoke_qr.py        -> qr_id 生成, image 774 bytes, 二维码可扫
scripts/smoke_authenticated.py（真实登录态）
    feed.featured    status 0, 2 items
    video.detail     status 0, has_detail True
    video.comments   status 0, 5 items, total 843
    user.profile     status 0, has_user True
    user.posts       status 0, 6 items, max_cursor 1791683100000
    feed.hot_search  status 0, 51 items
    user.following   另一账号隐私设置 -> PRIVACY_HIDDEN（预期）
    user.followers   同上（预期）
    search.general   已在你标签页验证 200/5 items；冷 profile 超时（见 §9.6）
```

## 11. 参考资料

B 站参考库只做架构对照，不参与运行时：

- 包：ilibili-api-python 17.4.2（导入名 ilibili_api）
- 下载与哈希记录：docs/reference-bilibili.md
- 借鉴点：业务分组、登录态与业务分离、显式错误类型
- 未照搬：签名算法、凭据由调用方持有的模式

## 风控友好请求策略（已实现）

- 单个 `DouyinClient` 内所有请求串行通过 `Throttle`，默认请求间隔为 1.2 秒，并加入 0~0.8 秒随机抖动。
- 403/412/429 不立即重试；403/412 进入递增冷却，429 优先读取响应中的 `retry_after`，没有时使用 15 秒起步、最多 5 分钟的冷却。
- 同一个 cookie 会话只向浏览器 profile 注入一次，后续请求复用同一个页面和同一套 HttpOnly cookie，避免反复 reload。
- `status_code` 为 8/2154/10232 时锁存当前 cookie 指纹，后续请求直接返回 `SESSION_EXPIRED`，换入新登录会话后才允许继续。
- 未实现后台无限重试、旧包静默回放、伪造 `a_bogus`。页面签名仍由当前浏览器 runtime 生成。

这套策略降低请求突发和重复重放造成的风控概率，但上游仍可能因账号状态、设备指纹、页面环境或服务端策略拒绝请求；遇到拒绝时客户端会停发并等待新会话或冷却结束。

## B 站模块对齐进度

当前抖音 API 与计算器 B 站模块的读取能力已经在服务端和 Python SDK 两层对齐：推荐、搜索、视频详情、原播放地址、评论、用户、收藏、历史、稍后看、合集和二维码登录均有稳定入口。SDK 新增方法集中在 src/douyin_api/sdk.py，对应示例是 examples/05_bili_aligned_reading.py。

播放器 UI、弹幕和本地收藏展示不属于 API 传输层；API 返回媒体原地址与结构化数据，由上层播放器或页面负责渲染。未接入的能力在 docs/bilibili-parity.md 明确标记，不以接口存在推断真实端到端完成。
