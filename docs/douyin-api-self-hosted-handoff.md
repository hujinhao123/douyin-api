# 抖音 API 私有化与自部署交接（2026-10-18）

## 已完成

- 独立 API 工作副本：`D:\Codex\Projects\douyin-api`
- Git 仓库已初始化，main 分支已有 5 个提交。
- 统一 Bearer Token 鉴权：除 `/health`、`/openapi.json`、`/docs`、`/redoc` 外全部保护。
- `DOUYIN_ALLOW_LAN=true` 时要求至少 32 字符 Token，否则拒绝启动。
- Linux 会话加密：`AESGCM1:`，主密钥文件权限 0600；Windows 优先 DPAPI。
- 视频流短期一次性票据：`POST /api/video/{id}/stream-ticket`，不把长期 Token 放进 URL。
- Docker Compose、Nginx HTTPS、systemd 模板。
- 计算器设置页新增“抖音 API”配置卡片。
- 计算器删除硬编码 `192.168.1.246:8787`，改为设备本地 `Dbase` 配置。
- 计算器已构建 AMR：`loli/ui/8001687764241342.1_17_09.amr`，SHA-256 `a061e8af54f58c71857a82edddcb0ab3e8cf9a9d0e8392f22e56768ce4482f37`。

## 验证证据

- API 全量测试：153 passed。
- API `compileall`：通过。
- Compose `config`：通过。
- 计算器 lint：107 files 通过。
- 计算器抖音测试：11 passed。
- AMR verify：ok，version 1.17.09，bytes 6467785。

## 未验证

- Docker 镜像构建未执行：Docker Desktop 引擎未启动（`dockerDesktopLinuxEngine` 管道不存在）。
- Linux 服务器 + HTTPS 公网部署未执行。
- Windows 局域网真机连接未执行。
- 计算器真机扫码、推荐、搜索、视频播放未执行。
- 真实账号写操作未执行。
- GitHub 私有仓库已创建并推送：`https://github.com/hujinhao123/douyin-api`；main=`e7708d5`，标签=`v0.1.0`，页面显示 Private。

## GitHub 发布结果

GitHub 发布需要一个空的私有仓库 `douyin-api`，或可用的 GitHub Token。创建后执行：

```powershell
cd D:\Codex\Projects\douyin-api
git remote add origin https://github.com/hujinhao123/douyin-api.git
git push -u origin main
git tag -a v0.1.0 -m "douyin-api v0.1.0 private self-hosted release"
git push origin v0.1.0
```

## 已知工作区项

API 工作目录里有两个未跟踪备份文件：

- `src/douyin_api/adapters/request_profile.py.bak`
- `src/douyin_api/transport/client.py.bak`

它们未提交、未进入仓库。删除操作被当前安全策略拦截，保留待人工处理。

