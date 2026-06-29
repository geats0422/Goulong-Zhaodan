"""Redis 异步客户端单例。

提供 FastAPI 路由、Service 层、ARQ worker 共用的异步 Redis 客户端。
与 app/core/redis.py（arq 专用 RedisSettings）区分：本模块面向验证码、限频等
键值读写场景。
"""
from __future__ import annotations

import redis.asyncio as redis

from app.core.config import settings

_redis_client: redis.Redis | None = None


def get_redis() -> redis.Redis:
    """获取全局 Redis 异步客户端（懒加载单例）。"""
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.from_url(settings.redis_url, decode_responses=True)
    return _redis_client


async def close_redis() -> None:
    """关闭 Redis 连接（lifespan 关闭时调用）。"""
    global _redis_client
    if _redis_client is not None:
        await _redis_client.aclose()
        _redis_client = None
