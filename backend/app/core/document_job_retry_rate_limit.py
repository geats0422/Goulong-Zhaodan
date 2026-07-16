from __future__ import annotations

import uuid
from typing import Any

from redis.exceptions import RedisError

from app.core.redis_client import get_redis


_FIXED_WINDOW_COUNTER = """
local count = redis.call('INCR', KEYS[1])
if count == 1 then
    redis.call('EXPIRE', KEYS[1], ARGV[1])
end
return count
"""


class RetryRateLimitUnavailableError(RuntimeError):
    pass


async def consume_retry_rate_limit(
    user_id: uuid.UUID,
    *,
    limit: int,
    window_seconds: int,
    redis: Any | None = None,
) -> bool:
    client = redis if redis is not None else get_redis()
    key = f"document-job-retry:{user_id}"
    try:
        count = await client.eval(_FIXED_WINDOW_COUNTER, 1, key, window_seconds)
    except RedisError as exc:
        raise RetryRateLimitUnavailableError from exc
    return int(count) <= limit
