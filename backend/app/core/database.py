from __future__ import annotations

import os
from collections.abc import AsyncGenerator
from pathlib import Path
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings


def _is_production() -> bool:
    return settings.environment == "production"


def _strip_ssl_from_url(url: str) -> str:
    """从 DATABASE_URL 里移除 ssl/sslmode query 参数（改用 connect_args 传 SSL）。"""
    if url.startswith("sqlite"):
        return url
    parsed = urlparse(url)
    qs = parse_qs(parsed.query)
    changed = False
    for key in ("sslmode", "ssl"):
        if key in qs:
            del qs[key]
            changed = True
    if changed:
        new_query = urlencode(qs, doseq=True)
        return urlunparse(parsed._replace(query=new_query))
    return url


_db_url = _strip_ssl_from_url(settings.database_url)

_engine_kwargs: dict = {"echo": False}
if not settings.database_url.startswith("sqlite"):
    _engine_kwargs.update(
        pool_size=10,
        max_overflow=20,
        pool_recycle=1800,
        pool_pre_ping=True,
    )
    if _is_production():
        _engine_kwargs["connect_args"] = {"ssl": "prefer"}

engine = create_async_engine(_db_url, **_engine_kwargs)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise


async def init_db() -> None:
    from app.models import Base
    from goulong_auth.base import AuthBase

    if settings.database_url.startswith("sqlite"):
        db_path = settings.database_url.rsplit("///", 1)[-1]
        if db_path and db_path != ":memory:":
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)

    async with engine.begin() as conn:
        if not settings.database_url.startswith("sqlite"):
            from sqlalchemy import text as sa_text
            await conn.execute(sa_text("CREATE SCHEMA IF NOT EXISTS goulong_auth"))
            await conn.execute(sa_text("CREATE SCHEMA IF NOT EXISTS zhaodan"))
        await conn.run_sync(AuthBase.metadata.create_all)
        await conn.run_sync(Base.metadata.create_all)
