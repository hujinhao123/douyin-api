# <PRIVATE_ACCOUNT_NUMBER_b90765981cdba8db> 本地 API

把网页版抖音的能力封装成本机 HTTP API + Python SDK：二维码登录、精选/推荐/关注流、搜索、视频详情、评论、用户主页、媒体地址、点赞收藏关注评论。

## 快速开始

```powershell
D:\Codex\Tools\Python313\python.exe -m pip install -r requirements.txt
$env:PLAYWRIGHT_BROWSERS_PATH = "D:\Codex\Caches\ms-playwright"
D:\Codex\Tools\Python313\python.exe -m playwright install chromium

cd src
D:\Codex\Tools\Python313\python.exe -m uvicorn douyin_api.server:create_app --factory --port 8787
```

打开 <http://127.0.0.1:8787/docs>。

## 扫码登录

```powershell
curl -X POST http://127.0.0.1:8787/auth/qr/start
curl http://127.0.0.1:8787/auth/qr/<qr_id>/image -o qr.png
curl http://127.0.0.1:8787/auth/qr/<qr_id>/status
curl http://127.0.0.1:8787/auth/session
```

## Python SDK

```python
from douyin_api.sdk import DouyinApiClient

with DouyinApiClient("http://127.0.0.1:8787") as dy:
    print(dy.hot_search(5))
    print(dy.featured(10))
    print(dy.video("<AWEME_ID>"))
```


## 部署

本机直接跑（见上）。容器化：

```powershell
docker compose up -d --build
curl http://127.0.0.1:8787/health
```

`docker-compose.yml` 默认只绑 `127.0.0.1:8787`，数据落在 `./data`（会话 + 浏览器 profile 持久化，重启不用重新扫码）。

## 文档

- [`docs/handoff.md`](docs/handoff.md) — 交接文档：加密链路、接口契约、坑、限制
- [`docs/api.md`](docs/api.md) — 接口文档
- [`docs/recovery.md`](docs/recovery.md) — 页面改版后的恢复手册
- [`docs/known-limits.md`](docs/known-limits.md) — 已知限制与未验证项（审计用）
- [`docs/reference-bilibili.md`](docs/reference-bilibili.md) — B 站参考库来源与哈希
- [`docs/bilibili-parity.md`](docs/bilibili-parity.md) — B 站页面能力与抖音 API 对齐表

## B 站模块风格调用

服务端路由已经覆盖推荐批量、搜索用户、我的收藏/历史/稍后看/合集、评论回复和合集视频；Python SDK 也提供对应方法，可直接参考：

```powershell
cd examples
D:\Codex\Tools\Python313\python.exe 05_bili_aligned_reading.py
```

该示例只读取当前登录账号和公开内容，不执行点赞、收藏、关注、评论，也不导出 cookie。

## 验证

```powershell
python -m pytest -q
python -m compileall -q src tests
python scripts\smoke_live.py          # 真实签名 + 热搜
python scripts\smoke_authenticated.py # 真实登录态全接口
pwsh -NoProfile -File scripts\smoke_server.ps1
```

## 结构

```
src/douyin_api/
  auth/        二维码登录、会话、导出票据
  adapters/    接口路径、签名、响应归一化
  transport/   浏览器传输、请求、错误分类
  endpoints/   HTTP 路由
  recovery.py  漂移检测
  sdk.py       Python 客户端
```

## 关键事实

- 签名是 `window.byted_acrawler.frontierSign({url})['X-Bogus']`，由页面实时生成。
- 纯 HTTP 请求会被 TLS 指纹拦（`403 ArgusSecurityPlugin`），所以请求也走浏览器。
- 用户作品分页用 `max_cursor`（毫秒时间戳），不是 `cursor`。
- 关注/粉丝路径是 `/aweme/v1/web/user/following/list/`，不是 `/relation/...`。
- `status_code: 2096` 是对方隐私设置，不是登录失效。
