from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select, update
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
    """插入系统预设；只按稳定 key 判断，绝不覆盖已有记录。"""
    inserted = 0
    for dimension, presets in (
        ("engineering", ENGINEERING_TYPE_PRESETS),
        ("contract", CONTRACT_TYPE_PRESETS),
    ):
        for key, name in presets:
            exists = await db.scalar(
                select(InspectionType.id).where(
                    InspectionType.dimension == dimension,
                    InspectionType.key == key,
                    InspectionType.owner_type == "system",
                )
            )
            if exists is not None:
                continue
            db.add(
                InspectionType(
                    key=key,
                    name=name,
                    dimension=dimension,
                    owner_type="system",
                    owner_user_id=None,
                    enabled=True,
                )
            )
            inserted += 1
    await db.flush()
    return inserted


async def backfill_legacy_data(db: AsyncSession) -> dict[str, int]:
    """幂等回填历史记录，并将旧招投标资料隐藏但不删除。"""
    await seed_system_types(db)

    archived_documents = await db.execute(
        update(KnowledgeDocument)
        .where(KnowledgeDocument.application_scenario == "bidding")
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


async def run_backfill(*, commit: bool = True) -> dict[str, int]:
    from app.core.database import async_session

    async with async_session() as db:
        try:
            result = await backfill_legacy_data(db)
            if commit:
                await db.commit()
            else:
                await db.rollback()
            return result
        except Exception:
            await db.rollback()
            logger.exception("合同初审类型存量回填失败")
            raise


def main() -> None:
    parser = argparse.ArgumentParser(description="幂等回填合同初审类型和历史资料")
    parser.add_argument("--dry-run", action="store_true", help="只验证数据库连接，不提交变更")
    args = parser.parse_args()

    if args.dry_run:
        print(asyncio.run(run_backfill(commit=False)))
        return
    print(asyncio.run(run_backfill()))


if __name__ == "__main__":
    main()
