from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import func, select, text, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import InspectionRecord, InspectionType, KnowledgeDocument

logger = logging.getLogger(__name__)

ENGINEERING_TYPE_PRESETS = (
    ("building-construction", "房建施工"),
    ("municipal-road", "市政道路"),
    ("decoration", "装饰装修"),
    ("mechanical-electrical", "机电安装"),
    ("steel-structure", "钢结构"),
    ("general-engineering", "通用工程"),
)
CONTRACT_TYPE_PRESETS = (
    ("labor-subcontract", "劳务分包"),
    ("professional-subcontract", "专业工程分包"),
    ("other", "其他类"),
)
DEFAULT_RULE_PACKAGE_KEY = "general-engineering-contract-rules:v1"


async def seed_system_types(db: AsyncSession) -> int:
    """使用 PostgreSQL 原子 upsert 插入预设，不覆盖已有系统记录。"""
    inserted = 0
    for dimension, presets in (
        ("engineering", ENGINEERING_TYPE_PRESETS),
        ("contract", CONTRACT_TYPE_PRESETS),
    ):
        for key, name in presets:
            statement = (
                pg_insert(InspectionType)
                .values(
                    key=key,
                    name=name,
                    dimension=dimension,
                    owner_type="system",
                    owner_user_id=None,
                    enabled=True,
                )
                .on_conflict_do_nothing(
                    index_elements=[InspectionType.dimension, InspectionType.key],
                    index_where=text("owner_type = 'system'"),
                )
            )
            result = await db.execute(statement)
            inserted += result.rowcount or 0
    return inserted


async def inspect_backfill(db: AsyncSession) -> dict[str, int]:
    """只读计算回填计划，不执行写入、flush 或更新。"""
    with db.no_autoflush:
        existing_keys = {
            (dimension, key)
            for dimension, key in (
                await db.execute(
                    select(InspectionType.dimension, InspectionType.key).where(
                        InspectionType.owner_type == "system"
                    )
                )
            ).all()
        }
        expected_keys = {
            (dimension, key)
            for dimension, presets in (
                ("engineering", ENGINEERING_TYPE_PRESETS),
                ("contract", CONTRACT_TYPE_PRESETS),
            )
            for key, _name in presets
        }
        archived_documents = await db.scalar(
            select(func.count(KnowledgeDocument.id)).where(
                KnowledgeDocument.application_scenario == "bidding",
                KnowledgeDocument.is_active.is_(True),
            )
        )
        legacy_records = await db.execute(
            select(InspectionRecord.document_type, func.count(InspectionRecord.id))
            .where(
                InspectionRecord.document_type.in_(('contract', 'bidding')),
                InspectionRecord.classification_source.is_(None),
            )
            .group_by(InspectionRecord.document_type)
        )
    record_counts: dict[str, int] = {row[0]: row[1] for row in legacy_records.all()}
    return {
        "system_types_existing": len(existing_keys & expected_keys),
        "system_types_to_insert": len(expected_keys - existing_keys),
        "archived_documents": archived_documents or 0,
        "contract_records": record_counts.get("contract", 0),
        "bidding_records": record_counts.get("bidding", 0),
    }


async def backfill_legacy_data(db: AsyncSession) -> dict[str, int]:
    """幂等回填历史记录，并将旧招投标资料隐藏但不删除。"""
    await seed_system_types(db)

    archived_documents = await db.execute(
        update(KnowledgeDocument)
        .where(
            KnowledgeDocument.application_scenario == "bidding",
            KnowledgeDocument.is_active.is_(True),
        )
        .values(is_active=False)
    )

    records = (
        await db.execute(
            select(InspectionRecord).where(
                InspectionRecord.document_type.in_(("contract", "bidding")),
                InspectionRecord.classification_source.is_(None),
            )
        )
    ).scalars()
    contract_count = 0
    bidding_count = 0
    for record in records:
        if record.document_type == "contract":
            record.detected_engineering_type = record.detected_engineering_type or "general-engineering"
            record.final_engineering_type = record.final_engineering_type or "general-engineering"
            record.detected_contract_type = record.detected_contract_type or "other"
            record.final_contract_type = record.final_contract_type or "other"
            record.engineering_type_snapshot = record.engineering_type_snapshot or "通用工程"
            record.contract_type_snapshot = record.contract_type_snapshot or "其他类"
            record.rule_package_key = record.rule_package_key or DEFAULT_RULE_PACKAGE_KEY
            record.classification_source = "legacy"
            contract_count += 1
        else:
            record.classification_source = "archived_legacy"
            bidding_count += 1

    await db.flush()
    return {
        "archived_documents": archived_documents.rowcount or 0,
        "contract_records": contract_count,
        "bidding_records": bidding_count,
    }


async def run_backfill(*, dry_run: bool = False) -> dict[str, int]:
    from app.core.database import async_session

    async with async_session() as db:
        try:
            if dry_run:
                return await inspect_backfill(db)
            result = await backfill_legacy_data(db)
            await db.commit()
            return result
        except Exception:
            await db.rollback()
            logger.exception("合同初审类型存量回填失败")
            raise


def main() -> None:
    parser = argparse.ArgumentParser(description="幂等回填合同初审类型和历史资料")
    parser.add_argument("--dry-run", action="store_true", help="只读统计待插入、归档和回填数量，不执行任何写入")
    args = parser.parse_args()

    if args.dry_run:
        print(asyncio.run(run_backfill(dry_run=True)))
        return
    print(asyncio.run(run_backfill()))


if __name__ == "__main__":
    main()
