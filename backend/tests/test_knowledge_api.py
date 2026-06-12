from __future__ import annotations

import sys
import types
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

fake_inspector_module = types.ModuleType("agents.inspector")


async def _fake_run_inspection(*args, **kwargs):
    return {"overall_risk": "low", "summary": "", "issues": [], "regulation_refs": []}


fake_inspector_module.run_inspection = _fake_run_inspection
sys.modules["agents.inspector"] = fake_inspector_module

from core.auth import get_current_user  # noqa: E402
from core.database import get_db_session  # noqa: E402
from main import app  # noqa: E402


async def _override_user():
    return {"user_id": "42", "api_key": "goulong-dev-key"}


@pytest.fixture
def mock_db():
    session = AsyncMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    session.flush = AsyncMock()
    session.add = MagicMock()
    session.add_all = MagicMock()
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


def _make_subcategory(id=1, category_key="traditional", name="房建"):
    sub = MagicMock()
    sub.id = id
    sub.category_key = category_key
    sub.name = name
    return sub


def _make_document(id=1, title="招标文件", subcategory_id=1, current_version_id=1):
    return MagicMock(
        spec=["id", "title", "subcategory_id", "current_version_id",
               "current_version", "subcategory", "created_at", "updated_at",
               "owner_type", "owner_user_id", "application_scenario", "source_path"],
        id=id,
        title=title,
        subcategory_id=subcategory_id,
        current_version_id=current_version_id,
        current_version=None,
        subcategory=None,
        owner_type="user",
        owner_user_id=42,
        application_scenario="bidding",
        source_path=None,
        created_at=datetime(2025, 1, 1),
        updated_at=datetime(2025, 1, 1),
    )


def _result_scalar(value):
    result = MagicMock()
    result.scalar_one_or_none.return_value = value
    return result


def _make_version(id=1, document_id=1, version_number=1, display_name="招标文件.pdf",
                  status="completed", original_file_path="/tmp/test.pdf",
                  file_size_bytes=100, file_type=".pdf"):
    return MagicMock(
        spec=["id", "document_id", "version_number", "display_name", "status",
               "original_file_path", "file_size_bytes", "file_type",
               "markdown_path", "error_message", "created_at"],
        id=id,
        document_id=document_id,
        version_number=version_number,
        display_name=display_name,
        status=status,
        original_file_path=original_file_path,
        file_size_bytes=file_size_bytes,
        file_type=file_type,
        markdown_path=None,
        error_message=None,
        created_at=datetime(2025, 1, 1),
    )


def _make_node(id=1, version_id=1, parent_id=None, node_type="chapter",
               path_label="第一章", content="内容", position=1):
    return MagicMock(
        spec=["id", "version_id", "parent_id", "node_type", "path_label",
               "content", "position", "page_index_id", "created_at"],
        id=id,
        version_id=version_id,
        parent_id=parent_id,
        node_type=node_type,
        path_label=path_label,
        content=content,
        position=position,
        page_index_id=None,
        created_at=datetime(2025, 1, 1),
    )


class TestListSubcategories:
    def test_returns_subcategories_for_valid_category(self, client, mock_db):
        sub = _make_subcategory()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [sub]
        mock_db.execute.return_value = mock_result

        response = client.get("/api/v1/knowledge/subcategories", params={"category": "traditional"})
        assert response.status_code == 200
        data = response.json()
        assert data["category"] == "traditional"
        assert data["category_label"] == "传统基建"
        assert len(data["subcategories"]) == 1
        assert data["subcategories"][0]["name"] == "房建"

    def test_invalid_category_returns_400(self, client, mock_db):
        response = client.get("/api/v1/knowledge/subcategories", params={"category": "invalid"})
        assert response.status_code == 400

    def test_empty_subcategories(self, client, mock_db):
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db.execute.return_value = mock_result

        response = client.get("/api/v1/knowledge/subcategories", params={"category": "traditional"})
        assert response.status_code == 200
        assert response.json()["subcategories"] == []


class TestListDocuments:
    def test_returns_documents_for_subcategory(self, client, mock_db):
        doc = _make_document()
        ver = _make_version()
        sub = _make_subcategory()
        doc.current_version = ver
        doc.subcategory = sub

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [doc]
        mock_db.execute.return_value = mock_result

        response = client.get("/api/v1/knowledge/documents", params={"subcategory_id": 1})
        assert response.status_code == 200
        data = response.json()
        assert len(data["documents"]) == 1
        assert data["documents"][0]["title"] == "招标文件"

    def test_empty_documents(self, client, mock_db):
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db.execute.return_value = mock_result

        response = client.get("/api/v1/knowledge/documents", params={"subcategory_id": 999})
        assert response.status_code == 200
        assert response.json()["documents"] == []


class TestGetDocumentNodes:
    def test_returns_node_tree(self, client, mock_db):
        doc = _make_document(id=1, current_version_id=1)
        ver = _make_version(id=1, version_number=1)

        node1 = _make_node(id=1, parent_id=None, node_type="chapter", path_label="第一章")
        node2 = _make_node(id=2, parent_id=1, node_type="section", path_label="1.1")

        mock_doc_result = MagicMock()
        mock_doc_result.scalar_one_or_none.return_value = doc

        mock_ver_result = MagicMock()
        mock_ver_result.scalar_one_or_none.return_value = ver

        mock_nodes_result = MagicMock()
        mock_nodes_result.scalars.return_value.all.return_value = [node1, node2]

        mock_db.execute.side_effect = [mock_doc_result, mock_ver_result, mock_nodes_result]

        response = client.get("/api/v1/knowledge/documents/1/nodes")
        assert response.status_code == 200
        data = response.json()
        assert data["document_id"] == 1
        assert data["version_number"] == 1
        assert len(data["nodes"]) == 1
        assert data["nodes"][0]["node_type"] == "chapter"
        assert len(data["nodes"][0]["children"]) == 1
        assert data["nodes"][0]["children"][0]["path_label"] == "1.1"

    def test_document_not_found(self, client, mock_db):
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        response = client.get("/api/v1/knowledge/documents/999/nodes")
        assert response.status_code == 404


class TestUploadAndIngest:
    def test_rejects_invalid_file_type(self, client, mock_db):
        response = client.post(
            "/api/v1/knowledge/upload",
            data={"category": "traditional"},
            files={"file": ("test.txt", b"content", "text/plain")},
        )
        assert response.status_code == 400

    def test_rejects_invalid_category(self, client, mock_db):
        response = client.post(
            "/api/v1/knowledge/upload",
            data={"category": "invalid"},
            files={"file": ("test.pdf", b"content", "application/pdf")},
        )
        assert response.status_code == 400

    def test_rejects_missing_subcategory_params(self, client, mock_db):
        response = client.post(
            "/api/v1/knowledge/upload",
            data={"category": "traditional"},
            files={"file": ("test.pdf", b"content", "application/pdf")},
        )
        assert response.status_code == 400

    def test_upload_accepts_application_scenario(self, client, mock_db, monkeypatch, tmp_path):
        import routers.knowledge as knowledge_router
        import services.knowledge_ingestion as ingestion_mod

        sub = _make_subcategory(id=7, category_key="traditional", name="房建")
        mock_db.execute.side_effect = [
            _result_scalar(None),  # subcategory does not exist, create it
            _result_scalar(None),  # no existing document for owner/scenario
        ]

        def assign_ids(obj):
            if obj.__class__.__name__ == "EngineeringSubcategory":
                obj.id = 7
            elif obj.__class__.__name__ == "KnowledgeDocument":
                obj.id = 11
            elif obj.__class__.__name__ == "DocumentVersion":
                obj.id = 13

        mock_db.refresh.side_effect = assign_ids
        monkeypatch.setattr(knowledge_router, "build_storage_path", lambda *args: tmp_path)
        monkeypatch.setattr(knowledge_router, "save_upload_file", lambda path, content: path.write_bytes(content))
        monkeypatch.setattr(ingestion_mod, "convert_to_markdown", lambda path: "# 标题\n内容")
        monkeypatch.setattr(ingestion_mod, "build_index_nodes", AsyncMock(return_value=[]))

        response = client.post(
            "/api/v1/knowledge/upload",
            data={
                "category": "traditional",
                "subcategory_name": sub.name,
                "application_scenario": "contract",
            },
            files={"file": ("合同文件.pdf", b"content", "application/pdf")},
        )

        assert response.status_code == 200
        assert response.json()["application_scenario"] == "contract"
        created_doc = next(
            call.args[0]
            for call in mock_db.add.call_args_list
            if call.args[0].__class__.__name__ == "KnowledgeDocument"
        )
        assert created_doc.owner_type == "user"
        assert created_doc.owner_user_id == 42
        assert created_doc.application_scenario == "contract"
        existing_doc_query = str(mock_db.execute.call_args_list[1].args[0])
        assert "owner_type" in existing_doc_query
        assert "owner_user_id" in existing_doc_query
        assert "application_scenario" in existing_doc_query

    def test_upload_rejects_invalid_application_scenario(self, client, mock_db):
        response = client.post(
            "/api/v1/knowledge/upload",
            data={
                "category": "traditional",
                "subcategory_name": "房建",
                "application_scenario": "invalid",
            },
            files={"file": ("test.pdf", b"content", "application/pdf")},
        )

        assert response.status_code == 400
        mock_db.execute.assert_not_called()


class TestGetOverview:
    def test_returns_nested_structure(self, client, mock_db):
        sub = _make_subcategory(id=1, category_key="traditional", name="房建")
        doc = _make_document(id=1, title="招标文件", subcategory_id=1)
        ver = _make_version(id=1, display_name="招标文件.pdf", status="completed")
        doc.current_version = ver
        doc.subcategory = sub
        sub.documents = [doc]

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [sub]
        mock_db.execute.return_value = mock_result

        response = client.get("/api/v1/knowledge/overview")
        assert response.status_code == 200
        data = response.json()
        assert len(data["categories"]) == 4
        trad = next(c for c in data["categories"] if c["key"] == "traditional")
        assert trad["label"] == "传统基建"
        assert len(trad["subcategories"]) == 1
        assert trad["subcategories"][0]["name"] == "房建"
        assert len(trad["subcategories"][0]["documents"]) == 1
        doc_item = trad["subcategories"][0]["documents"][0]
        assert doc_item["title"] == "招标文件"
        assert doc_item["owner_type"] == "user"
        assert doc_item["application_scenario"] == "bidding"

    def test_overview_system_document_metadata(self, client, mock_db):
        sub = _make_subcategory(id=1, category_key="traditional", name="房建")
        doc = _make_document(id=1, title="默认法规", subcategory_id=1)
        doc.owner_type = "system"
        doc.owner_user_id = None
        doc.application_scenario = "contract"
        sub.documents = [doc]

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [sub]
        mock_db.execute.return_value = mock_result

        response = client.get("/api/v1/knowledge/overview")

        assert response.status_code == 200
        data = response.json()
        trad = next(c for c in data["categories"] if c["key"] == "traditional")
        doc_item = trad["subcategories"][0]["documents"][0]
        assert doc_item["owner_type"] == "system"
        assert doc_item["application_scenario"] == "contract"

    def test_overview_with_no_subcategories(self, client, mock_db):
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db.execute.return_value = mock_result

        response = client.get("/api/v1/knowledge/overview")
        assert response.status_code == 200
        data = response.json()
        assert len(data["categories"]) == 4
        for cat in data["categories"]:
            assert cat["subcategories"] == []

    def test_overview_document_version_info(self, client, mock_db):
        sub = _make_subcategory(id=2, category_key="new_infrastructure", name="算力")
        doc = _make_document(id=2, title="网络规划", subcategory_id=2)
        ver = _make_version(id=2, version_number=3, display_name="网络规划(2).pdf", status="completed")
        doc.current_version = ver
        doc.subcategory = sub
        sub.documents = [doc]

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [sub]
        mock_db.execute.return_value = mock_result

        response = client.get("/api/v1/knowledge/overview")
        assert response.status_code == 200
        data = response.json()
        new_infra = next(c for c in data["categories"] if c["key"] == "new_infrastructure")
        doc_item = new_infra["subcategories"][0]["documents"][0]
        assert doc_item["current_version"]["version_number"] == 3
        assert doc_item["current_version"]["display_name"] == "网络规划(2).pdf"

    def test_overview_document_without_version(self, client, mock_db):
        sub = _make_subcategory(id=3, category_key="urban_renewal", name="旧改")
        doc = _make_document(id=3, title="改造方案", subcategory_id=3, current_version_id=None)
        doc.current_version = None
        doc.subcategory = sub
        sub.documents = [doc]

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [sub]
        mock_db.execute.return_value = mock_result

        response = client.get("/api/v1/knowledge/overview")
        assert response.status_code == 200
        data = response.json()
        urban = next(c for c in data["categories"] if c["key"] == "urban_renewal")
        doc_item = urban["subcategories"][0]["documents"][0]
        assert doc_item["current_version"] is None


class TestAuthEnforced:
    def test_knowledge_subcategories_requires_api_key(self):
        bare_client = TestClient(app)
        response = bare_client.get(
            "/api/v1/knowledge/subcategories",
            params={"category": "traditional"},
        )
        assert response.status_code == 401

    def test_knowledge_documents_requires_api_key(self):
        bare_client = TestClient(app)
        response = bare_client.get(
            "/api/v1/knowledge/documents",
            params={"subcategory_id": 1},
        )
        assert response.status_code == 401

    def test_knowledge_upload_requires_api_key(self):
        bare_client = TestClient(app)
        response = bare_client.post(
            "/api/v1/knowledge/upload",
            data={"category": "traditional"},
            files={"file": ("test.pdf", b"content", "application/pdf")},
        )
        assert response.status_code == 401

    def test_knowledge_nodes_requires_api_key(self):
        bare_client = TestClient(app)
        response = bare_client.get("/api/v1/knowledge/documents/1/nodes")
        assert response.status_code == 401
