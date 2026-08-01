"""任务19：合同初审跨后端集成测试。

覆盖完整主流程与边界场景，使用真实 PostgreSQL 测试库 + ASGITransport，
不依赖 mock DB，验证 API → 服务 → 持久化 → 历史读取的全链路契约。

覆盖场景（对应 docs/plans/2026-08-01-...-plan.md 任务19）：
1. 完整主流程：上传合同 → 解析分类 → 审查 → 报告/历史查看
2. Step 2 三字段提交（engineering_type_key + contract_type_key + knowledge_document_ids）
3. 低置信度分类仍允许继续审查
4. 无用户知识库时回退系统默认规则包
5. production 额度不足返回统一 402 契约且不泄露内部细节
6. local 环境不拦截额度
7. 旧 bidding 记录历史兼容读取，但不可按旧场景重审
8. 归档资料完整删除（文档/版本/索引节点）
9. 审查引擎异常返回脱敏 502，不泄露模型或堆栈
"""

from __future__ import annotations

import sys
import types
import uuid
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
import pytest_asyncio
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

from app.core import config as app_config  # noqa: E402
from app.core.database import async_session  # noqa: E402
from main import app  # noqa: E402
from app.models.knowledge import (  # noqa: E402
    DocumentVersion,
    EngineeringSubcategory,
    IndexNode,
    InspectionRecord,
    InspectionType,
    KnowledgeDocument,
)
from app.api.v1 import inspection as inspection_router  # noqa: E402
from app.services import inspection_runner  # noqa: E402
from tests.conftest import assert_safe_database_for_cleanup  # noqa: E402

VALID_PASSWORD = "TestPass123"


@pytest_asyncio.fixture
async def client(monkeypatch):
    """复用 test_inspection_api.py 的 ASGITransport + 真实 DB 模式。"""
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


async def _register(client: AsyncClient, username: str) -> tuple[dict[str, str], str]:
    response = await client.post("/auth/register", json={
        "email": f"{username}@test.com",
        "nickname": username,
        "password": VALID_PASSWORD,
        "email_code": "123456",
    })
    assert response.status_code == 201, response.text
    data = response.json()
    return {"Authorization": f"Bearer {data['access_token']}"}, data["id"]


def _patch_runner(monkeypatch, *, retrieval=None, run=None, classify=None):
    """统一 mock inspection_runner 的外部依赖（检索/Agent/分类）。"""
    if retrieval is not None:
        monkeypatch.setattr(inspection_runner, "retrieve_regulation_base", retrieval)
    if run is not None:
        monkeypatch.setattr(inspection_runner, "run_inspection", run)
    if classify is not None:
        monkeypatch.setattr(inspection_runner, "classify_inspection_document", classify)


def _default_retrieval(captured: dict | None = None):
    async def _fake(db, *args, **kwargs):
        if captured is not None:
            captured["kwargs"] = kwargs
        return {
            "snippets": [{"content": "合同审查依据"}],
            "sources": [{"title": "民法典合同编"}],
            "rule_package_key": "general-engineering-contract-rules:v1",
            "rule_package_keys": ["general-engineering-contract-rules:v1"],
        }

    return _fake


def _default_run(captured: dict | None = None):
    async def _fake(document_text: str, deps):
        if captured is not None:
            captured["deps"] = deps
        return SimpleNamespace(
            overall_risk="medium",
            summary="发现合同风险",
            issues=[{"title": "违约条款不明确", "severity": "medium"}],
            regulation_refs=["民法典合同编"],
            total_quota_consumed=120,
        )

    return _fake


# ---------------------------------------------------------------------------
# 1. 完整主流程：上传合同 → 审查 → 报告 → 历史列表/详情
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_full_flow_upload_contract_to_report_and_history(client: AsyncClient, monkeypatch):
    """上传合同 → 审查 → 报告，随后历史列表与详情均可读到分类快照与最终风险。"""
    headers, _ = await _register(client, "flow_upload_user")
    _patch_runner(monkeypatch, retrieval=_default_retrieval(), run=_default_run())

    upload_response = await client.post(
        "/inspection/upload",
        headers=headers,
        files={"file": ("工程施工合同.txt", "甲方与乙方签订工程施工合同，约定违约责任。".encode("utf-8"), "text/plain")},
        data={"application_scenario": "contract"},
    )

    assert upload_response.status_code == 200, upload_response.text
    report = upload_response.json()
    assert report["overall_risk"] == "medium"
    assert report["document_type"] == "contract"
    assert report["classification"]["confidence"]
    record_id = report["id"]

    list_response = await client.get("/inspection/records", headers=headers)
    assert list_response.status_code == 200
    item = next(it for it in list_response.json()["items"] if it["id"] == record_id)
    assert item["overall_risk"] == "medium"
    assert item["classification_display"]

    detail_response = await client.get(f"/inspection/records/{record_id}", headers=headers)
    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert detail["overall_risk"] == "medium"
    assert detail["classification"]
    assert detail["rule_package_keys"] == ["general-engineering-contract-rules:v1"]
    assert detail["knowledge_sources_snapshot"] == [{"title": "民法典合同编"}]


# ---------------------------------------------------------------------------
# 2. Step 2 三字段提交（engineering_type_key + contract_type_key + knowledge_document_ids）
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_step2_three_field_submission_drives_retrieval(client: AsyncClient, monkeypatch):
    """Step 2 三字段提交后，服务端用用户提交的类别与文档 ID 驱动知识库检索。"""
    headers, user_id = await _register(client, "flow_step2_user")

    created_type_ids: list[int] = []
    async with async_session() as session:
        for key, name, dimension in [
            ("municipal-road", "市政道路", "engineering"),
            ("professional-subcontract", "专业工程分包", "contract"),
        ]:
            from sqlalchemy import select
            exists = await session.scalar(
                select(InspectionType).where(
                    InspectionType.key == key, InspectionType.dimension == dimension,
                )
            )
            if exists is None:
                t = InspectionType(key=key, name=name, dimension=dimension, owner_type="system", enabled=True)
                session.add(t)
                await session.flush()
                created_type_ids.append(t.id)
        await session.commit()

    document_id = None
    async with async_session() as session:
        sub = EngineeringSubcategory(category_key="contract", name="Step2流程分类")
        session.add(sub)
        await session.flush()
        doc = KnowledgeDocument(
            title="用户合同规则", subcategory_id=sub.id, owner_type="user",
            owner_user_id=uuid.UUID(user_id), application_scenario="contract", is_active=True,
        )
        session.add(doc)
        await session.flush()
        version = DocumentVersion(
            document_id=doc.id, version_number=1, display_name="rule.md",
            original_file_path="/tmp/rule.md", status="completed", file_size_bytes=1, file_type=".md",
        )
        session.add(version)
        await session.flush()
        doc.current_version_id = version.id
        await session.commit()
        await session.refresh(doc)
        document_id = doc.id

    captured: dict = {}
    _patch_runner(monkeypatch, retrieval=_default_retrieval(captured), run=_default_run())

    parse_session = inspection_router._create_inspection_session(
        user_id=uuid.UUID(user_id), filename="市政道路合同.txt", file_size=20, file_format="txt",
        document_type="contract", document_type_label="合同",
        text="甲方与乙方签订市政道路工程专业分包合同，约定违约责任。",
    )

    try:
        response = await client.post(
            f"/inspection/sessions/{parse_session['id']}/inspect", headers=headers,
            json={
                "engineering_type_key": "municipal-road",
                "contract_type_key": "professional-subcontract",
                "knowledge_document_ids": [document_id],
            },
        )
        assert response.status_code == 200, response.text
        # 服务端必须用用户提交的类别与文档 ID 驱动检索，而非默认值
        assert captured["kwargs"]["engineering_type_key"] == "municipal-road"
        assert captured["kwargs"]["contract_type_key"] == "professional-subcontract"
        assert captured["kwargs"]["document_ids"] == [document_id]
        report = response.json()
        assert report["final_engineering_type"] == "municipal-road"
        assert report["final_contract_type"] == "professional-subcontract"
    finally:
        if created_type_ids:
            async with async_session() as session:
                await session.execute(
                    InspectionType.__table__.delete().where(InspectionType.id.in_(created_type_ids))
                )
                await session.commit()


# ---------------------------------------------------------------------------
# 3. 低置信度分类仍允许继续审查
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_low_confidence_classification_does_not_block_inspection(client: AsyncClient, monkeypatch):
    """低置信度只是提醒，不阻塞审查：报告应正常生成且携带 confidence=low。"""
    from app.services.contract_classifier import ContractClassification

    headers, _ = await _register(client, "low_confidence_user")

    async def _low_confidence_classify(*, document_name, text, rule_screening=None):
        return ContractClassification(
            engineering_type_key="general-engineering",
            contract_type_key="other",
            confidence="low",
            evidence=["未命中明确关键词"],
            source="fallback",
            requires_confirmation=True,
        )

    _patch_runner(
        monkeypatch,
        retrieval=_default_retrieval(),
        run=_default_run(),
        classify=_low_confidence_classify,
    )

    response = await client.post(
        "/inspection/upload",
        headers=headers,
        files={"file": ("模糊文档.txt", "这是一份内容含糊的项目说明材料。".encode("utf-8"), "text/plain")},
        data={"application_scenario": "contract"},
    )

    assert response.status_code == 200, response.text
    report = response.json()
    assert report["classification"]["confidence"] == "low"
    assert report["classification"]["requires_confirmation"] is True
    # 低置信度不阻塞：报告仍生成最终风险与摘要
    assert report["overall_risk"] == "medium"
    assert report["summary"]


# ---------------------------------------------------------------------------
# 4. 无用户知识库时回退系统默认规则包
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_no_user_knowledge_falls_back_to_system_default(client: AsyncClient, monkeypatch):
    """用户无启用文档时，检索回退系统默认规则包（selection_mode=system_fallback）。"""
    headers, _ = await _register(client, "fallback_user")

    # 预置系统默认合同规则包文档
    async with async_session() as session:
        sub = EngineeringSubcategory(category_key="contract", name="系统默认分类")
        session.add(sub)
        await session.flush()
        doc = KnowledgeDocument(
            title="民法典合同编", subcategory_id=sub.id, owner_type="system",
            application_scenario="contract", is_active=True,
            rule_package_key="general-engineering-contract-rules:v1",
        )
        session.add(doc)
        await session.flush()
        version = DocumentVersion(
            document_id=doc.id, version_number=1, display_name="civil-code.md",
            original_file_path="/tmp/civil-code.md", status="completed",
            file_size_bytes=10, file_type=".md",
        )
        session.add(version)
        await session.flush()
        doc.current_version_id = version.id
        session.add(IndexNode(
            version_id=version.id, node_type="section",
            path_label="民法典 > 合同编", content="当事人应当按照约定全面履行自己的义务。",
            position=1,
        ))
        await session.commit()

    captured: dict = {}
    _patch_runner(monkeypatch, run=_default_run(captured))
    # 不 mock retrieve：使用真实检索，验证回退逻辑

    response = await client.post(
        "/inspection/upload",
        headers=headers,
        files={"file": ("通用合同.txt", "甲方与乙方签订通用工程施工合同。".encode("utf-8"), "text/plain")},
        data={"application_scenario": "contract"},
    )

    assert response.status_code == 200, response.text
    regulation_base = captured["deps"].regulation_base
    assert regulation_base["selection_mode"] == "system_fallback"
    assert regulation_base["rule_package_key"] == "general-engineering-contract-rules:v1"
    assert regulation_base["fallback_notice"]  # 含回退提示文案


# ---------------------------------------------------------------------------
# 5. production 额度不足返回统一 402 契约且不泄露内部细节
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_production_quota_exhausted_returns_unified_402(client: AsyncClient, monkeypatch):
    """production 环境额度耗尽：返回 402 + 统一契约，且不泄露模型/token/路径等内部信息。"""
    from goulong_auth.models import Membership
    from sqlalchemy import update

    headers, user_id = await _register(client, "quota_exhausted_user")
    # 注册默认 token_quota=0（回退 200000）/token_used=0；耗尽 used 使剩余为 0
    async with async_session() as session:
        await session.execute(
            update(Membership)
            .where(Membership.user_id == uuid.UUID(user_id), Membership.product == "zhaodan")
            .values(token_used=200_000)
        )
        await session.commit()

    monkeypatch.setattr(app_config.settings, "environment", "production")
    _patch_runner(monkeypatch, retrieval=_default_retrieval(), run=_default_run())

    response = await client.post(
        "/inspection/upload",
        headers=headers,
        files={"file": ("合同.txt", "甲方与乙方签订合同。".encode("utf-8"), "text/plain")},
        data={"application_scenario": "contract"},
    )

    assert response.status_code == 402, response.text
    detail = response.json()["detail"]
    assert detail["code"] == "insufficient_quota"
    assert detail["action"]["path"] == "/settings?tab=billing"
    # 失败响应不得泄露模型、token 数量、内部路径或堆栈
    blob = repr(detail).lower()
    for forbidden in ("deepseek", "model", "token_used", "token_quota", "/app/", "traceback", "exception"):
        assert forbidden not in blob, f"额度不足响应不应暴露内部细节：{forbidden}"


# ---------------------------------------------------------------------------
# 6. local 环境不拦截额度
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_local_environment_does_not_block_inspection(client: AsyncClient, monkeypatch):
    """local 环境：即使没有可用额度记录也不拦截，审查正常完成。"""
    from goulong_auth.models import Membership
    from sqlalchemy import delete

    headers, user_id = await _register(client, "local_env_user")
    # 删除 membership 模拟"无额度记录"，验证 local 仍放行
    async with async_session() as session:
        await session.execute(
            delete(Membership).where(Membership.user_id == uuid.UUID(user_id))
        )
        await session.commit()

    monkeypatch.setattr(app_config.settings, "environment", "local")
    _patch_runner(monkeypatch, retrieval=_default_retrieval(), run=_default_run())

    response = await client.post(
        "/inspection/upload",
        headers=headers,
        files={"file": ("合同.txt", "甲方与乙方签订合同。".encode("utf-8"), "text/plain")},
        data={"application_scenario": "contract"},
    )

    assert response.status_code == 200, response.text
    assert response.json()["overall_risk"] == "medium"


# ---------------------------------------------------------------------------
# 7. 旧 bidding 记录历史兼容读取，但不可按旧场景重审
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_legacy_bidding_record_readable_but_not_reinspectable(client: AsyncClient, monkeypatch):
    """旧招投标报告：历史详情/列表可读且标记归档，重审返回 deprecated_application_scenario。"""
    from app.services.inspection_history import is_archived_legacy_record

    headers, user_id = await _register(client, "legacy_bidding_user")
    async with async_session() as session:
        record = InspectionRecord(
            user_id=uuid.UUID(user_id),
            document_name="旧招标报告.docx",
            document_type="bidding",
            document_type_label="招投标文件",
            status="completed",
            overall_risk="low",
            summary="历史招投标报告",
            issues=[],
            regulation_refs=[],
            classification_source="archived_legacy",
        )
        session.add(record)
        await session.commit()
        await session.refresh(record)
        record_id = record.id

    # 历史详情可读
    detail = await client.get(f"/inspection/records/{record_id}", headers=headers)
    assert detail.status_code == 200
    detail_body = detail.json()
    assert detail_body["document_type"] == "bidding"
    assert is_archived_legacy_record(detail_body) is True

    # 历史列表可读，展示归档兼容文案
    listing = await client.get("/inspection/records", headers=headers)
    assert listing.status_code == 200
    item = next(it for it in listing.json()["items"] if it["id"] == record_id)
    assert "招投标" in item["classification_display"] or "历史记录" in item["classification_display"]

    # 旧招投标记录不可按旧场景重审
    _patch_runner(monkeypatch, retrieval=_default_retrieval(), run=_default_run())
    reinspect = await client.post(
        f"/inspection/records/{record_id}/inspect", headers=headers, json={"project_id": "default"},
    )
    assert reinspect.status_code == 400
    assert reinspect.json()["detail"]["code"] == "deprecated_application_scenario"


# ---------------------------------------------------------------------------
# 8. 归档资料完整删除（文档/版本/索引节点）
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_archive_delete_removes_document_versions_and_index_nodes(client: AsyncClient, monkeypatch):
    """归档删除：原文件、版本、索引节点、文档记录全部清理，列表不再返回。"""
    from sqlalchemy import select

    headers, user_id = await _register(client, "archive_delete_user")

    async with async_session() as session:
        sub = EngineeringSubcategory(category_key="traditional", name="归档删除分类")
        session.add(sub)
        await session.flush()
        doc = KnowledgeDocument(
            title="用户旧招标资料", subcategory_id=sub.id, owner_type="user",
            owner_user_id=uuid.UUID(user_id), application_scenario="bidding", is_active=False,
        )
        session.add(doc)
        await session.flush()
        version = DocumentVersion(
            document_id=doc.id, version_number=1, display_name="bid.pdf",
            original_file_path="archive/bid/v1/bid.pdf", markdown_path="archive/bid/v1/bid.md",
            status="completed", file_size_bytes=100, file_type=".pdf",
        )
        session.add(version)
        await session.flush()
        doc.current_version_id = version.id
        session.add(IndexNode(
            version_id=version.id, node_type="section",
            path_label="招标文件 > 第一章", content="投标人须知", position=1,
        ))
        await session.commit()
        await session.refresh(doc)
        await session.refresh(version)
        document_id = doc.id
        version_id = version.id

    deleted_paths: list[str] = []

    def _fake_delete(path):
        deleted_paths.append(path)
        return True

    monkeypatch.setattr("app.services.knowledge_archive.delete_file", _fake_delete)

    delete_response = await client.delete(
        f"/inspection/archived-knowledge/{document_id}", headers=headers,
    )
    assert delete_response.status_code == 204, delete_response.text
    # 原文件 + Markdown 均被清理
    assert "archive/bid/v1/bid.pdf" in deleted_paths
    assert "archive/bid/v1/bid.md" in deleted_paths

    # 数据库记录全部清理
    async with async_session() as session:
        assert await session.get(KnowledgeDocument, document_id) is None
        assert await session.get(DocumentVersion, version_id) is None
        nodes = (await session.execute(
            select(IndexNode).where(IndexNode.version_id == version_id)
        )).scalars().all()
        assert nodes == []

    # 列表不再返回该文档
    listing = await client.get("/inspection/archived-knowledge", headers=headers)
    assert listing.status_code == 200
    assert all(d["id"] != document_id for d in listing.json()["documents"])

    # 再次删除幂等返回 404
    second = await client.delete(f"/inspection/archived-knowledge/{document_id}", headers=headers)
    assert second.status_code == 404


# ---------------------------------------------------------------------------
# 9. 审查引擎异常返回脱敏 502，不泄露模型或堆栈
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_inspection_engine_failure_returns_sanitized_502(client: AsyncClient, monkeypatch):
    """Agent 抛异常时返回 502 通用文案，响应不包含模型名/堆栈/内部路径。"""
    headers, _ = await _register(client, "engine_failure_user")

    async def _boom(document_text, deps):
        # 异常信息含敏感内部细节，必须被服务端脱敏
        raise RuntimeError("deepseek-chat model timeout: traceback at /app/services/inspection_runner.py")

    _patch_runner(monkeypatch, retrieval=_default_retrieval(), run=_boom)

    response = await client.post(
        "/inspection/upload",
        headers=headers,
        files={"file": ("合同.txt", "甲方与乙方签订合同。".encode("utf-8"), "text/plain")},
        data={"application_scenario": "contract"},
    )

    assert response.status_code == 502, response.text
    blob = response.text.lower()
    for forbidden in ("deepseek", "model", "traceback", "/app/", "inspection_runner", "runtimeerror"):
        assert forbidden not in blob, f"失败响应不应泄露内部细节：{forbidden}"
