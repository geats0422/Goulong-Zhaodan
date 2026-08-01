from __future__ import annotations

from sqlalchemy import delete, select
import pytest
from goulong_auth.models import User
from unittest.mock import AsyncMock, patch

from app.core.database import async_session
from app.models import (
    EngineeringSubcategory,
    InspectionRecord,
    InspectionType,
    KnowledgeDocument,
)
from scripts.backfill_contract_inspection_types import (
    DEFAULT_RULE_PACKAGE_KEY,
    CONTRACT_TYPE_PRESETS,
    ENGINEERING_TYPE_PRESETS,
    backfill_legacy_data,
    seed_system_types,
)


async def _clear_types() -> None:
    async with async_session() as db:
        await db.execute(delete(InspectionType))
        await db.commit()


@pytest.mark.asyncio
async def test_empty_database_seeds_stable_system_presets_idempotently() -> None:
    try:
        async with async_session() as db:
            await seed_system_types(db)
            await db.commit()
            await seed_system_types(db)
            await db.commit()

            rows = (await db.execute(select(InspectionType))).scalars().all()

        assert {(row.dimension, row.key, row.name) for row in rows} == {
            (dimension, key, name)
            for dimension, presets in (
                ("engineering", ENGINEERING_TYPE_PRESETS),
                ("contract", CONTRACT_TYPE_PRESETS),
            )
            for key, name in presets
        }
        assert len(rows) == 9
    finally:
        await _clear_types()


@pytest.mark.asyncio
async def test_seed_does_not_overwrite_existing_system_name() -> None:
    try:
        async with async_session() as db:
            db.add(
                InspectionType(
                    key="municipal-road",
                    name="既有系统名称",
                    dimension="engineering",
                    owner_type="system",
                    enabled=False,
                )
            )
            await db.commit()
            await seed_system_types(db)
            await db.commit()
            row = await db.scalar(
                select(InspectionType).where(
                    InspectionType.owner_type == "system",
                    InspectionType.key == "municipal-road",
                )
            )

        assert row is not None
        assert row.name == "既有系统名称"
        assert row.enabled is False
    finally:
        await _clear_types()


@pytest.mark.asyncio
async def test_backfill_is_idempotent_and_archives_without_deleting_history() -> None:
    async with async_session() as db:
        user = User(
            nickname="task3-user",
            email="task3-user@test.local",
            hashed_password="test",
        )
        db.add(user)
        await db.flush()
        subcategory = EngineeringSubcategory(category_key="legacy-task3", name="任务3测试")
        db.add(subcategory)
        await db.flush()
        contract_doc = KnowledgeDocument(
            title="历史合同",
            subcategory_id=subcategory.id,
            owner_type="user",
            application_scenario="contract",
            source_path="task3-contract",
        )
        bidding_doc = KnowledgeDocument(
            title="历史招标资料",
            subcategory_id=subcategory.id,
            owner_type="user",
            application_scenario="bidding",
            source_path="task3-bidding",
        )
        db.add_all([contract_doc, bidding_doc])
        record_contract = InspectionRecord(
            user_id=user.id,
            document_name="历史合同.docx",
            document_type="contract",
            document_type_label="合同",
            overall_risk="low",
            summary="历史",
            issues=[],
            regulation_refs=[],
            parsed_content="",
            status="completed",
        )
        record_bidding = InspectionRecord(
            user_id=user.id,
            document_name="历史招标.docx",
            document_type="bidding",
            document_type_label="招投标文件",
            overall_risk="low",
            summary="历史",
            issues=[],
            regulation_refs=[],
            parsed_content="",
            status="completed",
        )
        db.add_all([record_contract, record_bidding])
        await db.commit()
        contract_id, bidding_id = record_contract.id, record_bidding.id
        contract_doc_id, bidding_doc_id = contract_doc.id, bidding_doc.id

        await backfill_legacy_data(db)
        await db.commit()
        await backfill_legacy_data(db)
        await db.commit()

        contract = await db.get(InspectionRecord, contract_id)
        bidding = await db.get(InspectionRecord, bidding_id)
        contract_doc = await db.get(KnowledgeDocument, contract_doc_id)
        bidding_doc = await db.get(KnowledgeDocument, bidding_doc_id)

        assert contract is not None and bidding is not None
        assert contract.final_engineering_type == "general-engineering"
        assert contract.final_contract_type == "other"
        assert contract.engineering_type_snapshot == "通用工程"
        assert contract.contract_type_snapshot == "其他类"
        assert contract.classification_source == "legacy"
        assert contract.rule_package_key == DEFAULT_RULE_PACKAGE_KEY
        assert bidding.classification_source == "archived_legacy"
        assert bidding.final_engineering_type is None
        assert contract_doc is not None and contract_doc.is_active is True
        assert bidding_doc is not None and bidding_doc.is_active is False


@pytest.mark.asyncio
async def test_backfill_rolls_back_when_a_write_fails() -> None:
    from scripts import backfill_contract_inspection_types as module

    class SessionContext:
        def __init__(self) -> None:
            self.session = AsyncMock()

        async def __aenter__(self):
            return self.session

        async def __aexit__(self, *_args):
            return False

    context = SessionContext()
    with (
        patch("app.core.database.async_session", return_value=context),
        patch.object(module, "backfill_legacy_data", side_effect=RuntimeError("写入失败")),
    ):
        with pytest.raises(RuntimeError, match="写入失败"):
            await module.run_backfill()

    context.session.rollback.assert_awaited_once()
    context.session.commit.assert_not_awaited()
