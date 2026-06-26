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

fake_inspector_module = types.ModuleType("app.agents.inspector")


async def _fake_run_inspection(*args, **kwargs):
    return {"overall_risk": "low", "summary": "", "issues": [], "regulation_refs": []}


fake_inspector_module.run_inspection = _fake_run_inspection
sys.modules["app.agents.inspector"] = fake_inspector_module

import pytest  # noqa: E402
import pytest_asyncio  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402

from app.core.database import engine, init_db  # noqa: E402
from main import app  # noqa: E402
from tests.conftest import assert_safe_database_for_cleanup  # noqa: E402


VALID_PASSWORD = "TestPass123"


@pytest_asyncio.fixture
async def client():
    from app.core.rate_limit import register_limiter

    assert_safe_database_for_cleanup()
    register_limiter.reset()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.mark.asyncio
async def test_register_success(client: AsyncClient):
    resp = await client.post("/auth/register", json={
        "email": "testuser1@example.com",
        "nickname": "testuser1",
        "password": VALID_PASSWORD,
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["nickname"] == "testuser1"
    assert data["email"] == "t***1@example.com"
    assert "access_token" in data
    assert "refresh_token" not in data
    assert "refresh_token" in resp.cookies


@pytest.mark.asyncio
async def test_register_duplicate_email(client: AsyncClient):
    await client.post("/auth/register", json={
        "email": "dup@example.com",
        "nickname": "testuser_dup",
        "password": VALID_PASSWORD,
    })
    resp = await client.post("/auth/register", json={
        "email": "dup@example.com",
        "nickname": "testuser_dup2",
        "password": VALID_PASSWORD,
    })
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_register_missing_identity(client: AsyncClient):
    resp = await client.post("/auth/register", json={
        "nickname": "noid_user",
        "password": VALID_PASSWORD,
    })
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_register_password_too_short(client: AsyncClient):
    resp = await client.post("/auth/register", json={
        "email": "shortpw@example.com",
        "nickname": "validname",
        "password": "Ab1",
    })
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_register_password_no_uppercase(client: AsyncClient):
    resp = await client.post("/auth/register", json={
        "email": "noupc@example.com",
        "nickname": "validname2",
        "password": "testpass123",
    })
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_register_password_no_lowercase(client: AsyncClient):
    resp = await client.post("/auth/register", json={
        "email": "nolow@example.com",
        "nickname": "validname3",
        "password": "TESTPASS123",
    })
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_register_password_no_digit(client: AsyncClient):
    resp = await client.post("/auth/register", json={
        "email": "nodig@example.com",
        "nickname": "validname4",
        "password": "TestPassWord",
    })
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_register_password_has_space(client: AsyncClient):
    resp = await client.post("/auth/register", json={
        "email": "spacepw@example.com",
        "nickname": "validname5",
        "password": "Test Pass123",
    })
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_register_password_weak(client: AsyncClient):
    resp = await client.post("/auth/register", json={
        "email": "weakpw@example.com",
        "nickname": "validname6",
        "password": "Password123",
    })
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_register_password_allowed_special(client: AsyncClient):
    resp = await client.post("/auth/register", json={
        "email": "specuser1@example.com",
        "nickname": "specuser1",
        "password": "TestPass123!",
    })
    assert resp.status_code == 201


@pytest.mark.asyncio
async def test_register_password_disallowed_special(client: AsyncClient):
    resp = await client.post("/auth/register", json={
        "email": "specuser2@example.com",
        "nickname": "specuser2",
        "password": "TestPass123`",
    })
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_register_password_too_long(client: AsyncClient):
    resp = await client.post("/auth/register", json={
        "email": "longpw@example.com",
        "nickname": "longpw",
        "password": "A" * 129 + "a1",
    })
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_login_success(client: AsyncClient):
    await client.post("/auth/register", json={
        "email": "login@example.com",
        "nickname": "loginuser",
        "password": VALID_PASSWORD,
    })
    resp = await client.post("/auth/login", json={
        "email": "login@example.com",
        "password": VALID_PASSWORD,
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["nickname"] == "loginuser"
    assert "access_token" in data
    assert "refresh_token" in resp.cookies


@pytest.mark.asyncio
async def test_login_wrong_password(client: AsyncClient):
    await client.post("/auth/register", json={
        "email": "wrongpw@example.com",
        "nickname": "wrongpass",
        "password": VALID_PASSWORD,
    })
    resp = await client.post("/auth/login", json={
        "email": "wrongpw@example.com",
        "password": "WrongPass999",
    })
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_login_nonexistent_user(client: AsyncClient):
    resp = await client.post("/auth/login", json={
        "email": "nonexistent@example.com",
        "password": VALID_PASSWORD,
    })
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_refresh_success(client: AsyncClient):
    reg = await client.post("/auth/register", json={
        "email": "refresh@example.com",
        "nickname": "refreshuser",
        "password": VALID_PASSWORD,
    })
    refresh_token = reg.cookies.get("refresh_token")
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
        "email": "me@example.com",
        "nickname": "meuser",
        "password": VALID_PASSWORD,
    })
    access_token = reg.json()["access_token"]

    resp = await client.get("/auth/me", headers={
        "Authorization": f"Bearer {access_token}",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["nickname"] == "meuser"


@pytest.mark.asyncio
async def test_me_no_token(client: AsyncClient):
    resp = await client.get("/auth/me")
    assert resp.status_code == 401
