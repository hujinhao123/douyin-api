# douyin-api

可自部署的抖音网页能力 HTTP API 与 Python SDK。项目通过真实浏览器完成页面签名、二维码登录与会话保持，适合在受控的个人服务器或本机运行。

> 这是非官方项目，与抖音及其关联公司无隶属关系。接口依赖抖音网页和浏览器环境，页面改版后可能需要适配。使用者应自行遵守服务条款、版权和当地法律，不要用于批量抓取、绕过访问控制或未授权操作。

## 能做什么

- 二维码登录与登录会话状态
- 推荐、精选、关注、搜索和视频详情
- 评论、用户主页、合集和媒体信息
- 收藏、历史、稍后看等读取能力
- Python SDK 与 OpenAPI 文档
- Bearer Token 鉴权、加密会话存储和视频短期播放票据
- Linux HTTPS、Docker、systemd 与 Windows 局域网部署模板

## 安全模型

- 默认只监听 `127.0.0.1`。
- 开启局域网访问时必须配置至少 32 字符的 `DOUYIN_API_TOKEN`。
- 除 `/health`、`/openapi.json`、`/docs`、`/redoc` 外，业务接口均要求：

```http
Authorization: Bearer <DOUYIN_API_TOKEN>
```

- 不要把 8787 直接暴露到公网；公网部署应放在 HTTPS 反向代理之后。
- Cookie、`session.bin`、`master.key`、浏览器 profile、二维码和 `.env` 都不得提交到 Git。
- 视频播放先申请一次性短期票据，不要把长期 API Token 放进播放 URL。

## 快速开始（Windows）

以下命令适用于 PowerShell：

```powershell
git clone https://github.com/hujinhao123/douyin-api.git
cd douyin-api

python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt

$env:PLAYWRIGHT_BROWSERS_PATH = "$PWD\.playwright"
.\.venv\Scripts\python.exe -m playwright install chromium
```

生成并设置本机 Token：

```powershell
$env:DOUYIN_API_TOKEN = [Convert]::ToBase64String(
  [Security.Cryptography.RandomNumberGenerator]::GetBytes(48)
)
$env:DOUYIN_API_DATA = "$PWD\data"
$env:PYTHONPATH = "$PWD\src"

.\.venv\Scripts\python.exe -m uvicorn douyin_api.server:create_app `
  --factory --host 127.0.0.1 --port 8787
```

另开一个 PowerShell 验证：

```powershell
Invoke-RestMethod http://127.0.0.1:8787/health
Invoke-RestMethod http://127.0.0.1:8787/auth/session `
  -Headers @{ Authorization = "Bearer $env:DOUYIN_API_TOKEN" }
```

打开 <http://127.0.0.1:8787/docs> 查看接口文档。

如果系统没有 `venv` 模块，可先安装 `virtualenv`，再用 `python -m virtualenv .venv` 创建环境。

## 扫码登录

调用 `POST /auth/qr/start` 获取二维码，然后轮询 `GET /auth/qr/{qr_id}/status`。也可以直接打开 `/docs` 操作。

登录成功后会话保存在数据目录。Linux 使用 AES-GCM 加密，Windows 使用 DPAPI。迁移或恢复时必须同时保留 `session.bin` 和 `master.key`。

## Python SDK

```python
from douyin_api.sdk import DouyinApiClient

with DouyinApiClient(
    "http://127.0.0.1:8787",
    token="<DOUYIN_API_TOKEN>",
) as dy:
    print(dy.hot_search(5))
    print(dy.featured(10))
    print(dy.video("<AWEME_ID>"))
```

## 部署

- [自部署完整指南](docs/self-hosting.md)：Linux HTTPS、Docker、systemd、Windows 局域网
- [API 文档](docs/api.md)
- [恢复手册](docs/recovery.md)
- [已知限制](docs/known-limits.md)
- [安全说明](SECURITY.md)

Docker 快速验证：

```bash
cp .env.example .env
chmod 600 .env
docker compose -f deploy/docker-compose.prod.yml up -d --build
curl http://127.0.0.1:8787/health
```

## 测试

```bash
python -m pytest -q
python -m compileall -q src tests
```

需要真实登录态和真实抖音网络的冒烟测试见 `scripts/`，运行前请自行评估账号和风控风险。

## 项目结构

```text
src/douyin_api/
  auth/        二维码登录、会话和导出票据
  adapters/    接口路径、签名和响应归一化
  transport/   浏览器传输、请求与错误分类
  endpoints/   HTTP 路由
  recovery.py  漂移检测
  sdk.py       Python 客户端
deploy/        Docker、Nginx、systemd 模板
docs/          部署、API、恢复与限制文档
```

## 已知边界

- 依赖抖音网页的实际结构，页面或签名变化可能导致部分接口失效。
- 浏览器签名和请求模式有资源开销，不适合高并发或大规模采集。
- 公开仓库不包含登录 Cookie、会话密钥或任何真实账号数据。
- 安全漏洞请通过 GitHub 私有安全报告联系维护者，不要公开提交包含敏感信息的 issue。
