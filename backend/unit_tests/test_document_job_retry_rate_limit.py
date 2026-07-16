from __future__ import annotations

import uuid
from unittest.mock import AsyncMock

import pytest
from redis.exceptions import RedisError

from app.core.document_job_retry_rate_limit import (
    RetryRateLimitUnavailableError,
    consume_retry_rate_limit,
)


USER_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")


@pytest.mark.asyncio
async def test_retry_rate_limit_uses_atomic_redis_counter_keyed_only_by_user() -> None:
    redis = AsyncMock()
    redis.eval.return_value = 5

    allowed = await consume_retry_rate_limit(
        USER_ID,
        limit=5,
        window_seconds=3600,
        redis=redis,
    )

    assert allowed is True
    args = redis.eval.await_args.args
    assert "INCR" in args[0]
    assert "EXPIRE" in args[0]
    assert args[1:] == (1, f"document-job-retry:{USER_ID}", 3600)


@pytest.mark.asyncio
async def test_retry_rate_limit_rejects_request_over_limit() -> None:
    redis = AsyncMock()
    redis.eval.return_value = 6

    assert await consume_retry_rate_limit(USER_ID, limit=5, window_seconds=3600, redis=redis) is False


@pytest.mark.asyncio
async def test_retry_rate_limit_fails_closed_when_redis_is_unavailable() -> None:
    redis = AsyncMock()
    redis.eval.side_effect = RedisError("connection details must not escape")

    with pytest.raises(RetryRateLimitUnavailableError):
        await consume_retry_rate_limit(USER_ID, limit=5, window_seconds=3600, redis=redis)
