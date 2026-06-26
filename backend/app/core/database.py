from __future__ import annotations

from collections.abc import AsyncGenerator
from pathlib import Path
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings


def _ensure_ssl_database_url(url: str) -> str:
    if url.startswith("sqlite"):
        return url
    parsed = urlparse(url)
    qs = parse_qs(parsed.query)
    if "sslmode" not in qs and settings.environment == "production":
        qs["sslmode"] = ["require"]
        new_query = urlencode(qs, doseq=True)
        return urlunparse(parsed._replace(query=new_query))
    return url


_db_url = _ensure_ssl_database_url(settings.database_url)
engine = create_async_engine(_db_url, echo=False)
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
        await conn.run_sync(AuthBase.metadata.create_all)
        await conn.run_sync(Base.metadata.create_all)
