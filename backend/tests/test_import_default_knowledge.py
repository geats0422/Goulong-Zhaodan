from __future__ import annotations

import asyncio
import hashlib
import json
import sys
import types
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import select

for _mod_name in ["pageindex", "pydantic_ai", "pydantic_ai.agent", "pydantic_ai.models"]:
    if _mod_name not in sys.modules:
        sys.modules[_mod_name] = types.ModuleType(_mod_name)

if "markitdown" not in sys.modules or not hasattr(sys.modules.get("markitdown"), "MarkItDown"):
    _fake_md = types.ModuleType("markitdown")
    _fake_md.MarkItDown = MagicMock()
    sys.modules["markitdown"] = _fake_md

from scripts.import_default_knowledge import (  # noqa: E402
    DEFAULT_MANIFEST_PATH,
    classify_filename,
    deactivate_previous_rule_packages,
    import_manifest_source,
    load_manifest,
    package_base_name,
    scan_reference_dir,
    validate_manifest,
)
from app.core.database import async_session  # noqa: E402
from app.models import (  # noqa: E402
    EngineeringSubcategory,
    InspectionRecord,
    KnowledgeDocument,
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

    def test_fallback_to_contract_for_unknown_file(self):
        # 兜底逻辑已从 bidding 改为合同规则包导入（contract）
        assert classify_filename("未知文件.txt") == "contract"

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

            with patch("scripts.import_default_knowledge.save_file"):
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


# ---------------------------------------------------------------------------
# 任务 10：官方默认合同规则包 manifest 导入
# ---------------------------------------------------------------------------

DEFAULT_RULE_PACKAGE_KEY = "general-engineering-contract-rules:v1"


def _sha256_hex(content: bytes) -> str:
    return "sha256:" + hashlib.sha256(content).hexdigest()


def _build_manifest(
    *,
    rule_package_key: str = DEFAULT_RULE_PACKAGE_KEY,
    application_scenario: str = "contract",
    allowlist: list[str] | None = None,
    sources: list[dict] | None = None,
) -> dict:
    return {
        "rule_package_key": rule_package_key,
        "application_scenario": application_scenario,
        "engineering_type_key": "general-engineering",
        "contract_type_key": "other",
        "subcategory_category_key": "general",
        "subcategory_name": "默认法规",
        "official_domain_allowlist": allowlist
        if allowlist is not None
        else ["npc.gov.cn", "gov.cn", "mohurd.gov.cn", "court.gov.cn"],
        "sources": sources if sources is not None else [],
    }


def _build_source(
    filename: str,
    content: bytes,
    *,
    official_url: str = "http://www.npc.gov.cn/example.html",
    title: str | None = None,
    content_hash: str | None = None,
) -> tuple[dict, bytes]:
    source = {
        "title": title or filename,
        "official_url": official_url,
        "publish_date": "2020-05-28",
        "effective_date": "2021-01-01",
        "version": "2020版",
        "fetched_date": "2026-08-01",
        "content_hash": content_hash if content_hash is not None else _sha256_hex(content),
        "filename": filename,
    }
    return source, content


class TestLoadManifest:
    def test_loads_default_manifest_with_contract_rule_package(self):
        manifest = load_manifest(DEFAULT_MANIFEST_PATH)
        assert manifest["rule_package_key"] == DEFAULT_RULE_PACKAGE_KEY
        assert manifest["application_scenario"] == "contract"
        assert isinstance(manifest["official_domain_allowlist"], list)
        assert len(manifest["official_domain_allowlist"]) > 0
        assert len(manifest["sources"]) >= 1

    def test_missing_file_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            load_manifest(tmp_path / "missing.json")


class TestPackageBaseName:
    def test_strips_version_suffix(self):
        assert package_base_name("general-engineering-contract-rules:v1") == "general-engineering-contract-rules"

    def test_keeps_name_without_colon(self):
        assert package_base_name("plain-package") == "plain-package"


class TestValidateManifest:
    def test_valid_manifest_passes(self):
        source, _ = _build_source("民法典合同编.txt", b"civil code")
        manifest = _build_manifest(sources=[source])
        assert validate_manifest(manifest) == []

    def test_default_manifest_is_valid(self):
        # 默认 manifest 必须始终通过校验，否则管理员无法 dry-run
        manifest = load_manifest(DEFAULT_MANIFEST_PATH)
        assert validate_manifest(manifest) == []

    def test_missing_rule_package_key(self):
        source, _ = _build_source("a.txt", b"x")
        manifest = _build_manifest(sources=[source])
        manifest.pop("rule_package_key")
        errors = validate_manifest(manifest)
        assert any("rule_package_key" in e for e in errors)

    def test_rule_package_key_must_include_version(self):
        source, _ = _build_source("a.txt", b"x")
        manifest = _build_manifest(rule_package_key="no-version", sources=[source])
        errors = validate_manifest(manifest)
        assert any("版本" in e for e in errors)

    def test_non_contract_scenario_rejected(self):
        source, _ = _build_source("a.txt", b"x")
        manifest = _build_manifest(application_scenario="bidding", sources=[source])
        errors = validate_manifest(manifest)
        assert any("contract" in e for e in errors)

    def test_missing_allowlist_rejected(self):
        source, _ = _build_source("a.txt", b"x")
        manifest = _build_manifest(sources=[source])
        manifest.pop("official_domain_allowlist")
        errors = validate_manifest(manifest)
        assert any("official_domain_allowlist" in e for e in errors)

    def test_empty_allowlist_rejected(self):
        source, _ = _build_source("a.txt", b"x")
        manifest = _build_manifest(allowlist=[], sources=[source])
        errors = validate_manifest(manifest)
        assert any("official_domain_allowlist" in e for e in errors)

    def test_official_url_domain_not_in_allowlist(self):
        source, _ = _build_source(
            "a.txt", b"x", official_url="http://evil.example.com/law.html",
        )
        manifest = _build_manifest(sources=[source])
        errors = validate_manifest(manifest)
        assert any("官方域名白名单" in e for e in errors)

    def test_subdomain_of_allowlisted_domain_accepted(self):
        source, _ = _build_source(
            "a.txt", b"x", official_url="http://www.npc.gov.cn/law.html",
        )
        manifest = _build_manifest(sources=[source])
        assert validate_manifest(manifest) == []

    def test_missing_required_source_field(self):
        source, _ = _build_source("a.txt", b"x")
        source.pop("publish_date")
        manifest = _build_manifest(sources=[source])
        errors = validate_manifest(manifest)
        assert any("publish_date" in e for e in errors)

    def test_invalid_content_hash_format(self):
        source, _ = _build_source("a.txt", b"x", content_hash="md5:abc")
        manifest = _build_manifest(sources=[source])
        errors = validate_manifest(manifest)
        assert any("content_hash" in e for e in errors)

    def test_empty_sources_rejected(self):
        manifest = _build_manifest(sources=[])
        errors = validate_manifest(manifest)
        assert any("sources" in e for e in errors)


class TestImportManifestSource:
    @pytest.mark.asyncio
    async def test_imports_as_system_contract_rule_package(self, tmp_path):
        content = b"civil code third book content"
        source, _ = _build_source("民法典合同编.txt", content)
        manifest = _build_manifest(sources=[source])
        file_path = tmp_path / "民法典合同编.txt"
        file_path.write_bytes(content)

        with patch("scripts.import_default_knowledge.ingest_document_content", new_callable=AsyncMock) as mock_ingest, \
             patch("scripts.import_default_knowledge.save_file"):
            mock_ingest.return_value = (5, None)
            async with async_session() as db:
                result = await import_manifest_source(db, file_path, source, manifest)
                await db.commit()

                doc_id = await db.scalar(
                    select(KnowledgeDocument.id).where(
                        KnowledgeDocument.source_path
                        == f"contract-rules://{DEFAULT_RULE_PACKAGE_KEY}/民法典合同编.txt"
                    )
                )

        assert result["status"] == "success"
        assert result["node_count"] == 5
        assert doc_id is not None

        async with async_session() as db:
            doc = await db.get(KnowledgeDocument, doc_id)
            assert doc.owner_type == "system"
            assert doc.owner_user_id is None
            assert doc.application_scenario == "contract"
            assert doc.rule_package_key == DEFAULT_RULE_PACKAGE_KEY
            assert doc.engineering_type_key == "general-engineering"
            assert doc.contract_type_key == "other"
            assert doc.is_active is True

    @pytest.mark.asyncio
    async def test_duplicate_import_is_idempotent(self, tmp_path):
        content = b"construction law content"
        source, _ = _build_source("建筑法.txt", content)
        manifest = _build_manifest(sources=[source])
        file_path = tmp_path / "建筑法.txt"
        file_path.write_bytes(content)
        source_path = f"contract-rules://{DEFAULT_RULE_PACKAGE_KEY}/建筑法.txt"

        with patch("scripts.import_default_knowledge.ingest_document_content", new_callable=AsyncMock) as mock_ingest, \
             patch("scripts.import_default_knowledge.save_file"):
            mock_ingest.return_value = (3, None)
            async with async_session() as db:
                first = await import_manifest_source(db, file_path, source, manifest)
                await db.commit()
            async with async_session() as db:
                second = await import_manifest_source(db, file_path, source, manifest)
                await db.commit()

            count = await _count_documents_by_source_path(source_path)

        assert first["status"] == "success"
        assert second["status"] == "skipped"
        assert count == 1

    @pytest.mark.asyncio
    async def test_content_hash_mismatch_blocks_import(self, tmp_path):
        content = b"actual content"
        source, _ = _build_source("a.txt", content, content_hash=_sha256_hex(b"different disk content"))
        manifest = _build_manifest(sources=[source])
        file_path = tmp_path / "a.txt"
        file_path.write_bytes(content)
        source_path = f"contract-rules://{DEFAULT_RULE_PACKAGE_KEY}/a.txt"

        with patch("scripts.import_default_knowledge.ingest_document_content", new_callable=AsyncMock), \
             patch("scripts.import_default_knowledge.save_file"):
            async with async_session() as db:
                result = await import_manifest_source(db, file_path, source, manifest)
                await db.commit()

        assert result["status"] == "error"
        assert "content_hash" in result["error"]
        assert await _count_documents_by_source_path(source_path) == 0

    @pytest.mark.asyncio
    async def test_dry_run_does_not_persist(self, tmp_path):
        content = b"safety production law"
        source, _ = _build_source("安全生产法.txt", content)
        manifest = _build_manifest(sources=[source])
        file_path = tmp_path / "安全生产法.txt"
        file_path.write_bytes(content)
        source_path = f"contract-rules://{DEFAULT_RULE_PACKAGE_KEY}/安全生产法.txt"

        with patch("scripts.import_default_knowledge.ingest_document_content", new_callable=AsyncMock), \
             patch("scripts.import_default_knowledge.save_file"):
            async with async_session() as db:
                result = await import_manifest_source(db, file_path, source, manifest, dry_run=True)
                await db.commit()

        assert result["status"] == "dry_run"
        assert await _count_documents_by_source_path(source_path) == 0


class TestDeactivatePreviousRulePackages:
    @pytest.mark.asyncio
    async def test_deactivates_same_package_different_version(self):
        async with async_session() as db:
            sub = EngineeringSubcategory(category_key="general", name="默认法规")
            db.add(sub)
            await db.flush()
            db.add_all([
                KnowledgeDocument(
                    title="旧版 v1",
                    subcategory_id=sub.id,
                    owner_type="system",
                    application_scenario="contract",
                    rule_package_key="general-engineering-contract-rules:v1",
                    is_active=True,
                    source_path="contract-rules://general-engineering-contract-rules:v1/old.txt",
                ),
                KnowledgeDocument(
                    title="更旧 v0",
                    subcategory_id=sub.id,
                    owner_type="system",
                    application_scenario="contract",
                    rule_package_key="general-engineering-contract-rules:v0",
                    is_active=True,
                    source_path="contract-rules://general-engineering-contract-rules:v0/old.txt",
                ),
            ])
            await db.flush()

            count = await deactivate_previous_rule_packages(
                db, "general-engineering-contract-rules:v2"
            )
            await db.commit()

        assert count == 2
        async with async_session() as db:
            v1 = (
                await db.execute(
                    select(KnowledgeDocument).where(
                        KnowledgeDocument.source_path
                        == "contract-rules://general-engineering-contract-rules:v1/old.txt"
                    )
                )
            ).scalar_one_or_none()
            v0 = (
                await db.execute(
                    select(KnowledgeDocument).where(
                        KnowledgeDocument.source_path
                        == "contract-rules://general-engineering-contract-rules:v0/old.txt"
                    )
                )
            ).scalar_one_or_none()
            assert v1 is not None and v1.is_active is False
            assert v0 is not None and v0.is_active is False

    @pytest.mark.asyncio
    async def test_does_not_touch_other_packages_or_user_docs(self):
        async with async_session() as db:
            sub = EngineeringSubcategory(category_key="general", name="默认法规")
            db.add(sub)
            await db.flush()
            other_pkg = KnowledgeDocument(
                title="其他规则包",
                subcategory_id=sub.id,
                owner_type="system",
                application_scenario="contract",
                rule_package_key="specialized-building-rules:v1",
                is_active=True,
                source_path="contract-rules://specialized-building-rules:v1/a.txt",
            )
            user_doc = KnowledgeDocument(
                title="用户合同文档",
                subcategory_id=sub.id,
                owner_type="user",
                application_scenario="contract",
                rule_package_key="general-engineering-contract-rules:v1",
                is_active=True,
                source_path="user://1/a.txt",
            )
            current_pkg = KnowledgeDocument(
                title="当前版本",
                subcategory_id=sub.id,
                owner_type="system",
                application_scenario="contract",
                rule_package_key="general-engineering-contract-rules:v1",
                is_active=True,
                source_path="contract-rules://general-engineering-contract-rules:v1/cur.txt",
            )
            db.add_all([other_pkg, user_doc, current_pkg])
            await db.flush()
            other_id, user_id, current_id = other_pkg.id, user_doc.id, current_pkg.id

            count = await deactivate_previous_rule_packages(
                db, "general-engineering-contract-rules:v1"
            )
            await db.commit()

        assert count == 0
        async with async_session() as db:
            assert (await db.get(KnowledgeDocument, other_id)).is_active is True
            assert (await db.get(KnowledgeDocument, user_id)).is_active is True
            assert (await db.get(KnowledgeDocument, current_id)).is_active is True

    @pytest.mark.asyncio
    async def test_does_not_delete_history_snapshot(self):
        from goulong_auth.models import User

        async with async_session() as db:
            user = User(nickname="snap-user", email="snap@test.local", hashed_password="x")
            db.add(user)
            sub = EngineeringSubcategory(category_key="general", name="默认法规")
            db.add(sub)
            await db.flush()
            record = InspectionRecord(
                user_id=user.id,
                document_name="历史合同.docx",
                document_type="contract",
                document_type_label="合同",
                project_id="default",
                overall_risk="low",
                summary="历史报告",
                issues=[],
                regulation_refs=[],
                parsed_content="",
                status="completed",
                rule_package_key="general-engineering-contract-rules:v1",
                rule_package_keys_snapshot=["general-engineering-contract-rules:v1"],
            )
            db.add(record)
            await db.flush()
            record_id = record.id

            await deactivate_previous_rule_packages(
                db, "general-engineering-contract-rules:v2"
            )
            await db.commit()

        async with async_session() as db:
            restored = await db.get(InspectionRecord, record_id)
            assert restored is not None
            # 历史快照必须保持不变：新版本停用旧版本不影响已落库报告
            assert restored.rule_package_keys_snapshot == ["general-engineering-contract-rules:v1"]
            assert restored.rule_package_key == "general-engineering-contract-rules:v1"


class TestRunImportManifest:
    def test_invalid_manifest_exits(self, tmp_path):
        from scripts.import_default_knowledge import run_import

        bad_manifest = tmp_path / "bad.json"
        bad_manifest.write_text("not json", encoding="utf-8")
        with pytest.raises((SystemExit, json.JSONDecodeError)):
            asyncio.run(run_import(manifest_path=bad_manifest))

    @pytest.mark.asyncio
    async def test_dry_run_generates_only_contract_package(self, tmp_path):
        from scripts.import_default_knowledge import run_import

        content = b"civil code body"
        source, _ = _build_source("民法典合同编.txt", content)
        manifest = _build_manifest(sources=[source])
        manifest_path = tmp_path / "m.json"
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
        ref_dir = tmp_path / "ref"
        ref_dir.mkdir()
        (ref_dir / "民法典合同编.txt").write_bytes(content)

        with patch("scripts.import_default_knowledge.ingest_document_content", new_callable=AsyncMock), \
             patch("scripts.import_default_knowledge.save_file"):
            summary = await run_import(
                reference_dir=ref_dir,
                manifest_path=manifest_path,
                dry_run=True,
            )

        assert summary["dry_run"] is True
        assert summary["total"] == 1
        assert await _count_documents_by_source_path(
            f"contract-rules://{DEFAULT_RULE_PACKAGE_KEY}/民法典合同编.txt"
        ) == 0

    @pytest.mark.asyncio
    async def test_version_switch_deactivates_old_snapshot(self, tmp_path):
        from scripts.import_default_knowledge import run_import

        # 第一轮：导入 v1
        content_v1 = b"v1 body content"
        source_v1, _ = _build_source("民法典合同编.txt", content_v1, title="民法典 v1")
        manifest_v1 = _build_manifest(
            rule_package_key="general-engineering-contract-rules:v1",
            sources=[source_v1],
        )
        manifest_path_v1 = tmp_path / "v1.json"
        manifest_path_v1.write_text(json.dumps(manifest_v1, ensure_ascii=False), encoding="utf-8")
        ref_dir = tmp_path / "ref"
        ref_dir.mkdir()
        (ref_dir / "民法典合同编.txt").write_bytes(content_v1)

        with patch("scripts.import_default_knowledge.ingest_document_content", new_callable=AsyncMock) as mock_ingest, \
             patch("scripts.import_default_knowledge.save_file"):
            mock_ingest.return_value = (2, None)
            await run_import(reference_dir=ref_dir, manifest_path=manifest_path_v1)
            v1_count = await _count_documents_by_source_path(
                "contract-rules://general-engineering-contract-rules:v1/民法典合同编.txt"
            )
            assert v1_count == 1

        # 第二轮：导入 v2，v1 应被停用但保留
        content_v2 = b"v2 body content"
        source_v2, _ = _build_source("民法典合同编.txt", content_v2, title="民法典 v2")
        manifest_v2 = _build_manifest(
            rule_package_key="general-engineering-contract-rules:v2",
            sources=[source_v2],
        )
        manifest_path_v2 = tmp_path / "v2.json"
        manifest_path_v2.write_text(json.dumps(manifest_v2, ensure_ascii=False), encoding="utf-8")
        (ref_dir / "民法典合同编.txt").write_bytes(content_v2)

        with patch("scripts.import_default_knowledge.ingest_document_content", new_callable=AsyncMock) as mock_ingest2, \
             patch("scripts.import_default_knowledge.save_file"):
            mock_ingest2.return_value = (3, None)
            summary = await run_import(reference_dir=ref_dir, manifest_path=manifest_path_v2)

        assert summary["success"] == 1
        assert summary["deactivated"] == 1
        # v1 与 v2 各保留一条记录：v1 停用，v2 激活
        v1_path = "contract-rules://general-engineering-contract-rules:v1/民法典合同编.txt"
        v2_path = "contract-rules://general-engineering-contract-rules:v2/民法典合同编.txt"
        async with async_session() as db:
            v1_doc = (
                await db.execute(
                    select(KnowledgeDocument).where(
                        KnowledgeDocument.source_path == v1_path
                    )
                )
            ).scalar_one_or_none()
            v2_doc = (
                await db.execute(
                    select(KnowledgeDocument).where(
                        KnowledgeDocument.source_path == v2_path
                    )
                )
            ).scalar_one_or_none()
            assert v1_doc is not None and v1_doc.is_active is False
            assert v2_doc is not None and v2_doc.is_active is True


async def _count_documents_by_source_path(source_path: str) -> int:
    """按精确 source_path 计数，避免与其他测试的全局残留互相干扰。"""
    async with async_session() as db:
        rows = (
            await db.execute(
                select(KnowledgeDocument.id).where(
                    KnowledgeDocument.source_path == source_path
                )
            )
        ).scalars().all()
        return len(rows)
