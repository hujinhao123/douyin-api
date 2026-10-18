# bilibili-api-python 参考记录

只作为**架构参考**下载，不修改、不作为抖音项目的运行时依赖。

| 项 | 值 |
|---|---|
| 包名 | `bilibili-api-python` |
| 导入名 | `bilibili_api` |
| 版本 | 17.4.2 |
| 来源 | PyPI（`https://pypi.org/project/bilibili-api-python/`） |
| 下载方式 | `pip download --no-deps -i https://pypi.tuna.tsinghua.edu.cn/simple bilibili-api-python` |
| 文件 | `bilibili_api_python-17.4.2-py3-none-any.whl` |
| 大小 | 387,324 bytes |
| SHA-256 | `91e002b2e0bcd3eb50239e35ceb849133b574f407a92a06636e1de1031b6d09d` |
| 下载日期 | 2026-10-17 |

## 借鉴了什么

| 参考库的做法 | 抖音项目的对应 |
|---|---|
| 一个包暴露大量按业务分组的方法 | `sdk.py` 按 feed / search / video / user / social 分组 |
| 登录态独立于业务 API | `auth/` 与 `endpoints/` 分离，业务层只依赖 `SessionStore` |
| 同步与异步两套入口 | 本项目只有异步内核（`DouyinClient`），SDK 用同步 httpx 包一层 |
| 错误类型显式区分 | `errors.py` 里每种失败一个类，映射到固定 HTTP 状态 |

## 没有照搬的

- 参考库直接拼签名算法；本项目不还原 `X-Bogus`，改为调用页面运行时。
- 参考库把凭据放在调用方；本项目把会话锁在本地 DPAPI 文件里，导出要一次性票据。
