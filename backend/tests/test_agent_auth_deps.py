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

from fastapi import Depends, FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from core.agent_auth import get_api_key_user, require_api_scope
from core.database import get_db_session
from models import Base
from models.api_keys import ApiKey
from services.api_key_service import create_api_key
from models.knowledge import User


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
    user = User(username="auth_tester", hashed_password="fakehash")
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user.id


def make_app(session_factory):
    app = FastAPI()

    async def override_get_db():
        async with session_factory() as sess:
            yield sess

    app.dependency_overrides[get_db_session] = override_get_db

    @app.get("/test-me")
    async def test_me(user: dict = Depends(get_api_key_user)):
        return user

    @app.get("/test-scope")
    async def test_scope(user: dict = Depends(require_api_scope("inspection:run"))):
        return user

    return app


@pytest_asyncio.fixture
def app(session_factory):
    return make_app(session_factory)


@pytest_asyncio.fixture
def client(app):
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")


@pytest.mark.asyncio
async def test_no_auth_header(client):
    async with client as c:
        resp = await c.get("/test-me")
    assert resp.status_code == 401
    assert resp.json()["detail"] == "invalid_api_key"


@pytest.mark.asyncio
async def test_invalid_bearer_format(client):
    async with client as c:
        resp = await c.get("/test-me", headers={"Authorization": "Basic abc"})
    assert resp.status_code == 401
    assert resp.json()["detail"] == "invalid_api_key"


@pytest.mark.asyncio
async def test_bearer_wrong_prefix(client):
    async with client as c:
        resp = await c.get(
            "/test-me", headers={"Authorization": "Bearer wrong_prefix_abc123"}
        )
    assert resp.status_code == 401
    assert resp.json()["detail"] == "invalid_api_key"


@pytest.mark.asyncio
async def test_invalid_api_key(client):
    async with client as c:
        resp = await c.get(
            "/test-me",
            headers={"Authorization": "Bearer glzd_live_nonexistent00000000000000000"},
        )
    assert resp.status_code == 401
    assert resp.json()["detail"] == "invalid_api_key"


@pytest.mark.asyncio
async def test_revoked_api_key(client, db, user_id):
    result = await create_api_key(
        db=db,
        user_id=user_id,
        name="Revoked Key",
        client_type="mcp",
        scope_template="mcp_readonly",
    )
    full_key = result["full_key"]

    from services.api_key_service import revoke_api_key

    await revoke_api_key(db, result["api_key"].id, user_id)

    async with client as c:
        resp = await c.get(
            "/test-me", headers={"Authorization": f"Bearer {full_key}"}
        )
    assert resp.status_code == 401
    assert resp.json()["detail"] == "api_key_revoked"


@pytest.mark.asyncio
async def test_expired_api_key(client, db, user_id):
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

    async with client as c:
        resp = await c.get(
            "/test-me", headers={"Authorization": f"Bearer {full_key}"}
        )
    assert resp.status_code == 401
    assert resp.json()["detail"] == "api_key_expired"


@pytest.mark.asyncio
async def test_valid_api_key(client, db, user_id):
    result = await create_api_key(
        db=db,
        user_id=user_id,
        name="Valid Key",
        client_type="cli",
        scope_template="cli_inspection",
    )
    full_key = result["full_key"]

    async with client as c:
        resp = await c.get(
            "/test-me", headers={"Authorization": f"Bearer {full_key}"}
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["user_id"] == user_id
    assert body["api_key_id"] == result["api_key"].id
    assert "inspection:run" in body["scopes"]


@pytest.mark.asyncio
async def test_valid_api_key_updates_last_used_at(client, db, user_id):
    from sqlalchemy import select

    result = await create_api_key(
        db=db,
        user_id=user_id,
        name="LastUsed Key",
        client_type="mcp",
        scope_template="mcp_readonly",
    )
    full_key = result["full_key"]
    key_id = result["api_key"].id

    stmt = select(ApiKey).where(ApiKey.id == key_id)
    db_result = await db.execute(stmt)
    before = db_result.scalar_one()
    assert before.last_used_at is None

    async with client as c:
        resp = await c.get(
            "/test-me", headers={"Authorization": f"Bearer {full_key}"}
        )
    assert resp.status_code == 200

    await db.refresh(before)
    assert before.last_used_at is not None


@pytest.mark.asyncio
async def test_scope_sufficient(client, db, user_id):
    result = await create_api_key(
        db=db,
        user_id=user_id,
        name="Scoped Key",
        client_type="cli",
        scope_template="cli_inspection",
    )
    full_key = result["full_key"]

    async with client as c:
        resp = await c.get(
            "/test-scope", headers={"Authorization": f"Bearer {full_key}"}
        )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_scope_insufficient(client, db, user_id):
    result = await create_api_key(
        db=db,
        user_id=user_id,
        name="Limited Key",
        client_type="mcp",
        scope_template="mcp_readonly",
    )
    full_key = result["full_key"]

    async with client as c:
        resp = await c.get(
            "/test-scope", headers={"Authorization": f"Bearer {full_key}"}
        )
    assert resp.status_code == 403
    assert resp.json()["detail"] == "insufficient_scope"
