from __future__ import annotations

from arq.connections import RedisSettings, create_pool

from core.config import settings


def get_redis_settings() -> RedisSettings:
    """从配置创建 RedisSettings"""
    return RedisSettings.from_dsn(settings.redis_url)


async def create_redis_pool():
    """创建 Redis 连接池"""
    return await create_pool(get_redis_settings())
