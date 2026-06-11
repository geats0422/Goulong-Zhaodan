from __future__ import annotations

import os
import sys
import types
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
import pytest_asyncio

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

for mod_name in [
    "markitdown",
    "pageindex",
    "pydantic_ai",
    "pydantic_ai.agent",
    "pydantic_ai.models",
]:
    if mod_name not in sys.modules:
        sys.modules[mod_name] = types.ModuleType(mod_name)

os.environ["API_KEY_ENCRYPTION_SECRET"] = "test-secret-for-unit-tests"

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from models import Base
from models.api_keys import ApiKey
from models.knowledge import User
from services.api_key_service import (
    authenticate_api_key,
    create_api_key,
    get_api_key_secret,
    list_api_keys,
    revoke_api_key,
    update_api_key,
)


@pytest_asyncio.fixture
async def engine():
    eng = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    await eng.dispose()


@pytest_asyncio.fixture
def session_factory(engine):
    return sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


@pytest_asyncio.fixture
async def db(session_factory):
    async with session_factory() as sess:
        yield sess


@pytest_asyncio.fixture
async def user_id(db: AsyncSession) -> int:
    user = User(username="service_tester", hashed_password="fakehash")
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user.id


@pytest_asyncio.fixture
async def other_user_id(db: AsyncSession) -> int:
    user = User(username="other_tester", hashed_password="fakehash")
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user.id


@pytest.mark.asyncio
async def test_create_api_key(db: AsyncSession, user_id: int):
    result = await create_api_key(
        db=db,
        user_id=user_id,
        name="测试 Key",
        client_type="mcp",
        scope_template="mcp_readonly",
    )

    assert result["full_key"].startswith("glzd_live_")
    api_key = result["api_key"]
    assert api_key.id is not None
    assert api_key.user_id == user_id
    assert api_key.name == "测试 Key"
    assert api_key.client_type == "mcp"
    assert api_key.status == "active"

    stmt = select(ApiKey).where(ApiKey.id == api_key.id)
    db_result = await db.execute(stmt)
    db_key = db_result.scalar_one()
    assert db_key.key_prefix == api_key.key_prefix


@pytest.mark.asyncio
async def test_create_api_key_with_template(db: AsyncSession, user_id: int):
    result = await create_api_key(
        db=db,
        user_id=user_id,
        name="模板 Key",
        client_type="cli",
        scope_template="cli_inspection",
    )

    api_key = result["api_key"]
    assert api_key.scopes == [
        "profile:read",
        "inspection:run",
        "inspection:read",
        "knowledge:read",
    ]
    assert api_key.scope_template == "cli_inspection"


@pytest.mark.asyncio
async def test_create_api_key_custom(db: AsyncSession, user_id: int):
    result = await create_api_key(
        db=db,
        user_id=user_id,
        name="自定义 Key",
        client_type="agent",
        scope_template="custom",
        user_scopes=["profile:read", "knowledge:read", "knowledge:write"],
    )

    api_key = result["api_key"]
    assert api_key.scopes == ["profile:read", "knowledge:read", "knowledge:write"]
    assert api_key.scope_template == "custom"


@pytest.mark.asyncio
async def test_list_api_keys(db: AsyncSession, user_id: int):
    await create_api_key(
        db=db,
        user_id=user_id,
        name="Key A",
        client_type="mcp",
        scope_template="mcp_readonly",
    )
    await create_api_key(
        db=db,
        user_id=user_id,
        name="Key B",
        client_type="cli",
        scope_template="cli_inspection",
    )

    keys = await list_api_keys(db, user_id)
    assert len(keys) == 2

    for key in keys:
        assert key.encrypted_key is None
        assert key.key_hash is None
        assert key.name in ("Key A", "Key B")


@pytest.mark.asyncio
async def test_list_api_keys_user_isolation(
    db: AsyncSession, user_id: int, other_user_id: int
):
    await create_api_key(
        db=db,
        user_id=user_id,
        name="User1 Key",
        client_type="mcp",
        scope_template="mcp_readonly",
    )
    await create_api_key(
        db=db,
        user_id=other_user_id,
        name="User2 Key",
        client_type="cli",
        scope_template="cli_inspection",
    )

    keys_user1 = await list_api_keys(db, user_id)
    keys_user2 = await list_api_keys(db, other_user_id)

    assert len(keys_user1) == 1
    assert keys_user1[0].name == "User1 Key"
    assert len(keys_user2) == 1
    assert keys_user2[0].name == "User2 Key"


@pytest.mark.asyncio
async def test_get_api_key_secret(db: AsyncSession, user_id: int):
    result = await create_api_key(
        db=db,
        user_id=user_id,
        name="Secret Key",
        client_type="mcp",
        scope_template="mcp_readonly",
    )
    full_key = result["full_key"]
    key_id = result["api_key"].id

    secret = await get_api_key_secret(db, key_id, user_id)
    assert secret == full_key

    stmt = select(ApiKey).where(ApiKey.id == key_id)
    db_result = await db.execute(stmt)
    db_key = db_result.scalar_one()
    assert db_key.last_viewed_at is not None


@pytest.mark.asyncio
async def test_get_api_key_secret_not_found(db: AsyncSession, user_id: int):
    secret = await get_api_key_secret(db, 99999, user_id)
    assert secret is None


@pytest.mark.asyncio
async def test_get_api_key_secret_wrong_user(
    db: AsyncSession, user_id: int, other_user_id: int
):
    result = await create_api_key(
        db=db,
        user_id=user_id,
        name="Owned Key",
        client_type="mcp",
        scope_template="mcp_readonly",
    )
    key_id = result["api_key"].id

    secret = await get_api_key_secret(db, key_id, other_user_id)
    assert secret is None


@pytest.mark.asyncio
async def test_update_api_key_name(db: AsyncSession, user_id: int):
    result = await create_api_key(
        db=db,
        user_id=user_id,
        name="旧名称",
        client_type="mcp",
        scope_template="mcp_readonly",
    )
    key_id = result["api_key"].id

    updated = await update_api_key(db, key_id, user_id, name="新名称")
    assert updated is not None
    assert updated.name == "新名称"


@pytest.mark.asyncio
async def test_revoke_api_key(db: AsyncSession, user_id: int):
    result = await create_api_key(
        db=db,
        user_id=user_id,
        name="待撤销",
        client_type="mcp",
        scope_template="mcp_readonly",
    )
    key_id = result["api_key"].id

    revoked = await revoke_api_key(db, key_id, user_id)
    assert revoked is not None
    assert revoked.status == "revoked"
    assert revoked.revoked_at is not None


@pytest.mark.asyncio
async def test_authenticate_api_key_valid(db: AsyncSession, user_id: int):
    result = await create_api_key(
        db=db,
        user_id=user_id,
        name="Auth Key",
        client_type="mcp",
        scope_template="mcp_readonly",
    )
    full_key = result["full_key"]
    key_id = result["api_key"].id

    authenticated = await authenticate_api_key(db, full_key)
    assert authenticated is not None
    assert authenticated.id == key_id

    stmt = select(ApiKey).where(ApiKey.id == key_id)
    db_result = await db.execute(stmt)
    db_key = db_result.scalar_one()
    assert db_key.last_used_at is not None


@pytest.mark.asyncio
async def test_authenticate_api_key_invalid(db: AsyncSession, user_id: int):
    result = await authenticate_api_key(db, "glzd_live_invalidkey0000000000000000000000")
    assert result is None


@pytest.mark.asyncio
async def test_authenticate_api_key_revoked(db: AsyncSession, user_id: int):
    result = await create_api_key(
        db=db,
        user_id=user_id,
        name="Revoked Auth",
        client_type="mcp",
        scope_template="mcp_readonly",
    )
    full_key = result["full_key"]
    key_id = result["api_key"].id

    await revoke_api_key(db, key_id, user_id)

    authenticated = await authenticate_api_key(db, full_key)
    assert authenticated is None


@pytest.mark.asyncio
async def test_authenticate_api_key_expired(db: AsyncSession, user_id: int):
    expired_at = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=1)
    result = await create_api_key(
        db=db,
        user_id=user_id,
        name="Expired Key",
        client_type="mcp",
        scope_template="mcp_readonly",
        expires_at=expired_at,
    )
    full_key = result["full_key"]

    authenticated = await authenticate_api_key(db, full_key)
    assert authenticated is None
