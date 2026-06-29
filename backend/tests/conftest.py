from __future__ import annotations

import os
from urllib.parse import urlparse

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from app.core import database as db_mod
from app.core.config import settings

TEST_DB_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql+asyncpg://postgres:990715@localhost:5432/goulong_test",
)

# Children first, parents last — respects FK constraints.
_CLEANUP_TABLES = [
    "zhaodan.agent_jobs",
    "zhaodan.deduction_orders",
    "zhaodan.subscription_contracts",
    "zhaodan.payment_orders",
    "goulong_auth.refresh_tokens",
    "goulong_auth.memberships",
    "zhaodan.api_keys",
    "zhaodan.inspection_records",
    "zhaodan.knowledge_document_settings",
    "zhaodan.taboo_words",
    "zhaodan.user_profiles",
    "zhaodan.index_nodes",
    "zhaodan.document_versions",
    "zhaodan.knowledge_documents",
    "zhaodan.engineering_subcategories",
    "goulong_auth.users",
]

# ---------------------------------------------------------------------------
# Patch the global engine BEFORE any test runs.
# NullPool ensures each operation gets a fresh connection, avoiding
# "another operation is in progress" errors from cross-event-loop sharing.
# ---------------------------------------------------------------------------
_test_engine = create_async_engine(TEST_DB_URL, echo=False, poolclass=NullPool)
_test_session_factory = async_sessionmaker(_test_engine, class_=AsyncSession, expire_on_commit=False)

db_mod.engine = _test_engine
db_mod.async_session = _test_session_factory


async def _create_schema_and_tables(engine: AsyncEngine) -> None:
    from app.models import Base
    from goulong_auth.base import AuthBase

    async with engine.begin() as conn:
        await conn.execute(text("CREATE SCHEMA IF NOT EXISTS goulong_auth"))
        await conn.execute(text("CREATE SCHEMA IF NOT EXISTS zhaodan"))
        await conn.run_sync(Base.metadata.create_all)
        await conn.run_sync(AuthBase.metadata.create_all)


async def _cleanup_tables(engine: AsyncEngine) -> None:
    async with engine.begin() as conn:
        # Break circular FK: knowledge_documents.current_version_id -> document_versions.id
        await conn.execute(text("UPDATE zhaodan.knowledge_documents SET current_version_id = NULL"))
        for table in _CLEANUP_TABLES:
            await conn.execute(text(f"DELETE FROM {table}"))


def assert_safe_database_for_cleanup() -> None:
    database_url = settings.database_url.replace("+asyncpg", "")
    parsed = urlparse(database_url)
    if parsed.scheme.startswith("sqlite"):
        return

    database_name = parsed.path.lstrip("/")
    if database_name.endswith("_test") or database_name == "test":
        return

    raise RuntimeError(f"拒绝清理非测试数据库: {database_name}")


@pytest_asyncio.fixture(autouse=True, scope="session")
async def _ensure_schema():
    """Session 开始时确保所有表存在（幂等，新模型自动建表）。"""
    await _create_schema_and_tables(db_mod.engine)


@pytest_asyncio.fixture(autouse=True)
async def _cleanup_before_test():
    """Clean up tables before each async test using the patched global engine."""
    await _cleanup_tables(db_mod.engine)


@pytest.fixture(autouse=True)
def _disable_turnstile(monkeypatch):
    """测试环境禁用 Turnstile 人机验证（SECRET_KEY 置空 → 开发模式跳过）。"""
    monkeypatch.setattr(settings, "turnstile_secret_key", "")


@pytest.fixture
def api_headers():
    return {"X-API-Key": "goulong-dev-key"}
