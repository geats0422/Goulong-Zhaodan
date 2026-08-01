from __future__ import annotations

import logging
import sys
import types
import uuid
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

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

from app.core.auth import CurrentUserContext, get_current_user  # noqa: E402
from app.core.database import get_db_session  # noqa: E402
from main import app  # noqa: E402

USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000042")
OTHER_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000099")


async def _override_user():
    return CurrentUserContext(user_id=USER_ID)


@pytest.fixture
def mock_db():
    session = AsyncMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    session.flush = AsyncMock()
    session.rollback = AsyncMock()
    session.add = MagicMock()
    session.add_all = MagicMock()
    session.delete = AsyncMock()
    session.execute = AsyncMock()
    session.scalar = AsyncMock()
    session.scalars = AsyncMock()
    return session


@pytest.fixture
def client(mock_db):
    async def _override():
        yield mock_db

    app.dependency_overrides[get_db_session] = _override
    app.dependency_overrides[get_current_user] = _override_user
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.pop(get_db_session, None)
        app.dependency_overrides.pop(get_current_user, None)


def _result_scalar(value):
    result = MagicMock()
    result.scalar_one_or_none.return_value = value
    return result


def _result_scalars_all(values):
    result = MagicMock()
    result.scalars.return_value.all.return_value = list(values)
    return result


def _delete_side_effect(document, versions):
    """构造删除流程的 db.execute.side_effect 序列。

    delete_user_archived_document 依次执行：
    1. select(KnowledgeDocument) → scalar_one_or_none → document
    2. select(DocumentVersion) → scalars().all() → versions
    3. delete(IndexNode) → 无返回值需求
    4. delete(DocumentVersion) → 无返回值需求
    """
    return [
        _result_scalar(document),
        _result_scalars_all(versions),
        MagicMock(),  # delete IndexNode
        MagicMock(),  # delete DocumentVersion
    ]


def _make_subcategory(id=1, category_key="traditional", name="房建"):
    sub = MagicMock()
    sub.id = id
    sub.category_key = category_key
    sub.name = name
    return sub


def _make_version(
    id=1,
    document_id=1,
    version_number=1,
    display_name="招标文件.pdf",
    status="completed",
    original_file_path="traditional/房建/招标文件/v1/招标文件.pdf",
    markdown_path="traditional/房建/招标文件/v1/招标文件.md",
):
    return MagicMock(
        spec=[
            "id", "document_id", "version_number", "display_name", "status",
            "original_file_path", "file_size_bytes", "file_type",
            "markdown_path", "error_message", "created_at",
        ],
        id=id,
        document_id=document_id,
        version_number=version_number,
        display_name=display_name,
        status=status,
        original_file_path=original_file_path,
        file_size_bytes=100,
        file_type=".pdf",
        markdown_path=markdown_path,
        error_message=None,
        created_at=datetime(2025, 1, 1),
    )


def _make_document(
    id=1,
    title="招标文件",
    subcategory_id=1,
    current_version_id=1,
    application_scenario="bidding",
    is_active=True,
    owner_type="user",
    owner_user_id=USER_ID,
):
    return MagicMock(
        spec=[
            "id", "title", "subcategory_id", "current_version_id",
            "current_version", "subcategory", "created_at", "updated_at",
            "owner_type", "owner_user_id", "application_scenario", "is_active",
            "source_path", "engineering_type_key", "contract_type_key",
            "rule_package_key", "versions",
        ],
        id=id,
        title=title,
        subcategory_id=subcategory_id,
        current_version_id=current_version_id,
        current_version=None,
        subcategory=None,
        owner_type=owner_type,
        owner_user_id=owner_user_id,
        application_scenario=application_scenario,
        is_active=is_active,
        source_path=None,
        engineering_type_key=None,
        contract_type_key=None,
        rule_package_key=None,
        versions=[],
        created_at=datetime(2025, 1, 1),
        updated_at=datetime(2025, 1, 1),
    )


# --- 任务9.1 上传固定 contract 场景，写入类别绑定 ---


class TestUploadFixedContractScenario:
    def test_upload_rejects_bidding_scenario(self, client, mock_db):
        response = client.post(
            "/api/v1/knowledge/upload",
            data={
                "category": "traditional",
                "subcategory_name": "房建",
                "application_scenario": "bidding",
            },
            files={"file": ("招标文件.pdf", b"content", "application/pdf")},
        )
        assert response.status_code == 400
        detail = response.json()["detail"]
        assert detail["code"] == "deprecated_application_scenario"

    def test_upload_writes_engineering_and_contract_type_binding(
        self, client, mock_db, monkeypatch
    ):
        import app.api.v1.knowledge as knowledge_router

        mock_db.execute.side_effect = [
            _result_scalar(None),  # subcategory create lookup
            _result_scalar(None),  # existing document lookup
        ]

        captured: dict = {}

        def assign_ids(obj):
            name = obj.__class__.__name__
            if name == "EngineeringSubcategory":
                obj.id = 7
            elif name == "KnowledgeDocument":
                obj.id = 11
                captured["document"] = obj
            elif name == "DocumentVersion":
                obj.id = 13

        mock_db.refresh.side_effect = assign_ids
        monkeypatch.setattr(knowledge_router, "build_storage_path", lambda *a, **k: "test/dir")
        monkeypatch.setattr(knowledge_router, "save_file", lambda path, content: None)
        monkeypatch.setattr(knowledge_router, "validate_file_magic", lambda *a, **k: None)
        monkeypatch.setattr(
            knowledge_router, "create_document_job",
            AsyncMock(return_value=MagicMock(job_id="job_123")),
        )

        response = client.post(
            "/api/v1/knowledge/upload",
            data={
                "category": "traditional",
                "subcategory_name": "房建",
                "application_scenario": "contract",
                "engineering_type_key": "municipal-road",
                "contract_type_key": "professional-subcontract",
            },
            files={"file": ("合同文件.pdf", b"content", "application/pdf")},
        )

        assert response.status_code == 200, response.text
        document = captured["document"]
        assert document.application_scenario == "contract"
        assert document.engineering_type_key == "municipal-road"
        assert document.contract_type_key == "professional-subcontract"

    def test_upload_without_type_keys_keeps_none_binding(
        self, client, mock_db, monkeypatch
    ):
        import app.api.v1.knowledge as knowledge_router

        mock_db.execute.side_effect = [
            _result_scalar(None),
            _result_scalar(None),
        ]

        captured: dict = {}

        def assign_ids(obj):
            name = obj.__class__.__name__
            if name == "EngineeringSubcategory":
                obj.id = 7
            elif name == "KnowledgeDocument":
                obj.id = 11
                captured["document"] = obj
            elif name == "DocumentVersion":
                obj.id = 13

        mock_db.refresh.side_effect = assign_ids
        monkeypatch.setattr(knowledge_router, "build_storage_path", lambda *a, **k: "test/dir")
        monkeypatch.setattr(knowledge_router, "save_file", lambda path, content: None)
        monkeypatch.setattr(knowledge_router, "validate_file_magic", lambda *a, **k: None)
        monkeypatch.setattr(
            knowledge_router, "create_document_job",
            AsyncMock(return_value=MagicMock(job_id="job_123")),
        )

        response = client.post(
            "/api/v1/knowledge/upload",
            data={
                "category": "traditional",
                "subcategory_name": "房建",
                "application_scenario": "contract",
            },
            files={"file": ("合同文件.pdf", b"content", "application/pdf")},
        )

        assert response.status_code == 200, response.text
        document = captured["document"]
        assert document.application_scenario == "contract"
        assert document.engineering_type_key is None
        assert document.contract_type_key is None

    def test_upload_blank_type_keys_treated_as_none(
        self, client, mock_db, monkeypatch
    ):
        import app.api.v1.knowledge as knowledge_router

        mock_db.execute.side_effect = [
            _result_scalar(None),
            _result_scalar(None),
        ]

        captured: dict = {}

        def assign_ids(obj):
            name = obj.__class__.__name__
            if name == "EngineeringSubcategory":
                obj.id = 7
            elif name == "KnowledgeDocument":
                obj.id = 11
                captured["document"] = obj
            elif name == "DocumentVersion":
                obj.id = 13

        mock_db.refresh.side_effect = assign_ids
        monkeypatch.setattr(knowledge_router, "build_storage_path", lambda *a, **k: "test/dir")
        monkeypatch.setattr(knowledge_router, "save_file", lambda path, content: None)
        monkeypatch.setattr(knowledge_router, "validate_file_magic", lambda *a, **k: None)
        monkeypatch.setattr(
            knowledge_router, "create_document_job",
            AsyncMock(return_value=MagicMock(job_id="job_123")),
        )

        response = client.post(
            "/api/v1/knowledge/upload",
            data={
                "category": "traditional",
                "subcategory_name": "房建",
                "application_scenario": "contract",
                "engineering_type_key": "   ",
                "contract_type_key": "",
            },
            files={"file": ("合同文件.pdf", b"content", "application/pdf")},
        )

        assert response.status_code == 200, response.text
        document = captured["document"]
        assert document.engineering_type_key is None
        assert document.contract_type_key is None


# --- 任务9.2 GET /inspection/archived-knowledge 只读列表 ---


class TestArchivedKnowledgeList:
    def test_list_returns_only_current_user_bidding_documents(self, client, mock_db):
        doc_user = _make_document(
            id=10, title="我的招投标资料", application_scenario="bidding",
            owner_type="user", owner_user_id=USER_ID, is_active=False,
        )
        mock_db.execute.return_value = _result_scalars_all([doc_user])

        response = client.get("/inspection/archived-knowledge")
        assert response.status_code == 200, response.text
        data = response.json()

        assert "documents" in data
        assert len(data["documents"]) == 1
        item = data["documents"][0]
        assert item["id"] == 10
        assert item["title"] == "我的招投标资料"
        assert item["application_scenario"] == "bidding"
        assert item["owner_type"] == "user"

        query_sql = str(mock_db.execute.call_args.args[0])
        # 参数化查询使用列名过滤，验证三个维度的过滤条件都存在
        assert "application_scenario" in query_sql
        assert "owner_user_id" in query_sql
        assert "owner_type" in query_sql

    def test_list_returns_empty_when_user_has_no_archived_documents(self, client, mock_db):
        mock_db.execute.return_value = _result_scalars_all([])

        response = client.get("/inspection/archived-knowledge")
        assert response.status_code == 200
        assert response.json()["documents"] == []

    def test_list_requires_authentication(self):
        bare_client = TestClient(app)
        response = bare_client.get("/inspection/archived-knowledge")
        assert response.status_code == 401


# --- 任务9.3 DELETE /inspection/archived-knowledge/{id} 用户完整删除 ---


class TestDeleteArchivedKnowledge:
    def test_delete_removes_files_markdown_nodes_versions_and_record(
        self, client, mock_db, monkeypatch
    ):
        doc = _make_document(
            id=20, title="归档招标资料", application_scenario="bidding",
            owner_type="user", owner_user_id=USER_ID, is_active=False,
        )
        version = _make_version(
            id=30, document_id=20,
            original_file_path="archive/v1/file.pdf",
            markdown_path="archive/v1/file.md",
        )

        mock_db.execute.side_effect = _delete_side_effect(doc, [version])

        delete_calls: list[str] = []

        def fake_delete(path):
            delete_calls.append(path)
            return True

        monkeypatch.setattr(
            "app.services.knowledge_archive.delete_file", fake_delete
        )

        response = client.delete("/inspection/archived-knowledge/20")

        assert response.status_code == 204, response.text
        # 删除原文件 + Markdown
        assert "archive/v1/file.pdf" in delete_calls
        assert "archive/v1/file.md" in delete_calls
        # 数据库事务被 commit
        mock_db.commit.assert_awaited()
        # 文档记录被删除
        mock_db.delete.assert_awaited()

    def test_delete_writes_audit_log(self, client, mock_db, monkeypatch, caplog):
        import app.services.knowledge_archive as archive_mod

        doc = _make_document(
            id=21, title="归档招标资料", application_scenario="bidding",
            owner_type="user", owner_user_id=USER_ID, is_active=False,
        )
        version = _make_version(id=31, document_id=21)

        mock_db.execute.side_effect = _delete_side_effect(doc, [version])
        monkeypatch.setattr("app.services.knowledge_archive.delete_file", lambda p: True)

        with caplog.at_level(logging.INFO, logger=archive_mod._logger.name):
            response = client.delete("/inspection/archived-knowledge/21")

        assert response.status_code == 204
        audit_records = [
            r for r in caplog.records
            if getattr(r, "audit_event", "") == "archived_knowledge_deleted"
        ]
        assert audit_records, "应当写入归档删除审计日志"
        record = audit_records[0]
        assert getattr(record, "document_id", None) == 21
        assert getattr(record, "user_id", None) == str(USER_ID)

    def test_delete_forbidden_for_other_users_document(self, client, mock_db):
        # 跨用户查询不应返回他人文档
        mock_db.execute.side_effect = _delete_side_effect(None, [])

        response = client.delete("/inspection/archived-knowledge/99")

        assert response.status_code == 404
        mock_db.delete.assert_not_awaited()

    def test_delete_forbidden_for_system_archived_document(self, client, mock_db):
        # 系统归档资料按 owner_type=user 过滤后查不到
        mock_db.execute.side_effect = _delete_side_effect(None, [])

        response = client.delete("/inspection/archived-knowledge/100")

        assert response.status_code == 404
        mock_db.delete.assert_not_awaited()

    def test_delete_rejects_non_archived_document(self, client, mock_db):
        # contract 文档不在归档删除范围（按 application_scenario=bidding 过滤）
        mock_db.execute.side_effect = _delete_side_effect(None, [])

        response = client.delete("/inspection/archived-knowledge/200")

        assert response.status_code == 404

    def test_delete_is_idempotent_on_recall(self, client, mock_db, monkeypatch):
        doc = _make_document(
            id=22, title="归档", application_scenario="bidding",
            owner_type="user", owner_user_id=USER_ID, is_active=False,
        )
        version = _make_version(id=32, document_id=22)

        # 第一次：返回 document + versions；第二次：document 已删，返回 None
        mock_db.execute.side_effect = (
            _delete_side_effect(doc, [version]) + _delete_side_effect(None, [])
        )
        monkeypatch.setattr("app.services.knowledge_archive.delete_file", lambda p: True)

        first = client.delete("/inspection/archived-knowledge/22")
        second = client.delete("/inspection/archived-knowledge/22")

        assert first.status_code == 204
        assert second.status_code == 404

    def test_delete_rolls_back_on_database_failure(self, client, mock_db, monkeypatch):
        from sqlalchemy.exc import OperationalError

        doc = _make_document(
            id=23, title="归档", application_scenario="bidding",
            owner_type="user", owner_user_id=USER_ID, is_active=False,
        )
        version = _make_version(id=33, document_id=23)

        mock_db.execute.side_effect = _delete_side_effect(doc, [version])
        # commit 抛出数据库异常（SQLAlchemyError 子类）
        mock_db.commit.side_effect = OperationalError(
            statement="DELETE FROM ...", params={}, orig=Exception("db down")
        )
        monkeypatch.setattr("app.services.knowledge_archive.delete_file", lambda p: True)

        response = client.delete("/inspection/archived-knowledge/23")

        # 数据库失败应回滚并返回 5xx，文档记录保持
        assert response.status_code == 503
        detail = response.json()["detail"]
        assert detail["code"] == "archive_delete_failed"
        mock_db.rollback.assert_awaited()

    def test_delete_continues_when_file_already_missing(self, client, mock_db, monkeypatch):
        """文件已不存在时，delete_file 返回 False，不应阻塞删除流程。"""
        doc = _make_document(
            id=24, title="归档", application_scenario="bidding",
            owner_type="user", owner_user_id=USER_ID, is_active=False,
        )
        version = _make_version(id=34, document_id=24)

        mock_db.execute.side_effect = _delete_side_effect(doc, [version])
        monkeypatch.setattr("app.services.knowledge_archive.delete_file", lambda p: False)

        response = client.delete("/inspection/archived-knowledge/24")

        assert response.status_code == 204
        mock_db.commit.assert_awaited()

    def test_delete_requires_authentication(self):
        bare_client = TestClient(app)
        response = bare_client.delete("/inspection/archived-knowledge/1")
        assert response.status_code == 401


# --- 任务9.4 归档资料不可重新启用 ---


class TestArchivedKnowledgeReadOnly:
    def test_no_patch_reactivate_endpoint(self, client, mock_db):
        """归档资料没有重新启用入口：PATCH 路径应 405（路由已注册 GET/DELETE）。"""
        for scenario_body in [
            {"is_active": True},
            {"application_scenario": "contract"},
            {"application_scenario": "contract", "is_active": True},
        ]:
            response = client.patch(
                "/inspection/archived-knowledge/1",
                json=scenario_body,
            )
            assert response.status_code == 405, (
                f"归档资料不可通过 PATCH 重新启用: {scenario_body}"
            )

    def test_no_restore_endpoint(self, client, mock_db):
        response = client.post(
            "/inspection/archived-knowledge/1/restore",
            json={},
        )
        assert response.status_code in {404, 405}
