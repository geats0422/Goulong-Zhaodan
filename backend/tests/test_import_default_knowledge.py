from __future__ import annotations

import asyncio
import sys
import types
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

for _mod_name in ["pageindex", "pydantic_ai", "pydantic_ai.agent", "pydantic_ai.models"]:
    if _mod_name not in sys.modules:
        sys.modules[_mod_name] = types.ModuleType(_mod_name)

if "markitdown" not in sys.modules or not hasattr(sys.modules.get("markitdown"), "MarkItDown"):
    _fake_md = types.ModuleType("markitdown")
    _fake_md.MarkItDown = MagicMock()
    sys.modules["markitdown"] = _fake_md

from scripts.import_default_knowledge import (  # noqa: E402
    classify_filename,
    scan_reference_dir,
)


class TestClassifyFilename:
    def test_contract_keyword(self):
        assert classify_filename("合同法.docx") == "contract"

    def test_bidding_keyword_bidding(self):
        assert classify_filename("招标投标法.docx") == "bidding"

    def test_bidding_keyword_government(self):
        assert classify_filename("政府采购办法.pdf") == "bidding"

    def test_contract_keyword_civil_code(self):
        assert classify_filename("民法典合同通则解释.docx") == "contract"

    def test_bidding_keyword_evaluation(self):
        assert classify_filename("评标专家管理办法.pdf") == "bidding"

    def test_fallback_to_bidding(self):
        assert classify_filename("未知文件.txt") == "bidding"

    def test_bidding_keyword_fair_competition(self):
        assert classify_filename("公平竞争审查条例.pdf") == "bidding"

    def test_bidding_keyword_franchise(self):
        assert classify_filename("特许经营管理办法.pdf") == "bidding"

    def test_contract_keyword_civil_code_third_book(self):
        assert classify_filename("《中华人民共和国民法典》第三编合同.docx") == "contract"

    def test_bidding_keyword_tender(self):
        assert classify_filename("招标公告发布管理办法.pdf") == "bidding"

    def test_bidding_keyword_complaint(self):
        assert classify_filename("投诉处理办法.pdf") == "bidding"

    def test_bidding_keyword_publicity(self):
        assert classify_filename("公示信息管理办法.pdf") == "bidding"

    def test_bidding_keyword_self_tender(self):
        assert classify_filename("自行招标试行办法.docx") == "bidding"


class TestScanReferenceDir:
    def test_returns_supported_files_with_scenario(self, tmp_path):
        (tmp_path / "招标投标法.docx").write_bytes(b"fake")
        (tmp_path / "合同法.pdf").write_bytes(b"fake")

        results = scan_reference_dir(tmp_path)

        assert len(results) == 2
        paths = {r[0] for r in results}
        scenarios = {r[1] for r in results}
        assert all(isinstance(p, Path) for p in paths)
        assert "bidding" in scenarios
        assert "contract" in scenarios

    def test_skips_unsupported_extensions(self, tmp_path):
        (tmp_path / "readme.txt").write_text("text")
        (tmp_path / "image.jpg").write_bytes(b"fake")
        (tmp_path / "data.xlsx").write_bytes(b"fake")

        results = scan_reference_dir(tmp_path)

        assert len(results) == 1
        assert results[0][0].suffix == ".xlsx"

    def test_empty_directory(self, tmp_path):
        results = scan_reference_dir(tmp_path)
        assert results == []

    def test_nonexistent_directory(self):
        results = scan_reference_dir(Path("/nonexistent/path"))
        assert results == []

    def test_classifies_all_reference_files(self, tmp_path):
        filenames = [
            "《中华人民共和国民法典》第三编合同.docx",
            "必须招标的工程项目规定.pdf",
            "工程建设项目施工招标投标办法.pdf",
            "政府采购质疑和投诉办法.pdf",
            "公平竞争审查条例.pdf",
            "基础设施和公用事业特许经营管理办法.pdf",
        ]
        for fn in filenames:
            (tmp_path / fn).write_bytes(b"fake")

        results = scan_reference_dir(tmp_path)

        assert len(results) == 6
        result_map = {r[0].name: r[1] for r in results}
        assert result_map["《中华人民共和国民法典》第三编合同.docx"] == "contract"
        assert result_map["必须招标的工程项目规定.pdf"] == "bidding"
        assert result_map["政府采购质疑和投诉办法.pdf"] == "bidding"


class TestImportSingleFile:
    @pytest.mark.asyncio
    async def test_skips_existing_source_path(self, tmp_path):
        from scripts.import_default_knowledge import import_single_file

        fake_file = tmp_path / "招标法.docx"
        fake_file.write_bytes(b"fake content")

        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = MagicMock()
        mock_db.execute = AsyncMock(return_value=mock_result)

        result = await import_single_file(mock_db, fake_file, "bidding")

        assert result["status"] == "skipped"

    @pytest.mark.asyncio
    async def test_creates_document_with_system_owner(self, tmp_path):
        from scripts.import_default_knowledge import import_single_file

        fake_file = tmp_path / "招标法.docx"
        fake_file.write_bytes(b"fake content")

        mock_db = AsyncMock()

        mock_source_result = MagicMock()
        mock_source_result.scalar_one_or_none.return_value = None

        mock_sub_result = MagicMock()
        mock_sub = MagicMock()
        mock_sub.id = 42
        mock_sub.name = "默认法规"
        mock_sub_result.scalar_one_or_none.return_value = mock_sub

        call_count = 0

        async def mock_execute(stmt):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return mock_source_result
            return mock_sub_result

        mock_db.execute = mock_execute

        created_objects = []

        def capture_add(obj):
            created_objects.append(obj)

        mock_db.add = capture_add

        async def mock_flush():
            for obj in created_objects:
                if not hasattr(obj, "id") or obj.id is None:
                    obj.id = len(created_objects) + 100

        mock_db.flush = mock_flush
        mock_db.refresh = AsyncMock()

        with patch("scripts.import_default_knowledge.ingest_document_content", new_callable=AsyncMock) as mock_ingest:
            mock_ingest.return_value = (10, None)

            with patch("scripts.import_default_knowledge.save_upload_file"):
                result = await import_single_file(mock_db, fake_file, "bidding")

        assert result["status"] == "success"
        assert result["node_count"] == 10

        docs = [o for o in created_objects if o.__class__.__name__ == "KnowledgeDocument"]
        assert len(docs) == 1
        doc = docs[0]
        assert doc.owner_type == "system"
        assert doc.owner_user_id is None
        assert doc.application_scenario == "bidding"
        assert doc.source_path is not None


class TestRunImport:
    def test_nonexistent_directory_exits(self):
        from scripts.import_default_knowledge import run_import

        with pytest.raises(SystemExit):
            asyncio.run(run_import(Path("/nonexistent/path")))
