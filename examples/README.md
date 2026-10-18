# 示例索引

五个可直接运行的脚本，覆盖 API 的五种典型用法。

| 文件 | 需要登录 | 说明 |
|---|---|---|
| `01_hot_search.py` | 否 | 健康检查 + 热搜榜（最小可用示例） |
| `02_qr_login.py` | — | 二维码登录全流程，把二维码存成 PNG |
| `03_read_content.py` | 是 | 精选流 → 视频详情 → 评论 → 媒体地址 → 写操作 dry-run |
| `04_drift_check.py` | 否 | 页面改版后的漂移检测 |
| `05_bili_aligned_reading.py` | 是 | B 站模块风格：推荐批量、播放地址、评论、我的内容、搜索 |

## 运行前提

```powershell
# 1) 服务已启动
cd ..\src
D:\Codex\Tools\Python313\python.exe -m uvicorn douyin_api.server:create_app --factory --port 8787

# 2) 让 examples 能 import SDK
$env:PYTHONPATH = "<绝对路径>\outputs\douyin-api\src"
```

## 运行

```powershell
cd ..\examples
D:\Codex\Tools\Python313\python.exe 01_hot_search.py
D:\Codex\Tools\Python313\python.exe 02_qr_login.py
D:\Codex\Tools\Python313\python.exe 03_read_content.py
D:\Codex\Tools\Python313\python.exe 04_drift_check.py
D:\Codex\Tools\Python313\python.exe 05_bili_aligned_reading.py
```

## 说明

- `03` 里的 `dy.like(...)` 默认 `dry_run=True`，**不会**真的点赞。
- `02` 会一直轮询到扫码完成或二维码过期，请确保手边有手机。
- 所有示例都不打印 cookie 值。
