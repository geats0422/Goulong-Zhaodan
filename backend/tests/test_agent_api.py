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
    from types import SimpleNamespace

    return SimpleNamespace(overall_risk="low", summary="", issues=[], regulation_refs=[])


fake_inspector_module.run_inspection = _fake_run_inspection
sys.modules["app.agents.inspector"] = fake_inspector_module

import pytest  # noqa: E402
import pytest_asyncio  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine  # noqa: E402

VALID_PASSWORD = "TestPass123"


@pytest_asyncio.fixture
async def client():
    from app.core.database import engine
    from app.core.rate_limit import register_limiter

    register_limiter.reset()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


from main import app  # noqa: E402


async def register_user(client: AsyncClient, username: str = "agent_user", password: str = VALID_PASSWORD):
    response = await client.post("/auth/register", json={
        "email": f"{username}@test.com",
        "nickname": username,
        "password": password,
    })
    assert response.status_code == 201
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


async def create_agent_api_key(
    client: AsyncClient,
    jwt_headers: dict,
    scope_template: str = "agent_automation",
    name: str = "测试 Agent Key",
):
    response = await client.post(
        "/settings/api-keys",
        headers=jwt_headers,
        json={
            "name": name,
            "client_type": "agent",
            "scope_template": scope_template,
        },
    )
    assert response.status_code == 201
    full_key = response.json()["full_key"]
    return {"Authorization": f"Bearer {full_key}"}


@pytest.mark.asyncio
async def test_agent_me(client: AsyncClient):
    jwt_headers = await register_user(client, "me_user")
    api_headers = await create_agent_api_key(client, jwt_headers)

    response = await client.get("/api/v1/agent/me", headers=api_headers)

    assert response.status_code == 200
    data = response.json()
    assert "user_id" in data
    assert "api_key_id" in data
    assert "scopes" in data
    assert isinstance(data["scopes"], list)
    assert len(data["scopes"]) > 0


@pytest.mark.asyncio
async def test_agent_me_no_auth(client: AsyncClient):
    response = await client.get("/api/v1/agent/me")

    assert response.status_code == 401
    assert response.json()["detail"] == "invalid_api_key"


@pytest.mark.asyncio
async def test_create_inspect_job(client: AsyncClient):
    jwt_headers = await register_user(client, "inspect_user")
    api_headers = await create_agent_api_key(client, jwt_headers)

    response = await client.post("/api/v1/agent/jobs/inspect", headers=api_headers, json={})

    assert response.status_code == 201
    data = response.json()
    assert "job_id" in data
    assert data["status"] == "queued"
    assert data["job_type"] == "inspect"
    assert data["progress"] == 0


@pytest.mark.asyncio
async def test_create_parse_job(client: AsyncClient):
    jwt_headers = await register_user(client, "parse_user")
    api_headers = await create_agent_api_key(client, jwt_headers)

    response = await client.post("/api/v1/agent/jobs/parse", headers=api_headers, json={})

    assert response.status_code == 201
    data = response.json()
    assert "job_id" in data
    assert data["status"] == "queued"
    assert data["job_type"] == "parse"
    assert data["progress"] == 0


@pytest.mark.asyncio
async def test_get_job_status(client: AsyncClient):
    jwt_headers = await register_user(client, "status_user")
    api_headers = await create_agent_api_key(client, jwt_headers)

    created = await client.post("/api/v1/agent/jobs/inspect", headers=api_headers, json={})
    job_id = created.json()["job_id"]

    response = await client.get(f"/api/v1/agent/jobs/{job_id}", headers=api_headers)

    assert response.status_code == 200
    data = response.json()
    assert data["job_id"] == job_id
    assert data["status"] == "queued"
    assert data["progress"] == 0
    assert "created_at" in data


@pytest.mark.asyncio
async def test_get_job_not_found(client: AsyncClient):
    jwt_headers = await register_user(client, "nf_user")
    api_headers = await create_agent_api_key(client, jwt_headers)

    response = await client.get("/api/v1/agent/jobs/job_nonexistent", headers=api_headers)

    assert response.status_code == 404
    assert response.json()["detail"] == "job_not_found"


@pytest.mark.asyncio
async def test_get_job_not_owner(client: AsyncClient):
    jwt_a = await register_user(client, "owner_a")
    api_a = await create_agent_api_key(client, jwt_a)

    created = await client.post("/api/v1/agent/jobs/inspect", headers=api_a, json={})
    job_id = created.json()["job_id"]

    jwt_b = await register_user(client, "owner_b")
    api_b = await create_agent_api_key(client, jwt_b)

    response = await client.get(f"/api/v1/agent/jobs/{job_id}", headers=api_b)

    assert response.status_code == 404
    assert response.json()["detail"] == "job_not_found"


@pytest.mark.asyncio
async def test_inspect_job_no_scope(client: AsyncClient):
    jwt_headers = await register_user(client, "noscope_user")
    api_headers = await create_agent_api_key(client, jwt_headers, scope_template="mcp_readonly")

    response = await client.post("/api/v1/agent/jobs/inspect", headers=api_headers, json={})

    assert response.status_code == 403
    assert response.json()["detail"] == "insufficient_scope"


@pytest.mark.asyncio
async def test_me_wrong_scope(client: AsyncClient):
    jwt_headers = await register_user(client, "wrongscope_user")
    api_headers = await create_agent_api_key(client, jwt_headers, scope_template="mcp_readonly")

    response = await client.get("/api/v1/agent/me", headers=api_headers)

    assert response.status_code == 200
    data = response.json()
    assert "profile:read" in data["scopes"]
    assert "inspection:run" not in data["scopes"]


async def _create_inspection_record(
    api_headers: dict,
    *,
    document_name: str = "测试文档.pdf",
    document_type: str = "tender",
    overall_risk: str = "low",
    summary: str = "测试摘要",
) -> int:
    import app.core.database as db_mod
    from app.models import InspectionRecord

    async with db_mod.async_session() as session:
        from app.services.api_key_service import authenticate_api_key

        api_key_token = api_headers["Authorization"].replace("Bearer ", "")
        api_key = await authenticate_api_key(session, api_key_token)
        record = InspectionRecord(
            user_id=api_key.user_id,
            document_name=document_name,
            document_type=document_type,
            document_type_label="招标文件",
            project_id="default",
            overall_risk=overall_risk,
            summary=summary,
            issues=[],
            regulation_refs=[],
            text_preview="预览文本",
            parsed_content="解析内容",
            quota_consumed=1,
        )
        session.add(record)
        await session.commit()
        await session.refresh(record)
        return record.id


async def _create_api_key_no_inspection_read(
    client: AsyncClient,
    jwt_headers: dict,
) -> dict:
    response = await client.post(
        "/settings/api-keys",
        headers=jwt_headers,
        json={
            "name": "无 inspection:read Key",
            "client_type": "agent",
            "scope_template": "custom",
            "scopes": ["profile:read"],
        },
    )
    assert response.status_code == 201
    full_key = response.json()["full_key"]
    return {"Authorization": f"Bearer {full_key}"}


@pytest.mark.asyncio
async def test_list_records(client: AsyncClient):
    jwt_headers = await register_user(client, "records_user")
    api_headers = await create_agent_api_key(client, jwt_headers)

    await _create_inspection_record(api_headers, document_name="文档A.pdf")
    await _create_inspection_record(api_headers, document_name="文档B.pdf")

    response = await client.get("/api/v1/agent/records", headers=api_headers)

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 2
    assert data[0]["document_name"] in ("文档A.pdf", "文档B.pdf")
    assert "id" in data[0]
    assert "overall_risk" in data[0]
    assert "created_at" in data[0]


@pytest.mark.asyncio
async def test_list_records_no_scope(client: AsyncClient):
    jwt_headers = await register_user(client, "records_noscope_user")
    api_headers = await _create_api_key_no_inspection_read(client, jwt_headers)

    response = await client.get("/api/v1/agent/records", headers=api_headers)

    assert response.status_code == 403
    assert response.json()["detail"] == "insufficient_scope"


@pytest.mark.asyncio
async def test_get_record_detail(client: AsyncClient):
    jwt_headers = await register_user(client, "detail_user")
    api_headers = await create_agent_api_key(client, jwt_headers)

    record_id = await _create_inspection_record(
        api_headers,
        document_name="详情文档.pdf",
        overall_risk="high",
        summary="存在风险",
    )

    response = await client.get(f"/api/v1/agent/records/{record_id}", headers=api_headers)

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == record_id
    assert data["document_name"] == "详情文档.pdf"
    assert data["overall_risk"] == "high"
    assert data["summary"] == "存在风险"
    assert "issues" in data
    assert "regulation_refs" in data


@pytest.mark.asyncio
async def test_get_record_not_found(client: AsyncClient):
    jwt_headers = await register_user(client, "nf_record_user")
    api_headers = await create_agent_api_key(client, jwt_headers)

    response = await client.get("/api/v1/agent/records/999999", headers=api_headers)

    assert response.status_code == 404
    assert response.json()["detail"] == "record_not_found"


@pytest.mark.asyncio
async def test_get_record_not_owner(client: AsyncClient):
    jwt_a = await register_user(client, "rec_owner_a")
    api_a = await create_agent_api_key(client, jwt_a)
    record_id = await _create_inspection_record(api_a)

    jwt_b = await register_user(client, "rec_owner_b")
    api_b = await create_agent_api_key(client, jwt_b)

    response = await client.get(f"/api/v1/agent/records/{record_id}", headers=api_b)

    assert response.status_code == 404
    assert response.json()["detail"] == "record_not_found"


@pytest.mark.asyncio
async def test_knowledge_search(client: AsyncClient):
    jwt_headers = await register_user(client, "knowledge_user")
    api_headers = await create_agent_api_key(client, jwt_headers)

    from unittest.mock import AsyncMock, patch

    fake_result = {
        "snippets": [
            {
                "document_id": 1,
                "title": "招标投标法",
                "owner_type": "system",
                "path_label": "第一章 > 第三条",
                "content": "在中华人民共和国境内进行招投标活动，适用本法。",
            },
        ],
        "sources": [
            {"document_id": 1, "title": "招标投标法", "owner_type": "system"},
        ],
    }

    with patch("app.api.v1.agent.retrieve_regulation_base", new_callable=AsyncMock) as mock_retrieve:
        mock_retrieve.return_value = fake_result

        response = await client.post(
            "/api/v1/agent/knowledge/search",
            headers=api_headers,
            json={"query": "招投标法规", "application_scenario": "bidding", "limit": 5},
        )

    assert response.status_code == 200
    data = response.json()
    assert "snippets" in data
    assert "sources" in data
    assert len(data["snippets"]) == 1
    assert data["snippets"][0]["content"] == "在中华人民共和国境内进行招投标活动，适用本法。"
    mock_retrieve.assert_awaited_once()


@pytest.mark.asyncio
async def test_knowledge_search_no_scope(client: AsyncClient):
    jwt_headers = await register_user(client, "knowledge_noscope_user")
    api_headers = await _create_api_key_no_inspection_read(client, jwt_headers)

    response = await client.post(
        "/api/v1/agent/knowledge/search",
        headers=api_headers,
        json={"query": "招投标法规"},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "insufficient_scope"


@pytest.mark.asyncio
async def test_agent_inspect_success(client: AsyncClient):
    jwt_headers = await register_user(client, "inspect_sync_user")
    api_headers = await create_agent_api_key(client, jwt_headers)

    response = await client.post(
        "/api/v1/agent/inspect",
        headers=api_headers,
        json={
            "document_name": "测试招标文件.pdf",
            "text": "本项目为公开招标采购，投标人须具备相应资质，评标委员会依法组建。",
            "application_scenario": "bidding",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["document_name"] == "测试招标文件.pdf"
    assert data["overall_risk"] in ("low", "medium", "high", "critical")
    assert "summary" in data
    assert "issues" in data
    assert "regulation_refs" in data


@pytest.mark.asyncio
async def test_agent_inspect_no_scope(client: AsyncClient):
    jwt_headers = await register_user(client, "inspect_noscope_user")
    api_headers = await create_agent_api_key(client, jwt_headers, scope_template="mcp_readonly")

    response = await client.post(
        "/api/v1/agent/inspect",
        headers=api_headers,
        json={"document_name": "doc.pdf", "text": "正文内容"},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "insufficient_scope"


@pytest.mark.asyncio
async def test_agent_inspect_no_auth(client: AsyncClient):
    response = await client.post(
        "/api/v1/agent/inspect",
        json={"document_name": "doc.pdf", "text": "正文内容"},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "invalid_api_key"


@pytest.mark.asyncio
async def test_agent_inspect_invalid_scenario(client: AsyncClient):
    jwt_headers = await register_user(client, "inspect_bad_scenario_user")
    api_headers = await create_agent_api_key(client, jwt_headers)

    response = await client.post(
        "/api/v1/agent/inspect",
        headers=api_headers,
        json={
            "document_name": "doc.pdf",
            "text": "足够长的正文内容用于体检",
            "application_scenario": "not_a_real_scenario",
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "非法应用场景"


@pytest.mark.asyncio
async def test_agent_inspect_short_text(client: AsyncClient):
    jwt_headers = await register_user(client, "inspect_short_text_user")
    api_headers = await create_agent_api_key(client, jwt_headers)

    response = await client.post(
        "/api/v1/agent/inspect",
        headers=api_headers,
        json={"document_name": "doc.pdf", "text": "短"},
    )

    assert response.status_code == 400
    assert "过短" in response.json()["detail"]


@pytest.mark.asyncio
async def test_agent_inspect_with_mcp_inspect_template(client: AsyncClient):
    """mcp_inspect 模板的 key 应能调用体检端点 — MCP 可用性核心验证。"""
    jwt_headers = await register_user(client, "mcp_inspect_user")
    api_headers = await create_agent_api_key(client, jwt_headers, scope_template="mcp_inspect")

    response = await client.post(
        "/api/v1/agent/inspect",
        headers=api_headers,
        json={"document_name": "招标文档.pdf", "text": "本项目公开招标，投标人须具备资质并提交投标文件。"},
    )

    assert response.status_code == 200
    assert "overall_risk" in response.json()
