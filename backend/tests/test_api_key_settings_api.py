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
    from types import SimpleNamespace
    return SimpleNamespace(overall_risk="low", summary="", issues=[], regulation_refs=[])


fake_inspector_module.run_inspection = _fake_run_inspection
sys.modules["agents.inspector"] = fake_inspector_module

import pytest  # noqa: E402
import pytest_asyncio  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine  # noqa: E402

VALID_PASSWORD = "TestPass123"
SQLITE_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture
async def client():
    import core.database as db_mod
    from models import Base

    test_engine = create_async_engine(SQLITE_URL, echo=False)
    test_session_factory = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    original_engine = db_mod.engine
    original_session = db_mod.async_session
    db_mod.engine = test_engine
    db_mod.async_session = test_session_factory

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c

    db_mod.engine = original_engine
    db_mod.async_session = original_session
    await test_engine.dispose()


from main import app  # noqa: E402


async def register_and_auth(client: AsyncClient, username: str = "apikey_user", password: str = VALID_PASSWORD):
    response = await client.post("/auth/register", json={"username": username, "password": password})
    assert response.status_code == 201
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


async def _create_key(client: AsyncClient, headers: dict, name: str = "测试 Key"):
    return await client.post(
        "/settings/api-keys",
        headers=headers,
        json={
            "name": name,
            "client_type": "cli",
            "scope_template": "cli_inspection",
        },
    )


@pytest.mark.asyncio
async def test_create_api_key(client: AsyncClient):
    headers = await register_and_auth(client, "create_user")

    response = await _create_key(client, headers)

    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "测试 Key"
    assert data["client_type"] == "cli"
    assert data["scope_template"] == "cli_inspection"
    assert isinstance(data["scopes"], list)
    assert len(data["scopes"]) > 0
    assert data["key_prefix"].startswith("glzd_live_")
    assert data["status"] == "active"
    assert isinstance(data["id"], int)


@pytest.mark.asyncio
async def test_create_api_key_response_has_full_key(client: AsyncClient):
    headers = await register_and_auth(client, "fullkey_user")

    response = await _create_key(client, headers)

    assert response.status_code == 201
    data = response.json()
    assert "full_key" in data
    assert data["full_key"].startswith("glzd_live_")
    assert len(data["full_key"]) > 20


@pytest.mark.asyncio
async def test_list_api_keys(client: AsyncClient):
    headers = await register_and_auth(client, "list_user")
    await _create_key(client, headers, "Key A")
    await _create_key(client, headers, "Key B")

    response = await client.get("/settings/api-keys", headers=headers)

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    names = {item["name"] for item in data}
    assert names == {"Key A", "Key B"}
    for item in data:
        assert "full_key" not in item
        assert "encrypted_key" not in item
        assert "key_hash" not in item


@pytest.mark.asyncio
async def test_list_api_keys_empty(client: AsyncClient):
    headers = await register_and_auth(client, "empty_user")

    response = await client.get("/settings/api-keys", headers=headers)

    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_get_api_key_secret(client: AsyncClient):
    headers = await register_and_auth(client, "secret_user")
    created = await _create_key(client, headers)
    key_id = created.json()["id"]
    original_full_key = created.json()["full_key"]

    response = await client.get(f"/settings/api-keys/{key_id}/secret", headers=headers)

    assert response.status_code == 200
    data = response.json()
    assert data["full_key"] == original_full_key


@pytest.mark.asyncio
async def test_get_api_key_secret_updates_last_viewed_at(client: AsyncClient):
    headers = await register_and_auth(client, "viewed_user")
    created = await _create_key(client, headers)
    key_id = created.json()["id"]

    assert created.json()["last_viewed_at"] is None

    await client.get(f"/settings/api-keys/{key_id}/secret", headers=headers)

    listed = await client.get("/settings/api-keys", headers=headers)
    keys = listed.json()
    target = next(k for k in keys if k["id"] == key_id)
    assert target["last_viewed_at"] is not None


@pytest.mark.asyncio
async def test_get_api_key_secret_not_found(client: AsyncClient):
    headers = await register_and_auth(client, "notfound_user")

    response = await client.get("/settings/api-keys/9999/secret", headers=headers)

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_update_api_key(client: AsyncClient):
    headers = await register_and_auth(client, "update_user")
    created = await _create_key(client, headers)
    key_id = created.json()["id"]

    response = await client.patch(
        f"/settings/api-keys/{key_id}",
        headers=headers,
        json={"name": "新名称"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "新名称"
    assert data["id"] == key_id


@pytest.mark.asyncio
async def test_revoke_api_key(client: AsyncClient):
    headers = await register_and_auth(client, "revoke_user")
    created = await _create_key(client, headers)
    key_id = created.json()["id"]

    response = await client.delete(f"/settings/api-keys/{key_id}", headers=headers)

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "revoked"


@pytest.mark.asyncio
async def test_revoke_api_key_not_found(client: AsyncClient):
    headers = await register_and_auth(client, "revoke_nf_user")

    response = await client.delete("/settings/api-keys/9999", headers=headers)

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_api_key_user_isolation(client: AsyncClient):
    headers_a = await register_and_auth(client, "isolate_a")
    headers_b = await register_and_auth(client, "isolate_b")

    created = await _create_key(client, headers_a, "A 的 Key")
    key_id = created.json()["id"]

    list_b = await client.get("/settings/api-keys", headers=headers_b)
    assert list_b.status_code == 200
    assert all(k["id"] != key_id for k in list_b.json())

    secret_b = await client.get(f"/settings/api-keys/{key_id}/secret", headers=headers_b)
    assert secret_b.status_code == 404

    update_b = await client.patch(f"/settings/api-keys/{key_id}", headers=headers_b, json={"name": "被篡改"})
    assert update_b.status_code == 404

    delete_b = await client.delete(f"/settings/api-keys/{key_id}", headers=headers_b)
    assert delete_b.status_code == 404

    list_a = await client.get("/settings/api-keys", headers=headers_a)
    assert any(k["id"] == key_id for k in list_a.json())


@pytest.mark.asyncio
async def test_api_key_cannot_access_settings_password(client: AsyncClient):
    jwt_headers = await register_and_auth(client, "apikey_blocked_user", "TestPass123")

    created = await client.post(
        "/settings/api-keys",
        headers=jwt_headers,
        json={
            "name": "Blocked Key",
            "client_type": "agent",
            "scope_template": "agent_automation",
        },
    )
    assert created.status_code == 201
    full_key = created.json()["full_key"]
    api_headers = {"Authorization": f"Bearer {full_key}"}

    resp = await client.post(
        "/settings/password",
        headers=api_headers,
        json={"old_password": "TestPass123", "new_password": "NewPass456"},
    )

    assert resp.status_code == 401
