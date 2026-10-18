# 自部署

本项目默认只监听回环地址。对外提供访问时，先配置强 Token，再通过 HTTPS 反向代理；不要把 8787 直接暴露到公网。

## 0. 生成 Token

Linux:

```bash
python3 -c 'import secrets; print(secrets.token_urlsafe(48))'
```

PowerShell:

```powershell
[Convert]::ToBase64String([Security.Cryptography.RandomNumberGenerator]::GetBytes(48))
```

Token 至少 32 字符。不要提交到 Git。

## 1. Linux + Docker + HTTPS（主部署）

```bash
cd /opt/douyin-api
cp .env.example .env
chmod 600 .env
```

编辑 `.env`：

```dotenv
DOUYIN_API_DATA=/data
DOUYIN_HOST=0.0.0.0
DOUYIN_PORT=8787
DOUYIN_ALLOW_LAN=true
DOUYIN_API_TOKEN=替换为随机长Token
DOUYIN_MASTER_KEY_FILE=/data/master.key
DOUYIN_HEADLESS=true
```

Compose 只绑定回环：

```bash
docker compose -f deploy/docker-compose.prod.yml up -d --build
curl http://127.0.0.1:8787/health
```

Nginx 使用 `deploy/nginx/douyin-api.conf` 模板，替换域名和证书路径，`nginx -t` 后 reload。

## 2. Linux + systemd（无 Docker）

```bash
sudo useradd --system --home /opt/douyin-api --shell /usr/sbin/nologin douyin-api
sudo mkdir -p /opt/douyin-api/{releases,data,run}
sudo chown -R douyin-api:douyin-api /opt/douyin-api
```

将源码 release 放到 `/opt/douyin-api/releases/<version>`，创建 venv，安装依赖和 Playwright Chromium，再建立 `current` 软链接。真实环境文件放 `/opt/douyin-api/run/douyin-api.env`，权限 0600。

安装 `deploy/systemd/douyin-api.service` 后：

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now douyin-api
curl http://127.0.0.1:8787/health
```

## 3. Windows 本机 + 局域网（辅助）

```powershell
cd D:\Codex\Projects\douyin-api
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
$env:PLAYWRIGHT_BROWSERS_PATH = 'D:\Codex\Caches\ms-playwright'
.\.venv\Scripts\python.exe -m playwright install chromium
```

设置环境变量：

```powershell
$env:DOUYIN_API_DATA = 'D:\Codex\Caches\douyin-api\data'
$env:DOUYIN_HOST = '0.0.0.0'
$env:DOUYIN_ALLOW_LAN = 'true'
$env:DOUYIN_API_TOKEN = '<随机长Token>'
$env:DOUYIN_MASTER_KEY_FILE = 'D:\Codex\Caches\douyin-api\data\master.key'
$env:PYTHONPATH = (Resolve-Path .\src).Path
.\.venv\Scripts\python.exe -m uvicorn douyin_api.server:create_app --factory --host 0.0.0.0 --port 8787
```

如果 `python -m venv` 报错说缺少 venv 模块，可安装 `virtualenv` 后改用 `python -m virtualenv .venv`。`DOUYIN_API_DATA` 和 `DOUYIN_MASTER_KEY_FILE` 指向同一数据目录。`DOUYIN_API_TOKEN` 必须至少 32 字符，并与计算器设置页填写的 Token 完全一致。Windows 防火墙只允许指定私网网段访问 8787。计算器设置页填写：

```text
http://<电脑局域网IP>:8787
```

## 4. 客户端请求

除健康检查和文档页外，所有业务请求必须带：

```http
Authorization: Bearer <DOUYIN_API_TOKEN>
```

## 5. 视频播放票据

计算器先通过 Bearer Token 请求：

```http
POST /api/video/<id>/stream-ticket
```

再打开：

```text
GET /api/video/<id>/stream?ticket=<ticket>
```

票据只对对应视频有效、默认 5 分钟且一次使用。不要把 `DOUYIN_API_TOKEN` 直接放进播放器 URL。

## 6. 数据备份

需要备份：

- `data/session.bin`
- `data/master.key`
- `data/browser-profile/`

`session.bin` 离开 `master.key` 不能解密。两者必须一起备份，但不要放入 Git。

## 7. 未验证边界

- 未在真实 Linux 服务器完成公网 HTTPS 端到端验证时，不得声明“生产已通过”。
- 未在真实抖音账号执行写操作。
- 未在词典笔真机验证时，不得声明计算器端完成。
- 抖音页面、签名入口或接口路径变化时，按 `docs/recovery.md` 排查。
