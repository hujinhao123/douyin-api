# 已知限制与未完成项

这份清单是审计用的：每条都写清楚「现在是什么状态」和「要补什么」。

## 1. 未做真实端到端验证的部分

| 能力 | 现状 | 证据等级 |
|---|---|---|
| 点赞 / 取消点赞 | 契约 + mock 测试通过（全套 122 passed），未在真实账号执行 | `candidate` |
| 收藏 / 取消收藏 | 同上 | `candidate` |
| 关注 / 取关 | 同上 | `candidate` |
| 发表评论 | 同上 | `candidate` |
| 关注流 `feed.following` | 路径与响应结构按常见形态实现，未实测 | `candidate` |

**为什么没做**：写操作会改动真实账号数据（点赞、关注、发评论），在没有你明确同意的情况下不执行。接口、参数、幂等、确认机制都已就绪，你随时可以自己跑。

```powershell
# 先预览（不会发请求）
curl -X POST http://127.0.0.1:8787/api/video/<AWEME_ID>/like -H "Content-Type: application/json" -d "{\"dry_run\":true}"

# 确认后执行
curl -X POST http://127.0.0.1:8787/api/video/<AWEME_ID>/like -H "Content-Type: application/json" -d "{\"dry_run\":false,\"confirm\":true,\"idempotency_key\":\"k1\"}"
```

## 2. 有条件通过的部分

| 能力 | 现状 |
|---|---|
| `search.general` | 在已登录标签页实测 200 / 5 条（1.75s）；在新开的持久化 profile 上 >110s 无响应。属于指纹预热差异，不是参数错误 |
| 二维码 `scanned` 中间态 | 依赖页面文案「扫码成功 / 请在手机上确认」；文案改版会直接从 `created` 跳到 `confirmed`，不影响结果 |
| `X-Bogus` | 未还原算法，走页面实时签名。页面改版时 `SDK_READY` 选择器可能需要更新 |

## 3. 刻意没做的

| 项 | 原因 |
|---|---|
| 在 Python 里重写 `frontierSign` | 它随 bundle 每次发布变化，重写等于持续负债 |
| 绕过 TLS 指纹做纯 HTTP 请求 | 已实测所有头部组合仍 403，正确解是走浏览器 |
| 自动导出全部 cookie 到磁盘明文 | 会话只存 DPAPI 加密文件，导出要一次性票据 |
| 静默回放旧请求包 | 会让页面改版变成「看起来正常但数据是旧的」 |

## 4. 需要你决定才能继续的

1. **写接口是否在真实账号上验证** —— 会改动你的点赞/关注/评论记录。
2. **是否启用静态签名器** —— 需要从 bundle 里抽取 `frontierSign`，属于衍生代码，是否落地由你定。
3. **搜索接口的冷启动问题** —— 目前靠 profile 预热规避；如果你要求 100% 首次成功，需要改成复用你常驻的浏览器（`DOUYIN_BROWSER_CDP`）。

## 5. 环境依赖

- 必须有 Playwright 的 Chromium（`playwright install chromium`）。
- 必须能访问 `www.douyin.com`。
- Windows 上会话用 DPAPI 加密；非 Windows 退回 base64 占位（`PLAIN1:`），只适合本地开发。

## 6. 部署产物未实机构建

Dockerfile 与 docker-compose.yml 已提供，但本机 Docker Desktop 守护进程未运行（
pipe:////./pipe/dockerDesktopLinuxEngine 不存在），因此**镜像未实际构建过**。

启动 Docker Desktop 后可验证：

`powershell
cd outputs\\douyin-api
docker compose build
docker compose up -d
curl http://127.0.0.1:8787/health
`

基础镜像选 mcr.microsoft.com/playwright/python 是因为它自带 Chromium 与全部共享库；本项目签名与请求都依赖真实浏览器，用 slim 镜像会缺库。

Windows 服务化（NSSM / sc create）同样未做——python -m uvicorn ... 已可手动常驻，若要开机自启再包一层。
