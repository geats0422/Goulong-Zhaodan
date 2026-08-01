from __future__ import annotations

import sys
import types
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import quote
from unittest.mock import MagicMock

import pytest
import pytest_asyncio
from fastapi import HTTPException
from httpx import ASGITransport, AsyncClient

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

from app.core.database import async_session  # noqa: E402
from main import app  # noqa: E402
from app.models.knowledge import (  # noqa: E402
    DocumentVersion,
    EngineeringSubcategory,
    InspectionRecord,
    InspectionType,
    KnowledgeDocument,
    KnowledgeDocumentSetting,
    TabooWord,
)
from app.api.v1 import inspection as inspection_router  # noqa: E402
from app.services import inspection_runner  # noqa: E402
from app.services.inspection_history import (  # noqa: E402
    classification_display,
    rule_package_keys_display,
)
from tests.conftest import assert_safe_database_for_cleanup  # noqa: E402


VALID_PASSWORD = "TestPass123"


@pytest_asyncio.fixture
async def client(monkeypatch):
    assert_safe_database_for_cleanup()
    from app.core.rate_limit import register_limiter
    from app.services import email_service
    register_limiter.reset()
    inspection_router._inspection_sessions.clear()

    async def _always_true(*args, **kwargs):
        return True

    monkeypatch.setattr(email_service, "verify_code", _always_true)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    inspection_router._inspection_sessions.clear()


async def register_and_auth(client: AsyncClient, username: str = "inspection_user") -> tuple[dict[str, str], str]:
    response = await client.post("/auth/register", json={
        "email": f"{username}@test.com",
        "nickname": username,
        "password": VALID_PASSWORD,
        "email_code": "123456",
    })
    assert response.status_code == 201
    data = response.json()
    return {"Authorization": f"Bearer {data['access_token']}"}, data["id"]


async def register_and_create_parse_session(
    client: AsyncClient,
    username: str,
    *,
    filename: str,
    text: str,
    document_type: str = "bidding",
    document_type_label: str = "招投标文件",
) -> tuple[dict[str, str], str]:
    """注册用户并直接构造一个已解析会话，绕过异步 /parse。

    /parse 改为异步文档处理后不再在请求线程内同步解析正文，会话级审查测试
    需要预注入解析文本来聚焦 ``inspect_session`` 端点的场景路由逻辑。
    """
    headers, user_id = await register_and_auth(client, username)
    file_format = Path(filename).suffix.lstrip(".").lower()
    parse_session = inspection_router._create_inspection_session(
        user_id=uuid.UUID(user_id),
        filename=filename,
        file_size=len(text.encode("utf-8")),
        file_format=file_format,
        document_type=document_type,
        document_type_label=document_type_label,
        text=text,
    )
    return headers, parse_session["id"]


@pytest.mark.asyncio
async def test_parse_returns_job_id_and_pending_record(client: AsyncClient):
    headers, _ = await register_and_auth(client, "parse_metadata_user")
    file_content = "这是一个足够长的招标文件内容，用于解析案卷并生成文件摘要。".encode("utf-8")

    response = await client.post(
        "/inspection/parse",
        headers=headers,
        files={"file": ("A区数据中心项目招标文件_v2.txt", file_content, "text/plain")},
    )

    assert response.status_code == 202
    data = response.json()
    assert data["job_id"]
    assert data["session_id"]
    file_meta = data["file"]
    assert file_meta["name"] == "A区数据中心项目招标文件_v2.txt"
    assert file_meta["size"] == len(file_content)
    assert file_meta["format"] == "txt"
    # 异步入口不再同步检测文档类型/解析正文，交由后台 worker 填充。
    assert file_meta["document_type"] == "contract"
    assert file_meta["document_type_label"] == "合同"
    assert data["status"] == "processing"
    assert file_meta["text_preview"] == ""
    assert file_meta["parsed_content"] == ""

    records_response = await client.get("/inspection/records", headers=headers)
    assert records_response.status_code == 200
    record = records_response.json()["items"][0]
    assert record["document_name"] == "A区数据中心项目招标文件_v2.txt"
    assert record["overall_risk"] == "pending"
    assert record["summary"] == "文件已解析，等待审查"


@pytest.mark.asyncio
async def test_parse_defers_document_type_detection_to_worker(client: AsyncClient):
    """异步 /parse 不再同步解析正文，文档类型统一由后台 worker 解析后判定。"""
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

    assert response.status_code == 202
    file_meta = response.json()["file"]
    assert file_meta["document_type"] == "contract"


@pytest.mark.asyncio
async def test_parse_accepts_short_text_deferring_quality_check_to_worker(client: AsyncClient):
    """内容长度/质量校验已下沉到后台 worker 统一解析管线，/parse 仅落盘建 job。"""
    headers, _ = await register_and_auth(client, "parse_short_user")

    response = await client.post(
        "/inspection/parse",
        headers=headers,
        files={"file": ("短文件.txt", b"hi", "text/plain")},
    )

    assert response.status_code == 202
    assert response.json()["job_id"]


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

    assert result["document_type"] != "bidding"
    assert result["document_type_label"] == "未知类型"
    assert result["confidence"] == "low"


def test_detect_document_type_uses_keyword_weight_when_both_match():
    result = inspection_router._detect_document_type(
        "采购招标公告.txt",
        "本文件仅包含合同签署提示。",
    )

    assert result["document_type"] == "contract"
    assert result["document_type_label"] == "合同"


def test_detect_document_type_tie_breaks_to_bidding():
    result = inspection_router._detect_document_type(
        "工程合同招标.txt",
        "这是普通项目说明文本。",
    )

    assert result["document_type"] == "contract"
    assert result["document_type_label"] == "合同"
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

    inspection_runner.sanitize_inspection_result_refs(result, {"系统法规库", "违禁词:禁止词A"})

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

    async def fake_retrieve_regulation_base(
        db, user_id: int, application_scenario: str, limit: int,
        engineering_type_key: str, contract_type_key: str,
    ):
        captured["retrieval"] = {
            "user_id": user_id,
            "application_scenario": application_scenario,
            "limit": limit,
            "engineering_type_key": engineering_type_key,
            "contract_type_key": contract_type_key,
        }
        return {"snippets": [{"content": "法规依据"}], "sources": [{"title": "系统法规"}]}

    async def fake_run_inspection(document_text: str, deps):
        captured["deps"] = deps
        return SimpleNamespace(overall_risk="low", summary="ok", issues=[], regulation_refs=["系统法规"])

    monkeypatch.setattr("app.services.inspection_runner.retrieve_regulation_base", fake_retrieve_regulation_base)
    monkeypatch.setattr("app.services.inspection_runner.run_inspection", fake_run_inspection)

    response = await client.post(
        "/inspection/upload",
        headers=headers,
        files={"file": ("demo.txt", "这是一个足够长的合同审查文档内容".encode("utf-8"), "text/plain")},
        data={"application_scenario": "contract", "taboo_words": "临时词,重复词"},
    )

    assert response.status_code == 200
    assert str(captured["retrieval"]["user_id"]) == user_id
    assert captured["retrieval"]["application_scenario"] == "contract"
    assert captured["retrieval"]["engineering_type_key"] == "general-engineering"
    assert captured["retrieval"]["contract_type_key"] == "other"
    assert captured["retrieval"]["limit"] == 8
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
    headers, session_id = await register_and_create_parse_session(
        client,
        "session_inspect_user",
        filename="工程施工合同.txt",
        text="甲方与乙方签订工程施工合同，约定违约责任条款。",
        document_type="contract",
        document_type_label="合同",
    )

    captured = {}

    async def fake_retrieve_regulation_base(db, user_id: int, application_scenario: str, limit: int, engineering_type_key: str = "general-engineering", contract_type_key: str = "other"):
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

    monkeypatch.setattr("app.services.inspection_runner.retrieve_regulation_base", fake_retrieve_regulation_base)
    monkeypatch.setattr("app.services.inspection_runner.run_inspection", fake_run_inspection)

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
async def test_session_inspect_unknown_type_falls_back_to_contract(client: AsyncClient, monkeypatch: pytest.MonkeyPatch):
    headers, session_id = await register_and_create_parse_session(
        client,
        "unknown_fallback_user",
        filename="项目资料.txt",
        text="这是普通项目说明文本，没有明确类型线索。",
        document_type="unknown",
        document_type_label="未知类型",
    )

    captured = {}

    async def fake_retrieve_regulation_base(db, user_id: int, application_scenario: str, limit: int, engineering_type_key: str = "general-engineering", contract_type_key: str = "other"):
        captured["application_scenario"] = application_scenario
        return {"snippets": [{"content": "法规依据"}], "sources": [{"title": "系统法规"}]}

    async def fake_run_inspection(document_text: str, deps):
        return SimpleNamespace(
            overall_risk="low",
            summary="无风险",
            issues=[],
            regulation_refs=["系统法规"],
        )

    monkeypatch.setattr("app.services.inspection_runner.retrieve_regulation_base", fake_retrieve_regulation_base)
    monkeypatch.setattr("app.services.inspection_runner.run_inspection", fake_run_inspection)

    inspect_response = await client.post(
        f"/inspection/sessions/{session_id}/inspect",
        headers=headers,
        json={"project_id": "proj-unknown"},
    )

    assert inspect_response.status_code == 200
    assert captured["application_scenario"] == "contract"


@pytest.mark.asyncio
async def test_contract_inspect_only_references_contract_sources(client: AsyncClient, monkeypatch: pytest.MonkeyPatch):
    headers, session_id = await register_and_create_parse_session(
        client,
        "contract_ref_filter_user",
        filename="施工合同.txt",
        text="甲方与乙方签订工程施工合同，约定付款方式与违约责任。",
        document_type="contract",
        document_type_label="合同",
    )

    contract_sources = [
        {"title": "《中华人民共和国民法典》第三编合同"},
        {"title": "最高人民法院关于适用《中华人民共和国民法典》合同通则若干问题的解释"},
    ]

    async def fake_retrieve_regulation_base(db, user_id: int, application_scenario: str, limit: int, engineering_type_key: str = "general-engineering", contract_type_key: str = "other"):
        assert application_scenario == "contract"
        return {"snippets": [{"content": "合同法规"}], "sources": contract_sources}

    async def fake_run_inspection(document_text: str, deps):
        return SimpleNamespace(
            overall_risk="medium",
            summary="合同风险",
            issues=[],
            regulation_refs=["《中华人民共和国民法典》第三编合同", "招标投标法"],
        )

    monkeypatch.setattr("app.services.inspection_runner.retrieve_regulation_base", fake_retrieve_regulation_base)
    monkeypatch.setattr("app.services.inspection_runner.run_inspection", fake_run_inspection)

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
async def test_session_inspect_rejects_deprecated_bidding_scenario(client: AsyncClient, monkeypatch: pytest.MonkeyPatch):
    headers, session_id = await register_and_create_parse_session(
        client,
        "scenario_override_user",
        filename="施工合同.txt",
        text="甲方与乙方签订工程施工合同，约定付款方式与违约责任。",
        document_type="contract",
        document_type_label="合同",
    )

    captured = {}

    async def fake_retrieve_regulation_base(db, user_id: int, application_scenario: str, limit: int, engineering_type_key: str = "general-engineering", contract_type_key: str = "other"):
        captured["application_scenario"] = application_scenario
        return {"snippets": [{"content": "法规依据"}], "sources": [{"title": "系统法规"}]}

    async def fake_run_inspection(document_text: str, deps):
        return SimpleNamespace(
            overall_risk="low",
            summary="无风险",
            issues=[],
            regulation_refs=["系统法规"],
        )

    monkeypatch.setattr("app.services.inspection_runner.retrieve_regulation_base", fake_retrieve_regulation_base)
    monkeypatch.setattr("app.services.inspection_runner.run_inspection", fake_run_inspection)

    inspect_response = await client.post(
        f"/inspection/sessions/{session_id}/inspect",
        headers=headers,
        json={"project_id": "proj-override", "application_scenario": "bidding"},
    )

    assert inspect_response.status_code == 400
    assert inspect_response.json()["detail"]["code"] == "deprecated_application_scenario"
    assert "application_scenario" not in captured


@pytest.mark.asyncio
async def test_session_inspect_persists_record_for_paginated_desk_list(client: AsyncClient, monkeypatch: pytest.MonkeyPatch):
    headers, session_id = await register_and_create_parse_session(
        client,
        "session_records_user",
        filename="2026标准外包合同.docx",
        text="甲方与乙方签署合同，约定服务范围与违约责任。",
        document_type="contract",
        document_type_label="合同",
    )

    async def fake_retrieve_regulation_base(db, user_id: int, application_scenario: str, limit: int, engineering_type_key: str = "general-engineering", contract_type_key: str = "other"):
        return {"snippets": [{"content": "合同审查依据"}], "sources": [{"title": "民法典合同编"}]}

    async def fake_run_inspection(document_text: str, deps):
        return SimpleNamespace(
            overall_risk="low",
            summary="纯净通过",
            issues=[],
            regulation_refs=["民法典合同编"],
        )

    monkeypatch.setattr("app.services.inspection_runner.retrieve_regulation_base", fake_retrieve_regulation_base)
    monkeypatch.setattr("app.services.inspection_runner.run_inspection", fake_run_inspection)

    inspect_response = await client.post(
        f"/inspection/sessions/{session_id}/inspect",
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
    headers, user_id = await register_and_auth(client, "history_inspect_user")
    parsed_text = "甲方与乙方签署合同，约定服务范围与违约责任。"

    # 异步管线下 record 的 parsed_content 由后台 worker 填充；这里直接模拟
    # worker 已完成解析后的落库状态，聚焦 record 级审查入口。
    from app.core.data_encryption import encrypt_text

    async with async_session() as session:
        record = InspectionRecord(
            user_id=uuid.UUID(user_id),
            document_name="待审查合同.docx",
            document_type="contract",
            document_type_label="合同",
            project_id="default",
            overall_risk="pending",
            summary="文件已解析，等待审查",
            issues=[],
            regulation_refs=[],
            text_preview=parsed_text[:500],
            parsed_content=encrypt_text(parsed_text),
            quota_consumed=0,
            detected_engineering_type="general-engineering",
            final_engineering_type="municipal-road",
            detected_contract_type="other",
            final_contract_type="professional-subcontract",
        )
        session.add(record)
        await session.commit()
        await session.refresh(record)
        record_id = record.id

    detail_response = await client.get(f"/inspection/records/{record_id}", headers=headers)
    assert detail_response.status_code == 200
    assert detail_response.json()["parsed_content"] == parsed_text

    async def fake_retrieve_regulation_base(db, user_id: int, application_scenario: str, limit: int, engineering_type_key: str = "general-engineering", contract_type_key: str = "other"):
        assert engineering_type_key == "municipal-road"
        assert contract_type_key == "professional-subcontract"
        return {"snippets": [{"content": "合同审查依据"}], "sources": [{"title": "民法典合同编"}]}

    async def fake_run_inspection(document_text: str, deps):
        assert document_text == parsed_text
        return SimpleNamespace(
            overall_risk="medium",
            summary="发现 1 处疑点",
            issues=[{"title": "条款不完整", "severity": "medium"}],
            regulation_refs=["民法典合同编"],
        )

    monkeypatch.setattr("app.services.inspection_runner.retrieve_regulation_base", fake_retrieve_regulation_base)
    monkeypatch.setattr("app.services.inspection_runner.run_inspection", fake_run_inspection)

    inspect_response = await client.post(
        f"/inspection/records/{record_id}/inspect",
        headers=headers,
        json={"project_id": "default"},
    )

    assert inspect_response.status_code == 200
    assert inspect_response.json()["id"] == record_id
    assert inspect_response.json()["overall_risk"] == "medium"

    duplicate_response = await client.post(
        f"/inspection/records/{record_id}/inspect",
        headers=headers,
        json={"project_id": "default"},
    )
    assert duplicate_response.status_code == 409
    assert duplicate_response.json()["detail"]["code"] == "inspection_already_completed"

    updated_detail_response = await client.get(f"/inspection/records/{record_id}", headers=headers)
    assert updated_detail_response.json()["overall_risk"] == "medium"
    assert updated_detail_response.json()["final_engineering_type"] == "municipal-road"
    assert updated_detail_response.json()["final_contract_type"] == "professional-subcontract"


@pytest.mark.asyncio
async def test_record_reinspect_keeps_original_types_when_only_documents_provided(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch,
):
    """重审仅传知识库文档时，必须沿用原记录类别（final 优先于 detected）。

    回归任务8 HIGH：inspect_record 此前把未传类别交给 validate 默认成
    general-engineering/other，覆盖原记录类别，导致检索用错误类别。
    """
    from sqlalchemy import select  # 局部导入，避免改文件顶部导入区

    headers, user_id = await register_and_auth(client, "reinspect_types_user")
    parsed_text = "甲方与乙方签署合同，约定服务范围与违约责任。"

    from app.core.data_encryption import encrypt_text

    # validate 会校验类别存在；inspection_types 不在 conftest 清理清单内，幂等补齐系统类型，
    # 并记录本次新建的 id，测试结束在 finally 删除，避免污染其他测试（如 manual_resubmit 直接 add 同名类型）。
    # 含默认值 general-engineering/other：确保 bug 表现为"检索用错误类别"而非提前 422。
    created_type_ids: list[int] = []
    async with async_session() as session:
        for key, name, dimension in [
            ("municipal-road", "市政道路", "engineering"),
            ("professional-subcontract", "专业工程分包", "contract"),
            ("general-engineering", "通用工程", "engineering"),
            ("other", "其他类", "contract"),
        ]:
            exists = await session.scalar(
                select(InspectionType).where(
                    InspectionType.key == key,
                    InspectionType.dimension == dimension,
                )
            )
            if exists is None:
                type_obj = InspectionType(
                    key=key, name=name, dimension=dimension,
                    owner_type="system", enabled=True,
                )
                session.add(type_obj)
                await session.flush()
                created_type_ids.append(type_obj.id)
        await session.commit()

    try:
        async with async_session() as session:
            subcategory = EngineeringSubcategory(category_key="contract", name="重审知识库分类")
            session.add(subcategory)
            await session.flush()
            document = KnowledgeDocument(
                title="重审可用规则", subcategory_id=subcategory.id, owner_type="system",
                application_scenario="contract", is_active=True,
            )
            session.add(document)
            await session.flush()
            version = DocumentVersion(
                document_id=document.id, version_number=1, display_name="规则.md",
                original_file_path="/tmp/rules.md", status="completed", file_size_bytes=1,
                file_type=".md",
            )
            session.add(version)
            await session.flush()
            document.current_version_id = version.id
            await session.commit()
            await session.refresh(document)
            document_id = document.id

        async with async_session() as session:
            record = InspectionRecord(
                user_id=uuid.UUID(user_id),
                document_name="待重审合同.docx",
                document_type="contract",
                document_type_label="合同",
                project_id="default",
                overall_risk="pending",
                summary="文件已解析，等待审查",
                issues=[],
                regulation_refs=[],
                text_preview=parsed_text[:500],
                parsed_content=encrypt_text(parsed_text),
                quota_consumed=0,
                detected_engineering_type="general-engineering",
                final_engineering_type="municipal-road",
                detected_contract_type="other",
                final_contract_type="professional-subcontract",
            )
            session.add(record)
            await session.commit()
            await session.refresh(record)
            record_id = record.id

        captured: dict[str, object] = {}

        async def fake_retrieve_regulation_base(db, *args, **kwargs):
            captured["engineering_type_key"] = kwargs.get("engineering_type_key")
            captured["contract_type_key"] = kwargs.get("contract_type_key")
            return {"snippets": [], "sources": []}

        async def fake_run_inspection(document_text: str, deps):
            return SimpleNamespace(
                overall_risk="low", summary="ok", issues=[], regulation_refs=[],
            )

        monkeypatch.setattr("app.services.inspection_runner.retrieve_regulation_base", fake_retrieve_regulation_base)
        monkeypatch.setattr("app.services.inspection_runner.run_inspection", fake_run_inspection)

        inspect_response = await client.post(
            f"/inspection/records/{record_id}/inspect",
            headers=headers,
            json={"knowledge_document_ids": [document_id]},
        )

        assert inspect_response.status_code == 200, inspect_response.text
        # 关键断言：检索必须用原记录类别，而非默认 general-engineering/other
        assert captured["engineering_type_key"] == "municipal-road"
        assert captured["contract_type_key"] == "professional-subcontract"
    finally:
        if created_type_ids:
            async with async_session() as session:
                await session.execute(
                    InspectionType.__table__.delete().where(
                        InspectionType.id.in_(created_type_ids)
                    )
                )
                await session.commit()


@pytest.mark.asyncio
async def test_record_report_pdf_uses_contract_name_filename(client: AsyncClient, monkeypatch: pytest.MonkeyPatch):
    headers, session_id = await register_and_create_parse_session(
        client,
        "session_pdf_user",
        filename="2026标准外包合同.docx",
        text="甲方与乙方签署合同，约定服务范围与违约责任。",
        document_type="contract",
        document_type_label="合同",
    )

    async def fake_retrieve_regulation_base(db, user_id: int, application_scenario: str, limit: int, engineering_type_key: str = "general-engineering", contract_type_key: str = "other"):
        return {"snippets": [{"content": "合同审查依据"}], "sources": [{"title": "民法典合同编"}]}

    async def fake_run_inspection(document_text: str, deps):
        return SimpleNamespace(
            overall_risk="medium",
            summary="存在 1 处风险",
            issues=[{"title": "条款不完整", "severity": "medium", "suggestion": "补充验收标准"}],
            regulation_refs=["民法典合同编"],
        )

    monkeypatch.setattr("app.services.inspection_runner.retrieve_regulation_base", fake_retrieve_regulation_base)
    monkeypatch.setattr("app.services.inspection_runner.run_inspection", fake_run_inspection)

    inspect_response = await client.post(
        f"/inspection/sessions/{session_id}/inspect",
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
    assert parse_response.status_code == 202
    session_id = parse_response.json()["session_id"]

    inspect_response = await client.post(
        f"/inspection/sessions/{session_id}/inspect",
        headers=headers_b,
        json={"project_id": "default"},
    )

    assert inspect_response.status_code == 404


@pytest.mark.asyncio
async def test_step2_submission_validates_independent_types_and_document_access(client: AsyncClient):
    headers, user_id = await register_and_auth(client, "step2_validation_user")
    other_headers, other_user_id = await register_and_auth(client, "step2_other_user")
    del other_headers

    async with async_session() as session:
        engineering = InspectionType(
            key="private-engineering", name="私有工程", dimension="engineering",
            owner_type="user", owner_user_id=uuid.UUID(user_id), enabled=True,
        )
        contract = InspectionType(
            key="private-contract", name="私有合同", dimension="contract",
            owner_type="user", owner_user_id=uuid.UUID(user_id), enabled=True,
        )
        other_contract = InspectionType(
            key="other-contract", name="他人合同", dimension="contract",
            owner_type="user", owner_user_id=uuid.UUID(other_user_id), enabled=True,
        )
        session.add_all([engineering, contract, other_contract])
        await session.commit()
        await session.refresh(engineering)
        await session.refresh(contract)

    async with async_session() as session:
        subcategory = EngineeringSubcategory(category_key="contract", name="Step2 测试分类")
        session.add(subcategory)
        await session.flush()
        document = KnowledgeDocument(
            title="可用合同规则", subcategory_id=subcategory.id, owner_type="user",
            owner_user_id=uuid.UUID(user_id), application_scenario="contract", is_active=True,
        )
        session.add(document)
        await session.flush()
        version = DocumentVersion(
            document_id=document.id, version_number=1, display_name="规则.md",
            original_file_path="/tmp/rules.md", status="completed", file_size_bytes=1,
            file_type=".md",
        )
        session.add(version)
        await session.flush()
        document.current_version_id = version.id
        await session.commit()
        await session.refresh(document)
        document_id = document.id

    parse_session = inspection_router._create_inspection_session(
        user_id=uuid.UUID(user_id), filename="合同.txt", file_size=10, file_format="txt",
        document_type="contract", document_type_label="合同", text="甲乙双方签订合同并约定违约责任。",
    )

    async def fake_execute(**kwargs):
        return {
            "id": 1, "overall_risk": "low", "summary": "ok", "issues": [],
            "regulation_refs": [], "document_name": kwargs["document_name"],
            "document_type": "contract", "document_type_label": "合同",
        }

    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr("app.api.v1.inspection.execute_inspection", fake_execute)
    try:
        response = await client.post(
            f"/inspection/sessions/{parse_session['id']}/inspect", headers=headers,
            json={
                "engineering_type_key": "private-engineering",
                "contract_type_key": "private-contract",
                "knowledge_document_ids": [document_id],
            },
        )
        assert response.status_code == 200

        async with async_session() as db_session:
            db_session.add(KnowledgeDocumentSetting(
                user_id=uuid.UUID(user_id), document_id=document_id, enabled=False,
            ))
            await db_session.commit()
        disabled_document = await client.post(
            f"/inspection/sessions/{parse_session['id']}/inspect", headers=headers,
            json={
                "engineering_type_key": "private-engineering",
                "contract_type_key": "private-contract",
                "knowledge_document_ids": [document_id],
            },
        )
        assert disabled_document.status_code == 422
        assert disabled_document.json()["detail"]["code"] == "invalid_knowledge_document"

        cross_dimension = await client.post(
            f"/inspection/sessions/{parse_session['id']}/inspect", headers=headers,
            json={"engineering_type_key": "private-contract", "contract_type_key": "private-contract"},
        )
        assert cross_dimension.status_code == 422
        assert cross_dimension.json()["detail"]["code"] == "invalid_engineering_type"

        cross_user = await client.post(
            f"/inspection/sessions/{parse_session['id']}/inspect", headers=headers,
            json={"engineering_type_key": "private-engineering", "contract_type_key": "other-contract"},
        )
        assert cross_user.status_code == 422
        assert cross_user.json()["detail"]["code"] == "invalid_contract_type"
    finally:
        monkeypatch.undo()
        async with async_session() as session:
            await session.execute(
                InspectionType.__table__.delete().where(
                    InspectionType.owner_user_id.in_([uuid.UUID(user_id), uuid.UUID(other_user_id)])
                )
            )
            await session.commit()


@pytest.mark.asyncio
async def test_inspection_record_persists_full_rule_package_keys_snapshot(client: AsyncClient):
    """历史报告必须从持久化快照恢复完整规则包列表，不从单值推导。

    多包快照需落库到 inspection_records.rule_package_keys_snapshot，新会话读取时
    仍能得到完整列表，而不是退化成 rule_package_key 单值。
    """
    headers, user_id = await register_and_auth(client, "snapshot_user")
    del headers
    async with async_session() as session:
        record = InspectionRecord(
            user_id=uuid.UUID(user_id),
            document_name="合同.txt",
            document_type="contract",
            document_type_label="合同",
            status="completed",
            overall_risk="low",
            summary="ok",
            rule_package_key="pkg-a:v1",
            rule_package_keys_snapshot=["pkg-a:v1", "pkg-b:v1"],
        )
        session.add(record)
        await session.commit()
        await session.refresh(record)
        saved_id = record.id

    async with async_session() as session:
        restored = await session.get(InspectionRecord, saved_id)

    assert restored is not None
    assert rule_package_keys_display(restored) == ["pkg-a:v1", "pkg-b:v1"]


@pytest.mark.asyncio
async def test_history_record_endpoint_returns_full_rule_package_keys_snapshot(
    client: AsyncClient,
):
    """GET /inspection/records/{id} 必须返回持久化的完整规则包快照。"""
    headers, user_id = await register_and_auth(client, "history_snapshot_user")
    async with async_session() as session:
        record = InspectionRecord(
            user_id=uuid.UUID(user_id),
            document_name="合同.txt",
            document_type="contract",
            document_type_label="合同",
            status="completed",
            overall_risk="low",
            summary="ok",
            rule_package_key="pkg-a:v1",
            rule_package_keys_snapshot=["pkg-a:v1", "pkg-b:v1"],
        )
        session.add(record)
        await session.commit()
        await session.refresh(record)
        record_id = record.id

    response = await client.get(f"/inspection/records/{record_id}", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["rule_package_keys"] == ["pkg-a:v1", "pkg-b:v1"]


@pytest.mark.asyncio
async def test_execute_inspection_manual_selection_writes_manual_source_and_keeps_detected(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch,
):
    """重审时手动选择类别：source=manual、快照取选择值，且保留 detected 与证据。"""
    headers, user_id = await register_and_auth(client, "manual_resubmit_user")
    del headers
    async with async_session() as session:
        session.add_all([
            InspectionType(
                key="municipal-road", name="市政道路", dimension="engineering",
                owner_type="system", enabled=True,
            ),
            InspectionType(
                key="labor-subcontract", name="劳务分包", dimension="contract",
                owner_type="system", enabled=True,
            ),
        ])
        record = InspectionRecord(
            user_id=uuid.UUID(user_id),
            document_name="合同.txt",
            document_type="contract",
            document_type_label="合同",
            status="processing",
            overall_risk="pending",
            summary="等待审查",
            detected_engineering_type="general-engineering",
            detected_contract_type="other",
            classification_confidence="medium",
            classification_source="model",
            classification_evidence=["初筛关键词"],
        )
        session.add(record)
        await session.commit()
        await session.refresh(record)
        record_id = record.id

    async def fake_retrieve_regulation_base(db, *args, **kwargs):
        return {
            "snippets": [],
            "sources": [],
            "rule_package_keys": ["pkg-x:v1"],
            "rule_package_key": "pkg-x:v1",
        }

    async def fake_run_inspection(document_text: str, deps):
        return SimpleNamespace(
            overall_risk="low", summary="ok", issues=[], regulation_refs=[],
        )

    monkeypatch.setattr(
        "app.services.inspection_runner.retrieve_regulation_base",
        fake_retrieve_regulation_base,
    )
    monkeypatch.setattr(
        "app.services.inspection_runner.run_inspection", fake_run_inspection,
    )

    async with async_session() as session:
        report = await inspection_runner.execute_inspection(
            db=session,
            user_id=uuid.UUID(user_id),
            document_name="合同.txt",
            text="甲乙双方签订工程施工合同并约定违约责任条款。",
            project_id="default",
            application_scenario="contract",
            record_id=record_id,
            engineering_type_key="municipal-road",
            contract_type_key="labor-subcontract",
        )

    assert report.final_engineering_type == "municipal-road"
    assert report.final_contract_type == "labor-subcontract"
    assert report.classification_confidence == "medium"
    assert report.rule_package_keys == ["pkg-x:v1"]

    async with async_session() as session:
        restored = await session.get(InspectionRecord, record_id)

    assert restored is not None
    assert restored.classification_source == "manual"
    assert restored.engineering_type_snapshot == "市政道路"
    assert restored.contract_type_snapshot == "劳务分包"
    # 手动选择不得抹掉历史 detected 与证据
    assert restored.detected_engineering_type == "general-engineering"
    assert restored.detected_contract_type == "other"
    assert restored.classification_evidence == ["初筛关键词"]
    assert restored.rule_package_keys_snapshot == ["pkg-x:v1"]


@pytest.mark.asyncio
async def test_records_list_returns_classification_snapshot_fields(client: AsyncClient):
    """GET /inspection/records 列表项必须返回分类快照字段，供历史列表展示工程类别。

    前端历史列表只能拿到列表接口数据（详情需额外请求），因此列表项需要携带
    engineering_type_snapshot / contract_type_snapshot / classification_confidence
    及组合展示字段 classification_display，避免只显示粗粒度「合同」。
    """
    headers, user_id = await register_and_auth(client, "list_snapshot_user")
    async with async_session() as session:
        record = InspectionRecord(
            user_id=uuid.UUID(user_id),
            document_name="合同.txt",
            document_type="contract",
            document_type_label="合同",
            status="completed",
            overall_risk="low",
            summary="ok",
            engineering_type_snapshot="市政道路",
            contract_type_snapshot="劳务分包",
            classification_confidence="medium",
            classification_source="model",
        )
        session.add(record)
        await session.commit()
        await session.refresh(record)
        record_id = record.id

    response = await client.get("/inspection/records", headers=headers)
    assert response.status_code == 200
    item = next(it for it in response.json()["items"] if it["id"] == record_id)
    assert item["engineering_type_snapshot"] == "市政道路"
    assert item["contract_type_snapshot"] == "劳务分包"
    assert item["classification_confidence"] == "medium"
    # 组合展示字段复用 inspection_history.classification_display 逻辑
    assert item["classification_display"] == classification_display(record)
    assert item["classification_display"] == "市政道路 / 劳务分包"


@pytest.mark.asyncio
async def test_records_list_classification_display_falls_back_for_legacy_records(
    client: AsyncClient,
):
    """无快照的 legacy 记录在列表中应退化到通用工程合同文案，且快照字段为 None。"""
    headers, user_id = await register_and_auth(client, "list_legacy_user")
    async with async_session() as session:
        record = InspectionRecord(
            user_id=uuid.UUID(user_id),
            document_name="旧合同.txt",
            document_type="contract",
            document_type_label="合同",
            status="completed",
            overall_risk="low",
            summary="ok",
            classification_source="legacy",
        )
        session.add(record)
        await session.commit()
        await session.refresh(record)
        record_id = record.id

    response = await client.get("/inspection/records", headers=headers)
    assert response.status_code == 200
    item = next(it for it in response.json()["items"] if it["id"] == record_id)
    assert item["engineering_type_snapshot"] is None
    assert item["contract_type_snapshot"] is None
    assert item["classification_confidence"] is None
    assert item["classification_display"] == "历史记录 / 通用工程合同"
