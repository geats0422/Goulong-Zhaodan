from __future__ import annotations

import sys
import time
import types
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

for mod_name in [
    "pageindex",
    "pydantic_ai",
    "pydantic_ai.agent",
    "pydantic_ai.models",
]:
    if mod_name not in sys.modules:
        sys.modules[mod_name] = types.ModuleType(mod_name)

if "markitdown" not in sys.modules or not hasattr(sys.modules.get("markitdown"), "MarkItDown"):
    _fake_md = types.ModuleType("markitdown")
    _fake_md.MarkItDown = MagicMock()
    sys.modules["markitdown"] = _fake_md

fake_inspector_module = types.ModuleType("agents.inspector")


async def _fake_run_inspection(*args, **kwargs):
    return {"overall_risk": "low", "summary": "", "issues": [], "regulation_refs": []}


fake_inspector_module.run_inspection = _fake_run_inspection
sys.modules["agents.inspector"] = fake_inspector_module

import pytest

from core.rate_limit import IPRateLimiter


def test_register_within_limit():
    limiter = IPRateLimiter(max_requests=5, window_seconds=3600)
    ip = "1.2.3.4"
    for _ in range(5):
        assert not limiter.is_limited(ip)
        limiter.record(ip)


def test_register_exceeds_limit():
    limiter = IPRateLimiter(max_requests=5, window_seconds=3600)
    ip = "1.2.3.4"
    for _ in range(5):
        limiter.record(ip)
    assert limiter.is_limited(ip)


def test_different_ips_independent():
    limiter = IPRateLimiter(max_requests=5, window_seconds=3600)
    ip_a = "1.2.3.4"
    ip_b = "5.6.7.8"
    for _ in range(5):
        limiter.record(ip_a)
    assert limiter.is_limited(ip_a)
    assert not limiter.is_limited(ip_b)


def test_register_duplicate_email_unified_message():
    from unittest.mock import AsyncMock, patch

    from fastapi import HTTPException

    from core.rate_limit import IPRateLimiter
    from routers.auth import register

    limiter = IPRateLimiter(max_requests=5, window_seconds=3600)

    mock_request = MagicMock()
    mock_request.client = MagicMock()
    mock_request.client.host = "127.0.0.1"
    mock_request.headers = {}

    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = MagicMock()
    mock_db.execute = AsyncMock(return_value=mock_result)

    body = MagicMock()
    body.email = "dup@example.com"
    body.phone = None
    body.nickname = "dup_user"
    body.password = "TestPass123"

    mock_response = MagicMock()

    with patch("routers.auth.register_limiter", limiter):
        with pytest.raises(HTTPException) as exc_info:
            import asyncio
            asyncio.run(register(body, mock_response, mock_request, mock_db))

    assert exc_info.value.status_code == 400
    assert "已被注册" in exc_info.value.detail


def test_is_limited_cleans_expired_keys():
    limiter = IPRateLimiter(max_requests=2, window_seconds=1)
    ip_a = "10.0.0.1"
    ip_b = "10.0.0.2"
    limiter.record(ip_a)
    limiter.record(ip_b)
    assert ip_a in limiter._requests
    assert ip_b in limiter._requests

    time.sleep(1.1)
    limiter.is_limited(ip_a)
    assert ip_b not in limiter._requests
