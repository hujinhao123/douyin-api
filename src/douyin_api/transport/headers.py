"""Browser-like request headers derived from the live web client."""

from __future__ import annotations

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)


def build_headers(cookies: dict[str, str], *, referer: str = "https://www.douyin.com/") -> dict[str, str]:
    cookie_header = "; ".join(f"{k}={v}" for k, v in cookies.items() if v)
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "zh-CN,zh;q=0.9",
        "Referer": referer,
        "Origin": "https://www.douyin.com",
        "Sec-Fetch-Site": "same-origin",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Dest": "empty",
    }
    if cookie_header:
        headers["Cookie"] = cookie_header
    return headers