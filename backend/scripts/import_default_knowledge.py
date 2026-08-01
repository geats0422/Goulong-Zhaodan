from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import logging
import sys
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import ALLOWED_FILE_EXTENSIONS
from app.models.knowledge import (
    DocumentVersion,
    EngineeringSubcategory,
    KnowledgeDocument,
)
from app.services.file_storage import build_storage_path, save_file, safe_path_segment
from app.services.knowledge_ingestion import ingest_document_content

logger = logging.getLogger(__name__)

DEFAULT_MANIFEST_PATH = Path(__file__).resolve().parent / "default_contract_rules_manifest.json"
DEFAULT_RULE_PACKAGE_KEY = "general-engineering-contract-rules:v1"

CONTRACT_KEYWORDS = ("合同", "民法典合同编", "合同通则")
BIDDING_KEYWORDS = (
    "招标", "投标", "招投标", "评标", "政府采购",
    "质疑", "投诉", "公示", "公平竞争", "特许经营",
)

_REQUIRED_SOURCE_FIELDS = (
    "title",
    "official_url",
    "publish_date",
    "effective_date",
    "version",
    "content_hash",
    "filename",
)
_SHA256_PATTERN = "sha256:"


def classify_filename(filename: str) -> str:
    for kw in CONTRACT_KEYWORDS:
        if kw in filename:
            return "contract"
    for kw in BIDDING_KEYWORDS:
        if kw in filename:
            return "bidding"
    # 兜底分类已从 bidding 改为合同规则包导入：照胆只做合同初审。
    logger.warning("无法判断分类，使用合同规则包兜底: %s", filename)
    return "contract"


# ---------------------------------------------------------------------------
# manifest 加载与校验（任务 10：官方默认合同规则包）
# ---------------------------------------------------------------------------


def load_manifest(path: Path) -> dict:
    """读取 manifest JSON。文件不存在或格式错误时抛出异常。"""
    if not path.exists():
        raise FileNotFoundError(f"manifest 文件不存在: {path}")
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def package_base_name(rule_package_key: str) -> str:
    """general-engineering-contract-rules:v1 → general-engineering-contract-rules。"""
    return rule_package_key.split(":", 1)[0]


def _domain_in_allowlist(url: str, allowlist: list[str]) -> bool:
    netloc = urlparse(url).netloc.lower()
    if not netloc:
        return False
    host = netloc.split("@")[-1].split(":")[0]
    for allowed in allowlist:
        normalized = (allowed or "").lower()
        if not normalized:
            continue
        if host == normalized or host.endswith("." + normalized):
            return True
    return False


def _is_sha256_hex(value: str) -> bool:
    if not value.startswith(_SHA256_PATTERN):
        return False
    digest = value[len(_SHA256_PATTERN):]
    if len(digest) != 64:
        return False
    return all(ch in "0123456789abcdef" for ch in digest.lower())


def validate_manifest(manifest: dict) -> list[str]:
    """校验 manifest 结构、官方域名白名单和来源元数据，返回错误信息列表。"""
    errors: list[str] = []
    if not isinstance(manifest, dict):
        return ["manifest 必须是 JSON 对象"]

    rule_package_key = manifest.get("rule_package_key")
    if not rule_package_key or not isinstance(rule_package_key, str):
        errors.append("rule_package_key 缺失")
    elif ":" not in rule_package_key:
        errors.append("rule_package_key 缺少版本号（应为 name:version 格式）")

    if manifest.get("application_scenario") != "contract":
        errors.append("application_scenario 必须为 contract（合同初审场景）")

    allowlist = manifest.get("official_domain_allowlist")
    if not isinstance(allowlist, list) or not allowlist:
        errors.append("official_domain_allowlist 缺失或为空")
    elif not all(isinstance(d, str) and d.strip() for d in allowlist):
        errors.append("official_domain_allowlist 必须为非空字符串列表")

    sources = manifest.get("sources")
    if not isinstance(sources, list) or not sources:
        errors.append("sources 缺失或为空")
        return errors

    allowlist_strs = allowlist if isinstance(allowlist, list) else []
    for idx, source in enumerate(sources):
        prefix = f"sources[{idx}]"
        if not isinstance(source, dict):
            errors.append(f"{prefix} 必须是 JSON 对象")
            continue
        for field in _REQUIRED_SOURCE_FIELDS:
            value = source.get(field)
            if not value or not isinstance(value, str):
                errors.append(f"{prefix} 缺少必填字段: {field}")
        url = source.get("official_url")
        if (
            isinstance(url, str)
            and url
            and allowlist_strs
            and not _domain_in_allowlist(url, allowlist_strs)
        ):
            errors.append(f"{prefix} official_url 域名不在官方域名白名单: {url}")
        content_hash = source.get("content_hash")
        if isinstance(content_hash, str) and content_hash and not _is_sha256_hex(content_hash):
            errors.append(f"{prefix} content_hash 必须为 sha256:+64位16进制")

    return errors


def _manifest_source_path(rule_package_key: str, filename: str) -> str:
    """稳定的业务标识，用于幂等判断。文件名不参与文件系统路径。"""
    return f"contract-rules://{rule_package_key}/{filename}"


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
        original_storage_path = f"{storage_dir}/{safe_name}"

        version = DocumentVersion(
            document_id=document.id,
            version_number=1,
            display_name=file_path.name,
            original_file_path=original_storage_path,
            status="pending",
            file_size_bytes=file_size,
            file_type=ext,
        )
        db.add(version)
        await db.flush()
        await db.refresh(version)

        save_file(original_storage_path, content)

        node_count, error_msg = await ingest_document_content(
            db, document, version, original_storage_path, safe_stem, original_content=content,
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


# ---------------------------------------------------------------------------
# 任务 10：manifest 模式导入官方默认合同规则包
# ---------------------------------------------------------------------------


async def _get_or_create_subcategory(
    db: AsyncSession, *, category_key: str, name: str,
) -> EngineeringSubcategory:
    result = await db.execute(
        select(EngineeringSubcategory).where(
            EngineeringSubcategory.category_key == category_key,
            EngineeringSubcategory.name == name,
        )
    )
    sub = result.scalar_one_or_none()
    if sub is not None:
        return sub
    sub = EngineeringSubcategory(category_key=category_key, name=name)
    db.add(sub)
    await db.flush()
    await db.refresh(sub)
    return sub


def _sha256_of(content: bytes) -> str:
    return _SHA256_PATTERN + hashlib.sha256(content).hexdigest()


async def import_manifest_source(
    db: AsyncSession,
    file_path: Path,
    source: dict,
    manifest: dict,
    *,
    dry_run: bool = False,
) -> dict:
    """导入 manifest 单个来源到系统默认合同规则包。

    幂等：相同 rule_package_key + filename 的来源只导入一次。
    新版本（rule_package_key 不同）由 deactivate_previous_rule_packages 处理。
    """
    rule_package_key = manifest["rule_package_key"]
    scenario = manifest.get("application_scenario", "contract")
    engineering_type_key = manifest.get("engineering_type_key")
    contract_type_key = manifest.get("contract_type_key")
    filename = source["filename"]
    source_path = _manifest_source_path(rule_package_key, filename)

    result_data: dict = {
        "filename": filename,
        "title": source.get("title", filename),
        "rule_package_key": rule_package_key,
        "status": "pending",
        "node_count": 0,
        "error": None,
    }

    try:
        existing = await db.execute(
            select(KnowledgeDocument).where(
                KnowledgeDocument.source_path == source_path,
            )
        )
        if existing.scalar_one_or_none() is not None:
            result_data["status"] = "skipped"
            return result_data

        if dry_run:
            result_data["status"] = "dry_run"
            return result_data

        content = file_path.read_bytes()
        expected_hash = source.get("content_hash")
        if isinstance(expected_hash, str) and expected_hash:
            actual_hash = _sha256_of(content)
            if actual_hash != expected_hash:
                result_data["status"] = "error"
                result_data["error"] = (
                    f"content_hash 不匹配（期望 {expected_hash}，实际 {actual_hash}）"
                )
                return result_data

        sub = await _get_or_create_subcategory(
            db,
            category_key=manifest.get("subcategory_category_key", "general"),
            name=manifest.get("subcategory_name", "默认法规"),
        )

        stem = Path(filename).stem.strip() or "untitled"
        safe_stem = _safe_path_segment(stem)
        ext = Path(filename).suffix.lower() or ".txt"

        document = KnowledgeDocument(
            title=source.get("title") or stem,
            subcategory_id=sub.id,
            owner_type="system",
            owner_user_id=None,
            application_scenario=scenario,
            engineering_type_key=engineering_type_key,
            contract_type_key=contract_type_key,
            rule_package_key=rule_package_key,
            is_active=True,
            source_path=source_path,
        )
        db.add(document)
        await db.flush()
        await db.refresh(document)

        storage_dir = build_storage_path(
            manifest.get("subcategory_category_key", "general"),
            _safe_path_segment(sub.name),
            safe_stem,
            1,
        )
        safe_name = _safe_path_segment(filename)
        original_storage_path = f"{storage_dir}/{safe_name}"

        version = DocumentVersion(
            document_id=document.id,
            version_number=1,
            display_name=filename,
            original_file_path=original_storage_path,
            status="pending",
            file_size_bytes=len(content),
            file_type=ext,
        )
        db.add(version)
        await db.flush()
        await db.refresh(version)

        save_file(original_storage_path, content)

        node_count, error_msg = await ingest_document_content(
            db, document, version, original_storage_path, safe_stem, original_content=content,
        )
        document.current_version_id = version.id
        await db.flush()

        result_data["status"] = "success"
        result_data["node_count"] = node_count
        result_data["error"] = error_msg
    except Exception as exc:
        await db.rollback()
        result_data["status"] = "error"
        result_data["error"] = str(exc)
        logger.exception("导入 manifest 来源失败: %s", filename)

    return result_data


async def deactivate_previous_rule_packages(
    db: AsyncSession, active_rule_package_key: str, *, dry_run: bool = False,
) -> int:
    """停用同包名、不同版本的系统合同规则文档，保留历史记录与索引快照。"""
    base_name = package_base_name(active_rule_package_key)
    stmt = select(KnowledgeDocument).where(
        KnowledgeDocument.owner_type == "system",
        KnowledgeDocument.application_scenario == "contract",
        KnowledgeDocument.is_active.is_(True),
        KnowledgeDocument.rule_package_key.is_not(None),
        KnowledgeDocument.rule_package_key != active_rule_package_key,
    )
    rows = (await db.execute(stmt)).scalars().all()
    count = 0
    for doc in rows:
        if package_base_name(doc.rule_package_key or "") == base_name:
            count += 1
            if not dry_run:
                doc.is_active = False
    if not dry_run and count:
        await db.flush()
    return count


async def run_manifest_import(
    reference_dir: Path | None = None,
    manifest_path: Path | None = None,
    *,
    dry_run: bool = False,
) -> dict:
    """manifest 模式：导入官方默认合同规则包。

    法规文件不入 Git，由管理员准备到 reference_dir；manifest 维护官方 URL、
    发布日期、施行日期、版本和 content_hash。新版本导入时停用旧版本，
    但不删除历史文档、版本、索引或报告快照。
    """
    if manifest_path is None:
        manifest_path = DEFAULT_MANIFEST_PATH
    if reference_dir is None:
        project_root = Path(__file__).resolve().parent.parent.parent
        reference_dir = project_root / "knowledge-base" / "system" / "legal-regulations"

    manifest = load_manifest(manifest_path)
    errors = validate_manifest(manifest)
    if errors:
        print(f"错误：manifest 校验失败: {manifest_path}", file=sys.stderr)
        for err in errors:
            print(f"  - {err}", file=sys.stderr)
        raise SystemExit(1)

    sources = manifest.get("sources", [])
    rule_package_key = manifest["rule_package_key"]
    summary: dict = {
        "rule_package_key": rule_package_key,
        "total": len(sources),
        "success": 0,
        "skipped": 0,
        "failed": 0,
        "deactivated": 0,
        "dry_run": dry_run,
    }

    if not sources:
        print("manifest 无可导入来源")
        return summary

    from app.core.database import async_session

    print(
        f"[{'dry-run' if dry_run else '导入'}] 规则包 {rule_package_key}, "
        f"来源 {len(sources)} 个"
    )

    if dry_run:
        for src in sources:
            print(f"  - {src['filename']}: {src.get('title', '')}")
        try:
            async with async_session() as db:
                summary["deactivated"] = await deactivate_previous_rule_packages(
                    db, rule_package_key, dry_run=True,
                )
            print(f"[dry-run] 将停用旧版本文档: {summary['deactivated']}")
        except Exception as exc:
            # 数据库不可用或 schema 未就绪时，dry-run 仍提供 manifest 预览。
            logger.warning("dry-run 无法统计旧版本文档: %s", type(exc).__name__)
            print("[dry-run] 旧版本停用数量: 数据库不可用，已跳过")
        return summary

    async with async_session() as db:
        try:
            summary["deactivated"] = await deactivate_previous_rule_packages(
                db, rule_package_key,
            )
            await db.flush()

            for src in sources:
                filename = src["filename"]
                file_path = reference_dir / filename
                if not file_path.exists():
                    summary["failed"] += 1
                    print(f"  [FAIL] {filename} 本地文件不存在: {file_path}")
                    continue
                result = await import_manifest_source(db, file_path, src, manifest)
                status = result["status"]
                if status == "success":
                    summary["success"] += 1
                    print(
                        f"  [OK] {result['filename']} "
                        f"(规则包: {rule_package_key}, 节点: {result['node_count']})"
                    )
                elif status == "skipped":
                    summary["skipped"] += 1
                    print(f"  - {result['filename']} (已存在，跳过)")
                else:
                    summary["failed"] += 1
                    print(f"  [FAIL] {result['filename']} 错误: {result['error']}")

            await db.commit()
        except Exception:
            await db.rollback()
            logger.exception("manifest 导入失败")
            raise

    print(
        f"\n导入完成: 总计 {summary['total']}, 成功 {summary['success']}, "
        f"跳过 {summary['skipped']}, 失败 {summary['failed']}, "
        f"停用旧版本 {summary['deactivated']}"
    )
    return summary


async def run_import(
    reference_dir: Path | None = None,
    manifest_path: Path | None = None,
    *,
    dry_run: bool = False,
) -> dict:
    """导入入口。

    - 传入 manifest_path（或省略以使用默认 manifest）：走 manifest 模式，导入合同规则包。
    - 传入 reference_dir 且 manifest_path 显式为 None 的旧行为由 scan 模式保留；
      但默认 main() 始终走 manifest 模式。
    """
    if manifest_path is not None or reference_dir is None:
        return await run_manifest_import(
            reference_dir=reference_dir,
            manifest_path=manifest_path or DEFAULT_MANIFEST_PATH,
            dry_run=dry_run,
        )

    # 向后兼容：显式只传 reference_dir 时使用旧的目录扫描模式。
    if not reference_dir.exists():
        print(f"错误：参考目录不存在: {reference_dir}", file=sys.stderr)
        raise SystemExit(1)

    from app.core.database import async_session

    files = scan_reference_dir(reference_dir)
    if not files:
        print("未找到可导入的文件")
        return {"total": 0, "success": 0, "skipped": 0, "failed": 0}

    print(f"找到 {len(files)} 个文件待导入（扫描模式）")

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
        help="参考文件目录路径（默认: knowledge-base/system/legal-regulations）",
    )
    parser.add_argument(
        "--manifest",
        type=str,
        default=str(DEFAULT_MANIFEST_PATH),
        help="官方合同规则包 manifest 路径（默认使用脚本同目录的 default_contract_rules_manifest.json）",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="只读校验 manifest 并预览计划，不写入数据库或文件",
    )
    parser.add_argument(
        "--scan",
        action="store_true",
        help="使用旧的目录扫描模式（不推荐：默认走 manifest 合同规则包导入）",
    )
    args = parser.parse_args()

    ref_dir = Path(args.reference_dir) if args.reference_dir else None

    if args.scan:
        asyncio.run(run_import(ref_dir))
        return

    manifest_path = Path(args.manifest) if args.manifest else None
    asyncio.run(run_import(ref_dir, manifest_path, dry_run=args.dry_run))


if __name__ == "__main__":
    main()
