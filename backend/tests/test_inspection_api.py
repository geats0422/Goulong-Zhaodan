from __future__ import annotations

import sys
import types
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import quote
from unittest.mock import MagicMock

import pytest
import pytest_asyncio
from fastapi import HTTPException
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

for mod_name in [
    "pageindex",
    "pydantic_ai",
    "pydantic_ai.agent",
    "pydantic_ai.models",
]:
    if mod_name not in sys.modules:
        sys.modules[mod_name] = types.ModuleType(mod_name)
sys.modules["pydantic_ai"].Agent = MagicMock()

if "markitdown" not in sys.modules or not hasattr(sys.modules.get("markitdown"), "MarkItDown"):
    _fake_md = types.ModuleType("markitdown")
    _fake_md.MarkItDown = MagicMock()
    sys.modules["markitdown"] = _fake_md

from core.database import async_session, engine, init_db  # noqa: E402
from main import app  # noqa: E402
from models.knowledge import TabooWord  # noqa: E402
from routers import inspection as inspection_router  # noqa: E402
from tests.conftest import assert_safe_database_for_cleanup  # noqa: E402


VALID_PASSWORD = "TestPass123"


@pytest_asyncio.fixture
async def client():
    assert_safe_database_for_cleanup()
    await engine.dispose()
    await init_db()
    inspection_router._inspection_records.clear()
    inspection_router._inspection_sessions.clear()
    async with async_session() as session:
        await session.execute(text("UPDATE knowledge_documents SET current_version_id = NULL"))
        for table in [
            "inspection_records",
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
    inspection_router._inspection_records.clear()
    inspection_router._inspection_sessions.clear()
    await engine.dispose()


async def register_and_auth(client: AsyncClient, username: str = "inspection_user") -> tuple[dict[str, str], int]:
    response = await client.post("/auth/register", json={"username": username, "password": VALID_PASSWORD})
    assert response.status_code == 201
    data = response.json()
    return {"Authorization": f"Bearer {data['access_token']}"}, data["id"]


@pytest.mark.asyncio
async def test_parse_returns_session_and_file_metadata(client: AsyncClient):
    headers, _ = await register_and_auth(client, "parse_metadata_user")
    file_content = "这是一个足够长的招标文件内容，用于解析案卷并生成文件摘要。".encode("utf-8")

    response = await client.post(
        "/inspection/parse",
        headers=headers,
        files={"file": ("A区数据中心项目招标文件_v2.txt", file_content, "text/plain")},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["session_id"]
    file_meta = data["file"]
    assert file_meta["name"] == "A区数据中心项目招标文件_v2.txt"
    assert file_meta["size"] == len(file_content)
    assert file_meta["format"] == "txt"
    assert file_meta["document_type"] == "bidding"
    assert file_meta["document_type_label"] == "招投标文件"
    assert file_meta["text_preview"] == "这是一个足够长的招标文件内容，用于解析案卷并生成文件摘要。"
    assert file_meta["parsed_content"] == "这是一个足够长的招标文件内容，用于解析案卷并生成文件摘要。"

    records_response = await client.get("/inspection/records", headers=headers)
    assert records_response.status_code == 200
    record = records_response.json()["items"][0]
    assert record["document_name"] == "A区数据中心项目招标文件_v2.txt"
    assert record["overall_risk"] == "pending"
    assert record["summary"] == "文件已解析，等待审查"


@pytest.mark.asyncio
async def test_parse_detects_contract_document_type(client: AsyncClient):
    headers, _ = await register_and_auth(client, "parse_contract_user")

    response = await client.post(
        "/inspection/parse",
        headers=headers,
        files={
            "file": (
                "工程施工合同.txt",
                "甲方与乙方依据民法典签订本合同，并约定违约责任。".encode("utf-8"),
                "text/plain",
            )
        },
    )

    assert response.status_code == 200
    file_meta = response.json()["file"]
    assert file_meta["document_type"] == "contract"
    assert file_meta["document_type_label"] == "合同"


@pytest.mark.asyncio
async def test_parse_detects_bidding_document_type(client: AsyncClient):
    headers, _ = await register_and_auth(client, "parse_bidding_user")

    response = await client.post(
        "/inspection/parse",
        headers=headers,
        files={
            "file": (
                "数据中心采购招标文件.txt",
                "本项目采用公开招标方式，投标人需按评标办法提交投标文件。".encode("utf-8"),
                "text/plain",
            )
        },
    )

    assert response.status_code == 200
    file_meta = response.json()["file"]
    assert file_meta["document_type"] == "bidding"
    assert file_meta["document_type_label"] == "招投标文件"


def test_detect_document_type_identifies_contract_keywords():
    result = inspection_router._detect_document_type(
        "工程施工合同.txt",
        "甲方与乙方依据民法典签订本协议，并约定违约责任。",
    )

    assert result["document_type"] == "contract"
    assert result["document_type_label"] == "合同"
    assert result["confidence"] == "high"


def test_detect_document_type_identifies_bidding_keywords():
    result = inspection_router._detect_document_type(
        "数据中心采购招标文件.txt",
        "投标人需按评标办法提交投标文件，中标后签约。",
    )

    assert result["document_type"] == "bidding"
    assert result["document_type_label"] == "招投标文件"
    assert result["confidence"] == "high"


def test_detect_document_type_uses_keyword_weight_when_both_match():
    result = inspection_router._detect_document_type(
        "采购招标公告.txt",
        "本文件仅包含合同签署提示。",
    )

    assert result["document_type"] == "bidding"
    assert result["document_type_label"] == "招投标文件"


def test_detect_document_type_tie_breaks_to_bidding():
    result = inspection_router._detect_document_type(
        "工程合同招标.txt",
        "这是普通项目说明文本。",
    )

    assert result["document_type"] == "bidding"
    assert result["document_type_label"] == "招投标文件"
    assert result["confidence"] == "high"


def test_detect_document_type_defaults_to_unknown_when_no_keywords():
    result = inspection_router._detect_document_type("项目资料.txt", "这是普通项目说明文本，没有明确类型线索。")

    assert result["document_type"] == "unknown"
    assert result["document_type_label"] == "未知类型"
    assert result["confidence"] == "low"


@pytest.mark.parametrize("keyword,text_snippet", [
    ("付款", "本合同约定付款方式为分期付款"),
    ("履约", "履约保证金应在合同签订后缴纳"),
    ("违约金", "违约金按日千分之五计算"),
    ("不可抗力", "因不可抗力导致合同无法履行"),
    ("签订", "甲方与乙方签订本协议"),
])
def test_detect_contract_keywords(keyword, text_snippet):
    result = inspection_router._detect_document_type("文档.txt", text_snippet)
    assert result["document_type"] == "contract"


def test_create_inspection_session_stores_user_scoped_file_parse_data():
    inspection_router._inspection_sessions.clear()
    text = "这是一个足够长的招标文件内容，用于验证解析会话存储。"

    session = inspection_router._create_inspection_session(
        user_id=101,
        filename="招标文件.txt",
        file_size=len(text.encode("utf-8")),
        file_format="txt",
        document_type="bidding",
        document_type_label="招投标文件",
        text=text,
    )

    assert session["id"]
    assert session == inspection_router._inspection_sessions[session["id"]]
    assert session["user_id"] == 101
    assert session["filename"] == "招标文件.txt"
    assert session["file_size"] == len(text.encode("utf-8"))
    assert session["file_format"] == "txt"
    assert session["document_type"] == "bidding"
    assert session["document_type_label"] == "招投标文件"
    assert session["text"] == text
    assert session["text_preview"] == text[:500]
    assert isinstance(session["created_at"], datetime)


def test_get_session_for_user_rejects_missing_or_cross_user_session():
    inspection_router._inspection_sessions.clear()
    session = inspection_router._create_inspection_session(
        user_id=201,
        filename="合同.txt",
        file_size=128,
        file_format="txt",
        document_type="contract",
        document_type_label="合同",
        text="甲方与乙方签署合同，并约定违约责任。",
    )

    assert inspection_router._get_session_for_user(session["id"], 201) == session
    with pytest.raises(HTTPException) as cross_user_error:
        inspection_router._get_session_for_user(session["id"], 202)
    assert cross_user_error.value.status_code == 404
    with pytest.raises(HTTPException) as missing_error:
        inspection_router._get_session_for_user("missing-session", 201)
    assert missing_error.value.status_code == 404


def test_get_session_for_user_rejects_expired_session():
    inspection_router._inspection_sessions.clear()
    now = datetime(2026, 1, 1, 12, 0, 0)
    session = inspection_router._create_inspection_session(
        user_id=203,
        filename="过期合同.txt",
        file_size=128,
        file_format="txt",
        document_type="contract",
        document_type_label="合同",
        text="甲方与乙方签署合同，并约定违约责任。",
        created_at=now - inspection_router.INSPECTION_SESSION_TTL,
    )

    with pytest.raises(HTTPException) as expired_error:
        inspection_router._get_session_for_user(session["id"], 203, now=now)

    assert expired_error.value.status_code == 404
    assert session["id"] not in inspection_router._inspection_sessions


def test_cleanup_expired_inspection_sessions_removes_only_expired_sessions():
    inspection_router._inspection_sessions.clear()
    now = datetime(2026, 1, 1, 12, 0, 0)
    fresh_session = inspection_router._create_inspection_session(
        user_id=301,
        filename="新文件.txt",
        file_size=100,
        file_format="txt",
        document_type="bidding",
        document_type_label="招投标文件",
        text="新文件内容足够长。",
        created_at=now - inspection_router.INSPECTION_SESSION_TTL + timedelta(seconds=1),
    )
    expired_session = inspection_router._create_inspection_session(
        user_id=301,
        filename="旧文件.txt",
        file_size=100,
        file_format="txt",
        document_type="bidding",
        document_type_label="招投标文件",
        text="旧文件内容足够长。",
        created_at=now - inspection_router.INSPECTION_SESSION_TTL,
    )

    removed_count = inspection_router._cleanup_expired_inspection_sessions(now=now)

    assert removed_count == 1
    assert fresh_session["id"] in inspection_router._inspection_sessions
    assert expired_session["id"] not in inspection_router._inspection_sessions


def test_create_inspection_session_cleans_expired_sessions():
    inspection_router._inspection_sessions.clear()
    now = datetime(2026, 1, 1, 12, 0, 0)
    expired_session = inspection_router._create_inspection_session(
        user_id=401,
        filename="旧文件.txt",
        file_size=100,
        file_format="txt",
        document_type="bidding",
        document_type_label="招投标文件",
        text="旧文件内容足够长。",
        created_at=now - inspection_router.INSPECTION_SESSION_TTL,
    )

    new_session = inspection_router._create_inspection_session(
        user_id=401,
        filename="新文件.txt",
        file_size=100,
        file_format="txt",
        document_type="bidding",
        document_type_label="招投标文件",
        text="新文件内容足够长。",
        created_at=now,
    )

    assert expired_session["id"] not in inspection_router._inspection_sessions
    assert new_session["id"] in inspection_router._inspection_sessions


def test_create_inspection_session_enforces_per_user_limit():
    inspection_router._inspection_sessions.clear()
    now = datetime(2026, 1, 1, 12, 0, 0)
    sessions = [
        inspection_router._create_inspection_session(
            user_id=501,
            filename=f"文件{i}.txt",
            file_size=100,
            file_format="txt",
            document_type="bidding",
            document_type_label="招投标文件",
            text="文件内容足够长。",
            created_at=now + timedelta(seconds=i),
        )
        for i in range(inspection_router.MAX_INSPECTION_SESSIONS_PER_USER + 1)
    ]

    assert sessions[0]["id"] not in inspection_router._inspection_sessions
    assert sessions[-1]["id"] in inspection_router._inspection_sessions
    assert len(inspection_router._inspection_sessions) == inspection_router.MAX_INSPECTION_SESSIONS_PER_USER


def test_create_inspection_session_enforces_global_limit():
    inspection_router._inspection_sessions.clear()
    now = datetime(2026, 1, 1, 12, 0, 0)
    sessions = [
        inspection_router._create_inspection_session(
            user_id=600 + i,
            filename=f"文件{i}.txt",
            file_size=100,
            file_format="txt",
            document_type="bidding",
            document_type_label="招投标文件",
            text="文件内容足够长。",
            created_at=now + timedelta(seconds=i),
        )
        for i in range(inspection_router.MAX_INSPECTION_SESSIONS + 1)
    ]

    assert sessions[0]["id"] not in inspection_router._inspection_sessions
    assert sessions[-1]["id"] in inspection_router._inspection_sessions
    assert len(inspection_router._inspection_sessions) == inspection_router.MAX_INSPECTION_SESSIONS


def test_extract_inspection_text_rejects_invalid_utf8_text():
    with pytest.raises(HTTPException) as exc_info:
        inspection_router._extract_inspection_text("坏编码.txt", b"\xff\xfe\xfd")

    assert exc_info.value.status_code == 400


def test_clean_inspection_markdown_removes_data_image_noise():
    raw_text = """**教育经历**![module_title_background.png](data:image/png;base64,abc)图片占位符\n\n图\n\n片\n\n占\n\n位\n\n符\n\n**专业**![技能.png](data:image/png;base64,def)能力"""

    cleaned = inspection_router._clean_inspection_markdown(raw_text)

    assert "data:image" not in cleaned
    assert "module_title_background" not in cleaned
    assert "图片占位符" not in cleaned.replace("\n", "")
    assert "**教育经历**" in cleaned
    assert "**专业**能力" in cleaned


def test_sanitize_inspection_result_refs_keeps_only_configured_sources_and_taboo_words():
    result = SimpleNamespace(
        regulation_refs=["系统法规库", "个人信息保护法", "违禁词:禁止词A"],
        issues=[
            {"title": "允许来源", "regulation_ref": "系统法规库"},
            {"title": "未配置法规", "regulation_ref": "网络安全法", "citation": "个人信息保护法"},
        ],
    )

    inspection_router._sanitize_inspection_result_refs(result, {"系统法规库", "违禁词:禁止词A"})

    assert result.regulation_refs == ["系统法规库", "违禁词:禁止词A"]
    assert result.issues[0]["regulation_ref"] == "系统法规库"
    assert "regulation_ref" not in result.issues[1]
    assert "citation" not in result.issues[1]


@pytest.mark.asyncio
async def test_parse_rejects_unsupported_format(client: AsyncClient):
    headers, _ = await register_and_auth(client, "parse_unsupported_user")

    response = await client.post(
        "/inspection/parse",
        headers=headers,
        files={"file": ("文档.xlsx", b"fake-data", "application/octet-stream")},
    )

    assert response.status_code == 400
    assert "不支持的文件类型" in response.json()["detail"]


@pytest.mark.asyncio
async def test_parse_rejects_short_text(client: AsyncClient):
    headers, _ = await register_and_auth(client, "parse_short_user")

    response = await client.post(
        "/inspection/parse",
        headers=headers,
        files={"file": ("短文件.txt", b"hi", "text/plain")},
    )

    assert response.status_code == 400
    assert "过短" in response.json()["detail"]


@pytest.mark.asyncio
async def test_parse_rejects_oversized_file(client: AsyncClient):
    headers, _ = await register_and_auth(client, "parse_oversize_user")
    big_content = b"x" * (inspection_router.MAX_INSPECTION_FILE_SIZE + 1)

    response = await client.post(
        "/inspection/parse",
        headers=headers,
        files={"file": ("大文件.txt", big_content, "text/plain")},
    )

    assert response.status_code == 413


@pytest.mark.asyncio
async def test_upload_passes_application_scenario_regulation_base_and_merged_taboo_words(client: AsyncClient, monkeypatch: pytest.MonkeyPatch):
    headers, user_id = await register_and_auth(client)
    async with async_session() as session:
        session.add(TabooWord(user_id=user_id, word="禁止词A"))
        session.add(TabooWord(user_id=user_id, word="重复词"))
        await session.commit()

    captured = {}

    async def fake_retrieve_regulation_base(db, user_id: int, application_scenario: str, limit: int):
        captured["retrieval"] = {
            "user_id": user_id,
            "application_scenario": application_scenario,
            "limit": limit,
        }
        return {"snippets": [{"content": "法规依据"}], "sources": [{"title": "系统法规"}]}

    async def fake_run_inspection(document_text: str, deps):
        captured["deps"] = deps
        return SimpleNamespace(overall_risk="low", summary="ok", issues=[], regulation_refs=["系统法规"])

    monkeypatch.setattr("routers.inspection.retrieve_regulation_base", fake_retrieve_regulation_base)
    monkeypatch.setattr("routers.inspection.run_inspection", fake_run_inspection)

    response = await client.post(
        "/inspection/upload",
        headers=headers,
        files={"file": ("demo.txt", "这是一个足够长的合同审查文档内容".encode("utf-8"), "text/plain")},
        data={"application_scenario": "contract", "taboo_words": "临时词,重复词"},
    )

    assert response.status_code == 200
    assert captured["retrieval"] == {"user_id": user_id, "application_scenario": "contract", "limit": 8}
    deps = captured["deps"]
    assert deps.application_scenario == "contract"
    assert deps.regulation_base == {"snippets": [{"content": "法规依据"}], "sources": [{"title": "系统法规"}]}
    assert deps.taboo_words == ["禁止词A", "重复词", "临时词"]


@pytest.mark.asyncio
async def test_upload_rejects_invalid_application_scenario(client: AsyncClient):
    headers, _ = await register_and_auth(client, "invalid_scenario_user")

    response = await client.post(
        "/inspection/upload",
        headers=headers,
        files={"file": ("demo.txt", "这是一个足够长的待审查文档内容".encode("utf-8"), "text/plain")},
        data={"application_scenario": "invalid"},
    )

    assert response.status_code == 400


@pytest.mark.asyncio
async def test_session_inspect_uses_document_type_from_parse_session(client: AsyncClient, monkeypatch: pytest.MonkeyPatch):
    headers, user_id = await register_and_auth(client, "session_inspect_user")
    file_content = "甲方与乙方签订工程施工合同，约定违约责任条款。".encode("utf-8")

    parse_response = await client.post(
        "/inspection/parse",
        headers=headers,
        files={"file": ("工程施工合同.txt", file_content, "text/plain")},
    )
    assert parse_response.status_code == 200
    session_id = parse_response.json()["session_id"]

    captured = {}

    async def fake_retrieve_regulation_base(db, user_id: int, application_scenario: str, limit: int):
        captured["retrieval"] = {
            "user_id": user_id,
            "application_scenario": application_scenario,
            "limit": limit,
        }
        return {"snippets": [{"content": "法规依据"}], "sources": [{"title": "系统法规"}]}

    async def fake_run_inspection(document_text: str, deps):
        captured["deps"] = deps
        return SimpleNamespace(
            overall_risk="medium",
            summary="发现合同风险",
            issues=[{"title": "违约条款不明确", "severity": "medium"}],
            regulation_refs=["民法典"],
        )

    monkeypatch.setattr("routers.inspection.retrieve_regulation_base", fake_retrieve_regulation_base)
    monkeypatch.setattr("routers.inspection.run_inspection", fake_run_inspection)

    inspect_response = await client.post(
        f"/inspection/sessions/{session_id}/inspect",
        headers=headers,
        json={"project_id": "proj-001"},
    )

    assert inspect_response.status_code == 200
    data = inspect_response.json()
    assert data["document_type"] == "contract"
    assert data["document_type_label"] == "合同"
    assert data["overall_risk"] == "medium"
    assert captured["retrieval"]["application_scenario"] == "contract"


@pytest.mark.asyncio
async def test_session_inspect_unknown_type_falls_back_to_bidding(client: AsyncClient, monkeypatch: pytest.MonkeyPatch):
    headers, user_id = await register_and_auth(client, "unknown_fallback_user")
    file_content = "这是普通项目说明文本，没有明确类型线索。".encode("utf-8")

    parse_response = await client.post(
        "/inspection/parse",
        headers=headers,
        files={"file": ("项目资料.txt", file_content, "text/plain")},
    )
    assert parse_response.status_code == 200
    assert parse_response.json()["file"]["document_type"] == "unknown"

    session_id = parse_response.json()["session_id"]
    captured = {}

    async def fake_retrieve_regulation_base(db, user_id: int, application_scenario: str, limit: int):
        captured["application_scenario"] = application_scenario
        return {"snippets": [{"content": "法规依据"}], "sources": [{"title": "系统法规"}]}

    async def fake_run_inspection(document_text: str, deps):
        return SimpleNamespace(
            overall_risk="low",
            summary="无风险",
            issues=[],
            regulation_refs=["系统法规"],
        )

    monkeypatch.setattr("routers.inspection.retrieve_regulation_base", fake_retrieve_regulation_base)
    monkeypatch.setattr("routers.inspection.run_inspection", fake_run_inspection)

    inspect_response = await client.post(
        f"/inspection/sessions/{session_id}/inspect",
        headers=headers,
        json={"project_id": "proj-unknown"},
    )

    assert inspect_response.status_code == 200
    assert captured["application_scenario"] == "bidding"


@pytest.mark.asyncio
async def test_contract_inspect_only_references_contract_sources(client: AsyncClient, monkeypatch: pytest.MonkeyPatch):
    headers, _ = await register_and_auth(client, "contract_ref_filter_user")
    file_content = "甲方与乙方签订工程施工合同，约定付款方式与违约责任。".encode("utf-8")

    parse_response = await client.post(
        "/inspection/parse",
        headers=headers,
        files={"file": ("施工合同.txt", file_content, "text/plain")},
    )
    assert parse_response.status_code == 200
    session_id = parse_response.json()["session_id"]

    contract_sources = [
        {"title": "《中华人民共和国民法典》第三编合同"},
        {"title": "最高人民法院关于适用《中华人民共和国民法典》合同通则若干问题的解释"},
    ]

    async def fake_retrieve_regulation_base(db, user_id: int, application_scenario: str, limit: int):
        assert application_scenario == "contract"
        return {"snippets": [{"content": "合同法规"}], "sources": contract_sources}

    async def fake_run_inspection(document_text: str, deps):
        return SimpleNamespace(
            overall_risk="medium",
            summary="合同风险",
            issues=[],
            regulation_refs=["《中华人民共和国民法典》第三编合同", "招标投标法"],
        )

    monkeypatch.setattr("routers.inspection.retrieve_regulation_base", fake_retrieve_regulation_base)
    monkeypatch.setattr("routers.inspection.run_inspection", fake_run_inspection)

    inspect_response = await client.post(
        f"/inspection/sessions/{session_id}/inspect",
        headers=headers,
        json={"project_id": "proj-contract"},
    )

    assert inspect_response.status_code == 200
    data = inspect_response.json()
    assert "招标投标法" not in data["regulation_refs"]
    assert "《中华人民共和国民法典》第三编合同" in data["regulation_refs"]


@pytest.mark.asyncio
async def test_session_inspect_explicit_scenario_overrides_detected(client: AsyncClient, monkeypatch: pytest.MonkeyPatch):
    headers, _ = await register_and_auth(client, "scenario_override_user")
    file_content = "甲方与乙方签订工程施工合同，约定付款方式与违约责任。".encode("utf-8")

    parse_response = await client.post(
        "/inspection/parse",
        headers=headers,
        files={"file": ("施工合同.txt", file_content, "text/plain")},
    )
    assert parse_response.status_code == 200
    assert parse_response.json()["file"]["document_type"] == "contract"
    session_id = parse_response.json()["session_id"]

    captured = {}

    async def fake_retrieve_regulation_base(db, user_id: int, application_scenario: str, limit: int):
        captured["application_scenario"] = application_scenario
        return {"snippets": [{"content": "法规依据"}], "sources": [{"title": "系统法规"}]}

    async def fake_run_inspection(document_text: str, deps):
        return SimpleNamespace(
            overall_risk="low",
            summary="无风险",
            issues=[],
            regulation_refs=["系统法规"],
        )

    monkeypatch.setattr("routers.inspection.retrieve_regulation_base", fake_retrieve_regulation_base)
    monkeypatch.setattr("routers.inspection.run_inspection", fake_run_inspection)

    inspect_response = await client.post(
        f"/inspection/sessions/{session_id}/inspect",
        headers=headers,
        json={"project_id": "proj-override", "application_scenario": "bidding"},
    )

    assert inspect_response.status_code == 200
    assert captured["application_scenario"] == "bidding"


@pytest.mark.asyncio
async def test_session_inspect_persists_record_for_paginated_desk_list(client: AsyncClient, monkeypatch: pytest.MonkeyPatch):
    headers, _ = await register_and_auth(client, "session_records_user")
    monkeypatch.setattr("routers.inspection.convert_to_markdown", lambda path: "甲方与乙方签署合同，约定服务范围与违约责任。")
    parse_response = await client.post(
        "/inspection/parse",
        headers=headers,
        files={"file": ("2026标准外包合同.docx", "甲方与乙方签署合同，约定服务范围与违约责任。".encode("utf-8"), "text/plain")},
    )
    assert parse_response.status_code == 200

    async def fake_retrieve_regulation_base(db, user_id: int, application_scenario: str, limit: int):
        return {"snippets": [{"content": "合同审查依据"}], "sources": [{"title": "民法典合同编"}]}

    async def fake_run_inspection(document_text: str, deps):
        return SimpleNamespace(
            overall_risk="low",
            summary="纯净通过",
            issues=[],
            regulation_refs=["民法典合同编"],
        )

    monkeypatch.setattr("routers.inspection.retrieve_regulation_base", fake_retrieve_regulation_base)
    monkeypatch.setattr("routers.inspection.run_inspection", fake_run_inspection)

    inspect_response = await client.post(
        f"/inspection/sessions/{parse_response.json()['session_id']}/inspect",
        headers=headers,
        json={"project_id": "default"},
    )
    assert inspect_response.status_code == 200
    record_id = inspect_response.json()["id"]

    records_response = await client.get("/inspection/records?page=1&page_size=10", headers=headers)

    assert records_response.status_code == 200
    data = records_response.json()
    assert data["pagination"] == {"page": 1, "page_size": 10, "total": 1, "total_pages": 1}
    assert data["items"][0]["id"] == record_id
    assert data["items"][0]["document_name"] == "2026标准外包合同.docx"
    assert data["items"][0]["document_type_label"] == "合同"
    assert data["items"][0]["overall_risk"] == "low"
    assert data["items"][0]["issue_count"] == 0
    assert data["items"][0]["created_at"]

    search_response = await client.get("/inspection/records?keyword=外包合同", headers=headers)
    assert search_response.status_code == 200
    assert search_response.json()["pagination"]["total"] == 1

    empty_search_response = await client.get("/inspection/records?keyword=不存在", headers=headers)
    assert empty_search_response.status_code == 200
    assert empty_search_response.json()["pagination"]["total"] == 0

    delete_response = await client.delete(f"/inspection/records/{record_id}", headers=headers)
    assert delete_response.status_code == 204

    deleted_records_response = await client.get("/inspection/records?page=1&page_size=10", headers=headers)
    assert deleted_records_response.status_code == 200
    assert deleted_records_response.json()["pagination"]["total"] == 0

    deleted_detail_response = await client.get(f"/inspection/records/{record_id}", headers=headers)
    assert deleted_detail_response.status_code == 404


@pytest.mark.asyncio
async def test_pending_record_can_be_inspected_from_history(client: AsyncClient, monkeypatch: pytest.MonkeyPatch):
    headers, _ = await register_and_auth(client, "history_inspect_user")
    parsed_text = "甲方与乙方签署合同，约定服务范围与违约责任。"
    monkeypatch.setattr("routers.inspection.convert_to_markdown", lambda path: parsed_text)
    parse_response = await client.post(
        "/inspection/parse",
        headers=headers,
        files={"file": ("待审查合同.docx", parsed_text.encode("utf-8"), "text/plain")},
    )
    assert parse_response.status_code == 200

    records_response = await client.get("/inspection/records", headers=headers)
    record_id = records_response.json()["items"][0]["id"]

    detail_response = await client.get(f"/inspection/records/{record_id}", headers=headers)
    assert detail_response.status_code == 200
    assert detail_response.json()["parsed_content"] == parsed_text

    async def fake_retrieve_regulation_base(db, user_id: int, application_scenario: str, limit: int):
        return {"snippets": [{"content": "合同审查依据"}], "sources": [{"title": "民法典合同编"}]}

    async def fake_run_inspection(document_text: str, deps):
        assert document_text == parsed_text
        return SimpleNamespace(
            overall_risk="medium",
            summary="发现 1 处疑点",
            issues=[{"title": "条款不完整", "severity": "medium"}],
            regulation_refs=["民法典合同编"],
        )

    monkeypatch.setattr("routers.inspection.retrieve_regulation_base", fake_retrieve_regulation_base)
    monkeypatch.setattr("routers.inspection.run_inspection", fake_run_inspection)

    inspect_response = await client.post(
        f"/inspection/records/{record_id}/inspect",
        headers=headers,
        json={"project_id": "default"},
    )

    assert inspect_response.status_code == 200
    assert inspect_response.json()["id"] == record_id
    assert inspect_response.json()["overall_risk"] == "medium"

    updated_detail_response = await client.get(f"/inspection/records/{record_id}", headers=headers)
    assert updated_detail_response.json()["overall_risk"] == "medium"


@pytest.mark.asyncio
async def test_record_report_pdf_uses_contract_name_filename(client: AsyncClient, monkeypatch: pytest.MonkeyPatch):
    headers, _ = await register_and_auth(client, "session_pdf_user")
    monkeypatch.setattr("routers.inspection.convert_to_markdown", lambda path: "甲方与乙方签署合同，约定服务范围与违约责任。")
    parse_response = await client.post(
        "/inspection/parse",
        headers=headers,
        files={"file": ("2026标准外包合同.docx", "甲方与乙方签署合同，约定服务范围与违约责任。".encode("utf-8"), "text/plain")},
    )
    assert parse_response.status_code == 200

    async def fake_retrieve_regulation_base(db, user_id: int, application_scenario: str, limit: int):
        return {"snippets": [{"content": "合同审查依据"}], "sources": [{"title": "民法典合同编"}]}

    async def fake_run_inspection(document_text: str, deps):
        return SimpleNamespace(
            overall_risk="medium",
            summary="存在 1 处风险",
            issues=[{"title": "条款不完整", "severity": "medium", "suggestion": "补充验收标准"}],
            regulation_refs=["民法典合同编"],
        )

    monkeypatch.setattr("routers.inspection.retrieve_regulation_base", fake_retrieve_regulation_base)
    monkeypatch.setattr("routers.inspection.run_inspection", fake_run_inspection)

    inspect_response = await client.post(
        f"/inspection/sessions/{parse_response.json()['session_id']}/inspect",
        headers=headers,
        json={"project_id": "default"},
    )
    record_id = inspect_response.json()["id"]

    pdf_response = await client.get(f"/inspection/records/{record_id}/report.pdf", headers=headers)

    assert pdf_response.status_code == 200
    assert pdf_response.headers["content-type"] == "application/pdf"
    assert quote("2026标准外包合同审查报告.pdf") in pdf_response.headers["content-disposition"]
    assert pdf_response.content.startswith(b"%PDF")


@pytest.mark.asyncio
async def test_session_inspect_rejects_other_users_session(client: AsyncClient):
    headers_a, _ = await register_and_auth(client, "user_a_session")
    headers_b, _ = await register_and_auth(client, "user_b_session")
    file_content = "这是一个足够长的招标文件内容，用于测试跨用户隔离。".encode("utf-8")

    parse_response = await client.post(
        "/inspection/parse",
        headers=headers_a,
        files={"file": ("招标文件.txt", file_content, "text/plain")},
    )
    assert parse_response.status_code == 200
    session_id = parse_response.json()["session_id"]

    inspect_response = await client.post(
        f"/inspection/sessions/{session_id}/inspect",
        headers=headers_b,
        json={"project_id": "default"},
    )

    assert inspect_response.status_code == 404
