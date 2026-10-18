# 恢复手册（页面改版后的 15 分钟恢复流程）

## 0. 先判断是哪一层坏了

```powershell
curl http://127.0.0.1:8787/diagnostics/probe
curl http://127.0.0.1:8787/diagnostics/version
curl http://127.0.0.1:8787/health
```

看 `next_action` 一句话结论，再按下表进入对应章节。

| verdict | 层 | 章节 |
|---|---|---|
| `AUTH_CHANGED` | 会话 | §1 |
| `SIGN_FAILED` | 签名 | §2 |
| `PATH_CHANGED` | 请求 | §3 |
| `FIELD_CHANGED` | 归一化 | §4 |
| `PARAMS_CHANGED` | 参数 | §5 |
| `TRANSPORT_ERROR` | 网络/代理 | §6 |

---

## §1 AUTH_CHANGED：登录失效

**判定**：`status_code` 为 8 / 2154 / 10232，或 HTTP 401。

**处理**：

```powershell
curl -X POST http://127.0.0.1:8787/auth/qr/start
# 用返回的 qr_id
curl http://127.0.0.1:8787/auth/qr/<qr_id>/image -o qr.png
# 手机抖音扫码 -> 轮询
curl http://127.0.0.1:8787/auth/qr/<qr_id>/status
```

如果 `start` 直接 502：

1. 打开 `http://127.0.0.1:8787/docs` 之外的浏览器手动访问 <https://www.douyin.com>，确认能正常打开（不是验证码页）。
2. 删掉 `%LOCALAPPDATA%\douyin-api\browser-profile`（**只删这个 profile 目录**），重新 `start`。
3. 若浏览器环境被判定异常（4031），改用非 headless：
   ```powershell
   $env:DOUYIN_HEADLESS = "0"
   ```
   然后重启服务，手动完成一次登录，profile 会保留。

**不要**做的事：不要试图在 Python 里重放 `challenge` → `ticket_guard` → `mssdk` 这套握手。它每次发布都可能变，成本远高于驱动真实弹窗。

---

## §2 SIGN_FAILED：签名拿不到

**判定**：`SIGN_FAILED`，或 `/api/feed/hot-search` 返回 502。

**排查顺序**：

```powershell
# 1) 签名 SDK 是否还在
python scripts\smoke_live.py
```

脚本会打印 `X-Bogus: <16 chars>`。若报 `Page.wait_for_function: Timeout`：

```python
# 2) 在浏览器控制台确认入口是否改名
window.byted_acrawler.frontierSign
window.byted_acrawler
Object.keys(window).filter(k => /acrawler|bogus|webmssdk|bdms/i.test(k))
```

实测（2026-10-17）全局对象是 `byted_acrawler`，方法 `frontierSign({url})` 返回 `{"X-Bogus": "..."}`。若改名：

改 `src/douyin_api/adapters/signature.py` 里两处：

```python
SDK_READY = (
    "() => !!window.<NEW_OBJECT> && "
    "typeof window.<NEW_OBJECT>.<NEW_METHOD> === 'function'"
)
# 以及 __call__ 里的
"u => window.<NEW_OBJECT>.<NEW_METHOD>({url: u})['X-Bogus']"
```

若返回字段改名（例如变成 `a_bogus`），同步改 `['X-Bogus']` 和 `transport/client.py` 里的 header 名。

**永远不要**在 Python 里重写签名算法。

---

## §3 PATH_CHANGED：接口路径搬了

**判定**：HTTP 404。

**找新路径**（在已登录的浏览器控制台）：

```js
// 1) 打开开发者工具 Network，操作一次对应功能
// 2) 过滤 /aweme/v1/web/
// 3) 复制完整路径（去掉 query）
```

或者从 bundle 里搜：

```js
// 在控制台执行，列出所有 /aweme/v1/web/ 路径字面量
const src = [...document.scripts].map(s => s.src);
// 下载 bundle 后 grep：
// grep -oE '/aweme/v1/web/[a-z0-9_/]+' *.js | sort -u
```

**改一处**：`src/douyin_api/adapters/request_profile.py` 里对应的 `EndpointProfile.path`。

已确认的错误路径（别再用）：

```
✗ /aweme/v1/web/relation/following/list/   (404)
✗ /aweme/v1/web/relation/follower/list/    (404)
✗ /aweme/v1/web/im/relation/following/list/ (404)
✓ /aweme/v1/web/user/following/list/
✓ /aweme/v1/web/user/follower/list/
```

改完：

```powershell
python -m pytest tests\test_contract.py -q
python scripts\probe_live.py
```

---

## §4 FIELD_CHANGED：响应字段变了

**判定**：`status_code: 0` 但顶层少了预期 key，或列表字段不存在。

**定位**：

```powershell
# 抓一份当前真实响应（浏览器已登录，页面内 fetch）
# 或者直接看 /diagnostics/probe 的 top_level_keys
```

对比 `tests/fixtures/live_contract.json` 里记录的 `top_level` 和 `list_key`。

**改两处**：

1. `src/douyin_api/adapters/request_profile.py` → `response_key`
2. `src/douyin_api/adapters/page.py` → 对应 `normalize_*()` 函数里的字段名

**然后更新基线**：把新的 `top_level` / `list_key` 写回 `tests/fixtures/live_contract.json`，并把 `_meta.captured_at` 改成当天。

```powershell
python -m pytest tests\test_contract.py -q
```

契约测试会强制代码与基线一致，防止"改了代码忘了改文档"。

---

## §5 PARAMS_CHANGED：参数变了

**判定**：`status_code: 5`（缺参数）。

**定位**：DevTools → Network → 复制那条请求的完整 query，和 `COMMON_PARAMS` + `MINIMAL_PARAMS` 对比。

**改两处**：

1. `src/douyin_api/adapters/request_profile.py` → `COMMON_PARAMS`（所有接口共用的）
2. `src/douyin_api/recovery.py` → `MINIMAL_PARAMS`（探测用的最小参数集）

**常见变化点**：`version_code` / `version_name`（随客户端版本）、`pc_libra_divert`、`support_dash`、`device_memory`。

---

## §6 TRANSPORT_ERROR：网络问题

不是页面改版。依次检查：

```powershell
# 1) 能否访问抖音
curl -I https://www.douyin.com

# 2) 代理是否干扰（本项目 httpx 默认不走系统代理）
$env:HTTP_PROXY; $env:HTTPS_PROXY

# 3) Playwright 浏览器是否还在
$env:PLAYWRIGHT_BROWSERS_PATH
Test-Path "$env:PLAYWRIGHT_BROWSERS_PATH\chromium-*"
```

---

## §7 提交前的固定检查

```powershell
cd work\douyin-api

# 单元 + 契约 + 漂移检测
python -m pytest -q

# 语法
python -m compileall -q src tests

# 真实链路（需要网络 + 浏览器）
python scripts\smoke_live.py
python scripts\probe_live.py

# 服务端到端
pwsh -NoProfile -File scripts\smoke_server.ps1
```

五项全绿才算恢复完成。

---

## §8 变更记录模板

每次适配器改动，在下面追加一行：

| 日期 | 触发 verdict | 改的文件 | 验证结果 |
|---|---|---|---|
| 2026-10-17 | — | 初始版本 | pytest 101 passed; hot-search 51 items; feed/detail/comment/profile/posts 全部 status_code 0 |

## 风控恢复入口

1. 收到 403/412/429：客户端停止立即重试，进入冷却；等待冷却结束后只做一次新的实时请求。
2. 收到 `SESSION_EXPIRED`：当前 cookie 指纹被锁存；重新扫码登录或导入新会话后，指纹变化会自动解除锁存。
3. 浏览器页面被重新登录：先关闭旧 API 进程，再用同一个 browser profile 启动，避免两个 Playwright 实例争抢 profile。
4. 需要恢复时运行 `scripts/live_suite.py`，它在同一个浏览器页面中完成登录验证和接口验证，避免跨进程覆盖 cookie。

恢复过程中不要批量并发调用接口，也不要使用旧请求包替代实时请求。
