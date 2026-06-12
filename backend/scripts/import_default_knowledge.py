from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import ALLOWED_FILE_EXTENSIONS
from app.models.knowledge import (
    DocumentVersion,
    EngineeringSubcategory,
    KnowledgeDocument,
)
from app.services.file_storage import build_storage_path, save_upload_file, safe_path_segment
from app.services.knowledge_ingestion import ingest_document_content

logger = logging.getLogger(__name__)

CONTRACT_KEYWORDS = ("合同", "民法典合同编", "合同通则")
BIDDING_KEYWORDS = (
    "招标", "投标", "招投标", "评标", "政府采购",
    "质疑", "投诉", "公示", "公平竞争", "特许经营",
)


def classify_filename(filename: str) -> str:
    for kw in CONTRACT_KEYWORDS:
        if kw in filename:
            return "contract"
    for kw in BIDDING_KEYWORDS:
        if kw in filename:
            return "bidding"
    logger.warning("无法判断分类，使用兜底分类 bidding: %s", filename)
    return "bidding"


def scan_reference_dir(reference_dir: Path) -> list[tuple[Path, str]]:
    if not reference_dir.exists() or not reference_dir.is_dir():
        logger.error("参考目录不存在或不是目录: %s", reference_dir)
        return []
    results: list[tuple[Path, str]] = []
    for item in sorted(reference_dir.iterdir()):
        if not item.is_file():
            continue
        ext = item.suffix.lower()
        if ext not in ALLOWED_FILE_EXTENSIONS:
            logger.debug("跳过不支持的文件类型: %s", item.name)
            continue
        scenario = classify_filename(item.name)
        results.append((item, scenario))
    return results


async def _get_or_create_default_subcategory(db) -> EngineeringSubcategory:
    result = await db.execute(
        select(EngineeringSubcategory).where(
            EngineeringSubcategory.category_key == "traditional",
            EngineeringSubcategory.name == "默认法规",
        )
    )
    sub = result.scalar_one_or_none()
    if sub is not None:
        return sub
    sub = EngineeringSubcategory(category_key="traditional", name="默认法规")
    db.add(sub)
    await db.flush()
    await db.refresh(sub)
    return sub


def _safe_path_segment(text: str) -> str:
    return safe_path_segment(text)


async def import_single_file(db: AsyncSession, file_path: Path, application_scenario: str) -> dict:
    source_path_str = str(file_path)
    result_data: dict = {
        "filename": file_path.name,
        "status": "pending",
        "node_count": 0,
        "error": None,
    }

    try:
        existing = await db.execute(
            select(KnowledgeDocument).where(
                KnowledgeDocument.source_path == source_path_str,
            )
        )
        if existing.scalar_one_or_none() is not None:
            result_data["status"] = "skipped"
            return result_data

        sub = await _get_or_create_default_subcategory(db)

        stem = file_path.stem.strip() or "untitled"
        safe_stem = _safe_path_segment(stem)
        ext = file_path.suffix.lower()

        document = KnowledgeDocument(
            title=stem,
            subcategory_id=sub.id,
            owner_type="system",
            owner_user_id=None,
            application_scenario=application_scenario,
            source_path=source_path_str,
        )
        db.add(document)
        await db.flush()
        await db.refresh(document)

        content = file_path.read_bytes()
        file_size = len(content)

        storage_dir = build_storage_path(
            "traditional", _safe_path_segment(sub.name), safe_stem, 1,
        )
        safe_name = _safe_path_segment(file_path.name)
        original_path = storage_dir / safe_name

        version = DocumentVersion(
            document_id=document.id,
            version_number=1,
            display_name=file_path.name,
            original_file_path=str(original_path),
            status="pending",
            file_size_bytes=file_size,
            file_type=ext,
        )
        db.add(version)
        await db.flush()
        await db.refresh(version)

        save_upload_file(original_path, content)

        node_count, error_msg = await ingest_document_content(
            db, document, version, str(original_path), safe_stem,
        )
        await db.flush()

        result_data["status"] = "success"
        result_data["node_count"] = node_count
        result_data["error"] = error_msg
    except Exception as exc:
        await db.rollback()
        result_data["status"] = "error"
        result_data["error"] = str(exc)
        logger.exception("导入文件失败: %s", file_path.name)

    return result_data


async def run_import(reference_dir: Path | None = None) -> dict:
    if reference_dir is None:
        project_root = Path(__file__).resolve().parent.parent.parent
        reference_dir = project_root / "reference" / "招投标法律法规（新）-用于照胆"

    if not reference_dir.exists():
        print(f"错误：参考目录不存在: {reference_dir}", file=sys.stderr)
        raise SystemExit(1)

    from app.core.database import async_session

    files = scan_reference_dir(reference_dir)
    if not files:
        print("未找到可导入的文件")
        return {"total": 0, "success": 0, "skipped": 0, "failed": 0}

    print(f"找到 {len(files)} 个文件待导入")

    summary = {"total": len(files), "success": 0, "skipped": 0, "failed": 0}

    async with async_session() as db:
        for file_path, scenario in files:
            result = await import_single_file(db, file_path, scenario)
            if result["status"] == "success":
                summary["success"] += 1
                print(f"  [OK] {result['filename']} (场景: {scenario}, 节点: {result['node_count']})")
                try:
                    await db.commit()
                except Exception:
                    await db.rollback()
                    summary["success"] -= 1
                    summary["failed"] += 1
                    print(f"  [FAIL] {result['filename']} 提交失败")
            elif result["status"] == "skipped":
                summary["skipped"] += 1
                print(f"  - {result['filename']} (已存在，跳过)")
            else:
                summary["failed"] += 1
                print(f"  [FAIL] {result['filename']} 错误: {result['error']}")

    print(f"\n导入完成: 总计 {summary['total']}, 成功 {summary['success']}, "
          f"跳过 {summary['skipped']}, 失败 {summary['failed']}")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="导入默认知识库法规文件")
    parser.add_argument(
        "--reference-dir",
        type=str,
        default=None,
        help="参考文件目录路径（默认: reference/招投标法律法规（新）-用于照胆）",
    )
    args = parser.parse_args()

    ref_dir = Path(args.reference_dir) if args.reference_dir else None
    asyncio.run(run_import(ref_dir))


if __name__ == "__main__":
    main()
