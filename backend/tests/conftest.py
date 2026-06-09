from __future__ import annotations

from urllib.parse import urlparse

import pytest

from core.config import settings


def assert_safe_database_for_cleanup() -> None:
    database_url = settings.database_url.replace("+asyncpg", "")
    parsed = urlparse(database_url)
    if parsed.scheme.startswith("sqlite"):
        return

    database_name = parsed.path.lstrip("/")
    if database_name.endswith("_test") or database_name == "test":
        return

    raise RuntimeError(f"拒绝清理非测试数据库: {database_name}")


@pytest.fixture
def api_headers():
    return {"X-API-Key": "goulong-dev-key"}
