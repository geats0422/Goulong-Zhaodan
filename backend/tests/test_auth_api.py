from __future__ import annotations

import sys
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

import pytest  # noqa: E402
import pytest_asyncio  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402

from core.database import engine, init_db  # noqa: E402
from main import app  # noqa: E402
from tests.conftest import assert_safe_database_for_cleanup  # noqa: E402


VALID_PASSWORD = "TestPass123"


@pytest_asyncio.fixture
async def client():
    await init_db()
    from core.database import async_session
    from sqlalchemy import text

    assert_safe_database_for_cleanup()
    async with async_session() as session:
        for table in [
            "refresh_tokens",
            "knowledge_document_settings",
            "taboo_words",
            "user_profiles",
            "index_nodes",
            "document_versions",
            "knowledge_documents",
            "engineering_subcategories",
            "users",
        ]:
            await session.execute(text(f"DELETE FROM {table}"))
        await session.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    await engine.dispose()


@pytest.mark.asyncio
async def test_register_success(client: AsyncClient):
    resp = await client.post("/auth/register", json={
        "username": "testuser1",
        "password": VALID_PASSWORD,
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["username"] == "testuser1"
    assert "access_token" in data
    assert "refresh_token" in data
    assert "refresh_token" in resp.cookies


@pytest.mark.asyncio
async def test_register_duplicate_username(client: AsyncClient):
    await client.post("/auth/register", json={
        "username": "testuser_dup",
        "password": VALID_PASSWORD,
    })
    resp = await client.post("/auth/register", json={
        "username": "testuser_dup",
        "password": VALID_PASSWORD,
    })
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_register_short_username(client: AsyncClient):
    resp = await client.post("/auth/register", json={
        "username": "ab",
        "password": VALID_PASSWORD,
    })
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_register_password_too_short(client: AsyncClient):
    resp = await client.post("/auth/register", json={
        "username": "validname",
        "password": "Ab1",
    })
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_register_password_no_uppercase(client: AsyncClient):
    resp = await client.post("/auth/register", json={
        "username": "validname2",
        "password": "testpass123",
    })
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_register_password_no_lowercase(client: AsyncClient):
    resp = await client.post("/auth/register", json={
        "username": "validname3",
        "password": "TESTPASS123",
    })
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_register_password_no_digit(client: AsyncClient):
    resp = await client.post("/auth/register", json={
        "username": "validname4",
        "password": "TestPassWord",
    })
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_register_password_has_space(client: AsyncClient):
    resp = await client.post("/auth/register", json={
        "username": "validname5",
        "password": "Test Pass123",
    })
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_register_password_weak(client: AsyncClient):
    resp = await client.post("/auth/register", json={
        "username": "validname6",
        "password": "Password123",
    })
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_register_password_allowed_special(client: AsyncClient):
    resp = await client.post("/auth/register", json={
        "username": "specuser1",
        "password": "TestPass123!",
    })
    assert resp.status_code == 201


@pytest.mark.asyncio
async def test_register_password_disallowed_special(client: AsyncClient):
    resp = await client.post("/auth/register", json={
        "username": "specuser2",
        "password": "TestPass123`",
    })
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_register_password_too_long(client: AsyncClient):
    resp = await client.post("/auth/register", json={
        "username": "longpw",
        "password": "A" * 129 + "a1",
    })
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_login_success(client: AsyncClient):
    await client.post("/auth/register", json={
        "username": "loginuser",
        "password": VALID_PASSWORD,
    })
    resp = await client.post("/auth/login", json={
        "username": "loginuser",
        "password": VALID_PASSWORD,
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["username"] == "loginuser"
    assert "access_token" in data
    assert "refresh_token" in resp.cookies


@pytest.mark.asyncio
async def test_login_trims_username(client: AsyncClient):
    await client.post("/auth/register", json={
        "username": "trimuser",
        "password": VALID_PASSWORD,
    })
    resp = await client.post("/auth/login", json={
        "username": " trimuser ",
        "password": VALID_PASSWORD,
    })
    assert resp.status_code == 200
    assert resp.json()["username"] == "trimuser"


@pytest.mark.asyncio
async def test_login_wrong_password(client: AsyncClient):
    await client.post("/auth/register", json={
        "username": "wrongpass",
        "password": VALID_PASSWORD,
    })
    resp = await client.post("/auth/login", json={
        "username": "wrongpass",
        "password": "WrongPass999",
    })
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_login_nonexistent_user(client: AsyncClient):
    resp = await client.post("/auth/login", json={
        "username": "nonexistent",
        "password": VALID_PASSWORD,
    })
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_refresh_success(client: AsyncClient):
    reg = await client.post("/auth/register", json={
        "username": "refreshuser",
        "password": VALID_PASSWORD,
    })
    refresh_token = reg.json()["refresh_token"]
    client.cookies.set("refresh_token", refresh_token)

    resp = await client.post("/auth/refresh")
    assert resp.status_code == 200
    assert "access_token" in resp.json()


@pytest.mark.asyncio
async def test_refresh_invalid_token(client: AsyncClient):
    client.cookies.set("refresh_token", "invalid.token.here")
    resp = await client.post("/auth/refresh")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_me_success(client: AsyncClient):
    reg = await client.post("/auth/register", json={
        "username": "meuser",
        "password": VALID_PASSWORD,
    })
    access_token = reg.json()["access_token"]

    resp = await client.get("/auth/me", headers={
        "Authorization": f"Bearer {access_token}",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["username"] == "meuser"


@pytest.mark.asyncio
async def test_me_no_token(client: AsyncClient):
    resp = await client.get("/auth/me")
    assert resp.status_code == 401
