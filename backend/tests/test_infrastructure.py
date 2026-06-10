from __future__ import annotations

import sys
import types
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

for mod_name in [
    "markitdown",
    "pageindex",
    "pydantic_ai",
    "pydantic_ai.agent",
    "pydantic_ai.models",
]:
    if mod_name not in sys.modules:
        sys.modules[mod_name] = types.ModuleType(mod_name)

from core.constants import (  # noqa: E402
    APPLICATION_SCENARIOS,
    validate_application_scenario,
    validate_category,
    validate_file_type,
)
from models import Base, DocumentVersion, EngineeringSubcategory, IndexNode, KnowledgeDocument  # noqa: E402
from services.file_storage import build_storage_path, ensure_storage_dir, save_upload_file  # noqa: E402


def test_validate_category_valid() -> None:
    assert validate_category("new_infrastructure") == "新基建"
    assert validate_category("traditional") == "传统基建"
    assert validate_category("urban_renewal") == "城市更新"


def test_validate_category_invalid() -> None:
    with pytest.raises(ValueError, match="Invalid category key"):
        validate_category("nonexistent")


def test_validate_application_scenario_valid() -> None:
    assert APPLICATION_SCENARIOS["bidding"] == "招投标"
    assert validate_application_scenario("bidding") == "招投标"
    assert validate_application_scenario("contract") == "合同"


def test_validate_application_scenario_invalid() -> None:
    with pytest.raises(ValueError, match="Invalid application scenario"):
        validate_application_scenario("invalid")


def test_validate_file_type_valid() -> None:
    assert validate_file_type("test.docx") == ".docx"
    assert validate_file_type("test.doc") == ".doc"
    assert validate_file_type("test.pptx") == ".pptx"
    assert validate_file_type("test.xlsx") == ".xlsx"
    assert validate_file_type("test.pdf") == ".pdf"
    assert validate_file_type("UPPER.PDF") == ".pdf"


def test_validate_file_type_invalid() -> None:
    with pytest.raises(ValueError, match="Invalid file type"):
        validate_file_type("test.txt")


def test_build_storage_path() -> None:
    path = build_storage_path("traditional", "房建", "招标文件", 1)
    assert path == Path("data/knowledge") / "traditional" / "房建" / "招标文件" / "v1"


def test_build_storage_path_version() -> None:
    path = build_storage_path("new_infrastructure", "5G", "设计方案", 3)
    assert str(path).endswith("v3")


def test_ensure_storage_dir(tmp_path: Path) -> None:
    target = tmp_path / "a" / "b" / "c"
    result = ensure_storage_dir(target)
    assert result == target
    assert target.exists()


def test_save_upload_file(tmp_path: Path) -> None:
    file_path = tmp_path / "sub" / "test.docx"
    content = b"hello world"
    result = save_upload_file(file_path, content)
    assert result == file_path
    assert file_path.read_bytes() == content


def test_models_importable() -> None:
    assert EngineeringSubcategory.__tablename__ == "engineering_subcategories"
    assert KnowledgeDocument.__tablename__ == "knowledge_documents"
    assert hasattr(KnowledgeDocument, "owner_type")
    assert hasattr(KnowledgeDocument, "owner_user_id")
    assert hasattr(KnowledgeDocument, "application_scenario")
    assert hasattr(KnowledgeDocument, "source_path")
    assert DocumentVersion.__tablename__ == "document_versions"
    assert IndexNode.__tablename__ == "index_nodes"


@pytest.mark.asyncio
async def test_tables_created() -> None:
    from sqlalchemy.ext.asyncio import create_async_engine

    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with engine.begin() as conn:
        tables = await conn.run_sync(
            lambda sync_conn: sync_conn.execute(
                __import__("sqlalchemy").text(
                    "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
                )
            ).fetchall(),
        )
    table_names = {row[0] for row in tables}
    assert "engineering_subcategories" in table_names
    assert "knowledge_documents" in table_names
    assert "document_versions" in table_names
    assert "index_nodes" in table_names
    await engine.dispose()
