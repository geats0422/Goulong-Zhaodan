from __future__ import annotations

import sys
import types
from pathlib import Path
from types import SimpleNamespace
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
    return SimpleNamespace(overall_risk="low", summary="", issues=[], regulation_refs=[])


fake_inspector_module.run_inspection = _fake_run_inspection
sys.modules["app.agents.inspector"] = fake_inspector_module

import pytest  # noqa: E402
import pytest_asyncio  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy import text  # noqa: E402

from app.core.database import async_session, engine, init_db  # noqa: E402
from main import app  # noqa: E402
from app.models.knowledge import EngineeringSubcategory, KnowledgeDocument  # noqa: E402
from tests.conftest import assert_safe_database_for_cleanup  # noqa: E402

VALID_PASSWORD = "TestPass123"


@pytest_asyncio.fixture
async def client():
    from app.core.rate_limit import register_limiter
    register_limiter.reset()
    assert_safe_database_for_cleanup()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def register_and_auth(client: AsyncClient, username: str = "settings_user", password: str = VALID_PASSWORD):
    response = await client.post("/auth/register", json={
        "email": f"{username}@test.com",
        "nickname": username,
        "password": password,
    })
    assert response.status_code == 201
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


async def create_document(title: str = "施工规范") -> int:
    async with async_session() as session:
        sub = EngineeringSubcategory(category_key="traditional", name="房建")
        session.add(sub)
        await session.flush()
        doc = KnowledgeDocument(title=title, subcategory_id=sub.id, owner_type="system")
        session.add(doc)
        await session.commit()
        await session.refresh(doc)
        return doc.id


@pytest.mark.asyncio
async def test_settings_overview_defaults(client: AsyncClient):
    doc_id = await create_document()
    headers = await register_and_auth(client)

    response = await client.get("/settings/overview", headers=headers)

    assert response.status_code == 200
    data = response.json()
    assert data["profile"]["nickname"] == "settings_user"
    assert data["profile"]["subscription_plan"] == "free"
    assert data["profile"]["monthly_quota"] == 50
    assert data["profile"]["quota_used"] == 0
    assert data["profile"]["burn_after_read"] is True
    assert data["taboo_words"] == []
    docs = [doc for cat in data["knowledge"] for sub in cat["subcategories"] for doc in sub["documents"]]
    assert {"id": doc_id, "title": "施工规范", "enabled": True, "owner_type": "system", "application_scenario": "bidding"} in docs


@pytest.mark.asyncio
async def test_update_profile_is_user_scoped(client: AsyncClient):
    user_a = await register_and_auth(client, "profile_a")
    user_b = await register_and_auth(client, "profile_b")

    response = await client.patch(
        "/settings/profile",
        headers=user_a,
        json={"nickname": "张三", "burn_after_read": False},
    )
    assert response.status_code == 200
    assert response.json()["nickname"] == "张三"

    overview_a = await client.get("/settings/overview", headers=user_a)
    overview_b = await client.get("/settings/overview", headers=user_b)
    assert overview_a.json()["profile"]["burn_after_read"] is False
    assert overview_b.json()["profile"]["burn_after_read"] is True


@pytest.mark.asyncio
async def test_update_password(client: AsyncClient):
    headers = await register_and_auth(client, "password_user", "OldPass123")

    bad = await client.post(
        "/settings/password",
        headers=headers,
        json={"old_password": "wrongpass", "new_password": "NewPass456"},
    )
    assert bad.status_code == 400

    short = await client.post(
        "/settings/password",
        headers=headers,
        json={"old_password": "OldPass123", "new_password": "12345"},
    )
    assert short.status_code == 422

    ok = await client.post(
        "/settings/password",
        headers=headers,
        json={"old_password": "OldPass123", "new_password": "NewPass456"},
    )
    assert ok.status_code == 200

    old_login = await client.post("/auth/login", json={"email": "password_user@test.com", "password": "OldPass123"})
    new_login = await client.post("/auth/login", json={"email": "password_user@test.com", "password": "NewPass456"})
    assert old_login.status_code == 401
    assert new_login.status_code == 200


@pytest.mark.asyncio
async def test_password_change_revokes_refresh_tokens(client: AsyncClient):
    reg = await client.post("/auth/register", json={
        "email": "revoke_user@test.com",
        "nickname": "revoke_user",
        "password": "OldPass123",
    })
    access_token = reg.json()["access_token"]
    refresh_token = reg.cookies.get("refresh_token")
    headers = {"Authorization": f"Bearer {access_token}"}

    client.cookies.set("refresh_token", refresh_token)
    refresh_resp = await client.post("/auth/refresh")
    assert refresh_resp.status_code == 200

    pw_resp = await client.post(
        "/settings/password",
        headers=headers,
        json={"old_password": "OldPass123", "new_password": "NewPass456"},
    )
    assert pw_resp.status_code == 200

    client.cookies.set("refresh_token", refresh_token)
    revoked_resp = await client.post("/auth/refresh")
    assert revoked_resp.status_code == 401


@pytest.mark.asyncio
async def test_update_password_rejects_weak(client: AsyncClient):
    headers = await register_and_auth(client, "weakpw_user", "ValidPass123")

    resp = await client.post(
        "/settings/password",
        headers=headers,
        json={"old_password": "ValidPass123", "new_password": "Password123"},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_toggle_knowledge_document_is_user_scoped(client: AsyncClient):
    doc_id = await create_document("可切换文档")
    user_a = await register_and_auth(client, "knowledge_a")
    user_b = await register_and_auth(client, "knowledge_b")

    missing = await client.patch("/settings/knowledge/documents/9999", headers=user_a, json={"enabled": False})
    assert missing.status_code == 404

    disabled = await client.patch(f"/settings/knowledge/documents/{doc_id}", headers=user_a, json={"enabled": False})
    assert disabled.status_code == 200
    assert disabled.json()["enabled"] is False

    overview_a = await client.get("/settings/overview", headers=user_a)
    overview_b = await client.get("/settings/overview", headers=user_b)
    docs_a = [doc for cat in overview_a.json()["knowledge"] for sub in cat["subcategories"] for doc in sub["documents"]]
    docs_b = [doc for cat in overview_b.json()["knowledge"] for sub in cat["subcategories"] for doc in sub["documents"]]
    assert next(doc for doc in docs_a if doc["id"] == doc_id)["enabled"] is False
    assert next(doc for doc in docs_b if doc["id"] == doc_id)["enabled"] is True


@pytest.mark.asyncio
async def test_taboo_words_crud_is_user_scoped(client: AsyncClient):
    user_a = await register_and_auth(client, "taboo_a")
    user_b = await register_and_auth(client, "taboo_b")

    created = await client.post(
        "/settings/taboo-words",
        headers=user_a,
        json={"word": "内部绝密代号X7", "replacement": "项目编号", "note": "测试"},
    )
    assert created.status_code == 201
    word_id = created.json()["id"]

    duplicate = await client.post("/settings/taboo-words", headers=user_a, json={"word": "内部绝密代号X7"})
    assert duplicate.status_code == 409

    isolated = await client.get("/settings/overview", headers=user_b)
    assert isolated.json()["taboo_words"] == []

    updated = await client.patch(
        f"/settings/taboo-words/{word_id}",
        headers=user_a,
        json={"word": "内部代号", "replacement": "项目编号", "note": "已更新"},
    )
    assert updated.status_code == 200
    assert updated.json()["word"] == "内部代号"

    missing = await client.patch("/settings/taboo-words/9999", headers=user_a, json={"word": "不存在"})
    assert missing.status_code == 404

    deleted = await client.delete(f"/settings/taboo-words/{word_id}", headers=user_a)
    assert deleted.status_code == 204
    overview = await client.get("/settings/overview", headers=user_a)
    assert overview.json()["taboo_words"] == []


@pytest.mark.asyncio
async def test_inspection_upload_merges_saved_and_temporary_taboo_words(client: AsyncClient, monkeypatch):
    headers = await register_and_auth(client, "inspect_user")
    await client.post("/settings/taboo-words", headers=headers, json={"word": "保存词"})
    captured = {}

    async def fake_run_inspection(text, deps):
        captured["taboo_words"] = deps.taboo_words
        return SimpleNamespace(overall_risk="low", summary="", issues=[], regulation_refs=[])

    import app.api.v1.inspection as inspection_router

    monkeypatch.setattr(inspection_router, "run_inspection", fake_run_inspection)
    response = await client.post(
        "/inspection/upload",
        headers=headers,
        files={"file": ("test.txt", "这是一个足够长的工程文档内容", "text/plain")},
        data={"taboo_words": "临时词,保存词"},
    )

    assert response.status_code == 200
    assert captured["taboo_words"] == ["保存词", "临时词"]


@pytest.mark.asyncio
async def test_overview_includes_model_env(client: AsyncClient):
    headers = await register_and_auth(client, "modelenv_user")

    response = await client.get("/settings/overview", headers=headers)

    assert response.status_code == 200
    profile = response.json()["profile"]
    for field in [
        "model_name",
        "model_base_url",
        "model_api_key_preview",
        "model_catalog",
        "subscription_label",
        "subscription_period",
        "subscription_price",
    ]:
        assert field in profile
    assert isinstance(profile["model_catalog"], list)
    assert len(profile["model_catalog"]) >= 2


@pytest.mark.asyncio
async def test_update_profile_nickname(client: AsyncClient):
    headers = await register_and_auth(client, "username_user")

    resp = await client.patch("/settings/profile", headers=headers, json={"nickname": "newname1"})
    assert resp.status_code == 200
    assert resp.json()["nickname"] == "newname1"

    overview = await client.get("/settings/overview", headers=headers)
    assert overview.json()["profile"]["nickname"] == "newname1"


@pytest.mark.asyncio
async def test_update_profile_subscription_plan_removed(client: AsyncClient):
    headers = await register_and_auth(client, "subplan_user")

    resp = await client.patch("/settings/profile", headers=headers, json={"subscription_plan": "team"})
    assert resp.status_code == 200
    overview = await client.get("/settings/overview", headers=headers)
    assert overview.json()["profile"]["subscription_plan"] == "free"


@pytest.mark.asyncio
async def test_update_profile_model_name(client: AsyncClient):
    headers = await register_and_auth(client, "modelname_user")

    resp = await client.patch("/settings/profile", headers=headers, json={"model_name": "deepseek-ai/deepseek-v4-pro"})
    assert resp.status_code == 200

    overview = await client.get("/settings/overview", headers=headers)
    assert overview.json()["profile"]["model_name"] == "deepseek-ai/deepseek-v4-pro"


@pytest.mark.asyncio
async def test_update_profile_model_name_invalid(client: AsyncClient):
    headers = await register_and_auth(client, "modelinvalid_user")

    resp = await client.patch("/settings/profile", headers=headers, json={"model_name": "gpt-4o"})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_update_profile_phone(client: AsyncClient):
    headers = await register_and_auth(client, "phone_user")

    resp = await client.patch("/settings/profile", headers=headers, json={"phone": "13800138000"})
    assert resp.status_code == 200
    assert resp.json()["phone"] == "138****8000"

    overview = await client.get("/settings/overview", headers=headers)
    assert overview.json()["profile"]["phone"] == "138****8000"


@pytest.mark.asyncio
async def test_update_profile_phone_unique_conflict(client: AsyncClient):
    headers_a = await register_and_auth(client, "phone_a")
    headers_b = await register_and_auth(client, "phone_b")

    first = await client.patch("/settings/profile", headers=headers_a, json={"phone": "13800138000"})
    assert first.status_code == 200

    conflict = await client.patch("/settings/profile", headers=headers_b, json={"phone": "13800138000"})
    assert conflict.status_code == 409


@pytest.mark.asyncio
async def test_update_profile_email(client: AsyncClient):
    headers = await register_and_auth(client, "email_user")

    resp = await client.patch("/settings/profile", headers=headers, json={"email": "test@example.com"})
    assert resp.status_code == 200
    assert resp.json()["email"] == "t***t@example.com"


@pytest.mark.asyncio
async def test_overview_includes_scope_templates(client: AsyncClient):
    headers = await register_and_auth(client, "scope_user")

    resp = await client.get("/settings/overview", headers=headers)
    assert resp.status_code == 200
    scope_templates = resp.json()["profile"]["scope_templates"]
    assert isinstance(scope_templates, list)
    assert len(scope_templates) == 5
    template_keys = {t["key"] for t in scope_templates}
    assert "mcp_inspect" in template_keys
    for template in scope_templates:
        assert "key" in template
        assert "label" in template
        assert "description" in template
        assert "scopes" in template


@pytest.mark.asyncio
async def test_get_api_key_secret_updates_last_viewed_at(client: AsyncClient):
    headers = await register_and_auth(client, "apikey_view_user")

    create_resp = await client.post(
        "/settings/api-keys",
        headers=headers,
        json={"name": "test-key", "client_type": "agent", "scope_template": "mcp_readonly"},
    )
    assert create_resp.status_code == 201
    key_id = create_resp.json()["id"]

    secret_resp = await client.get(f"/settings/api-keys/{key_id}/secret", headers=headers)
    assert secret_resp.status_code == 200
    assert "full_key" in secret_resp.json()

    list_resp = await client.get("/settings/api-keys", headers=headers)
    assert list_resp.status_code == 200
    matched = [k for k in list_resp.json() if k["id"] == key_id]
    assert len(matched) == 1
    assert matched[0]["last_viewed_at"] is not None
