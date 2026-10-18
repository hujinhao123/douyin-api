from __future__ import annotations

import os

TEST_API_TOKEN = "test-api-token-" + "x" * 24


def install_test_api_token() -> str:
    os.environ["DOUYIN_API_TOKEN"] = TEST_API_TOKEN
    return TEST_API_TOKEN
