from __future__ import annotations

import asyncio

from sqlalchemy import delete, func, select, text
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
async def test_dry_run_is_read_only() -> None:
    from scripts.backfill_contract_inspection_types import inspect_backfill

    async with async_session() as db:
        sequence_before = (
            await db.execute(text("SELECT last_value, is_called FROM zhaodan.inspection_types_id_seq"))
        ).one()
        before_types = (await db.execute(select(InspectionType))).scalars().all()
        result = await inspect_backfill(db)
        after_types = (await db.execute(select(InspectionType))).scalars().all()
        sequence_after = (
            await db.execute(text("SELECT last_value, is_called FROM zhaodan.inspection_types_id_seq"))
        ).one()

    assert result["system_types_to_insert"] == 9 - len(before_types)
    assert len(after_types) == len(before_types)
    assert sequence_after == sequence_before


@pytest.mark.asyncio
async def test_concurrent_seed_tasks_are_atomic_and_idempotent() -> None:
    await _clear_types()

    async def seed_in_new_session() -> int:
        async with async_session() as db:
            inserted = await seed_system_types(db)
            await db.commit()
            return inserted

    try:
        results = await asyncio.gather(seed_in_new_session(), seed_in_new_session())

        async with async_session() as db:
            rows = (await db.execute(select(InspectionType))).scalars().all()

        assert sum(results) == 9
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


@pytest.mark.asyncio
async def test_real_postgres_flush_failure_rolls_back_all_backfill_writes() -> None:
    await _clear_types()
    async with async_session() as db:
        await seed_system_types(db)
        await db.commit()
        user = User(nickname="rollback-user", email="rollback@test.local", hashed_password="test")
        db.add(user)
        await db.flush()
        subcategory = EngineeringSubcategory(category_key="rollback-task3", name="回滚测试")
        db.add(subcategory)
        await db.flush()
        db.add(
            KnowledgeDocument(
                title="回滚招标资料",
                subcategory_id=subcategory.id,
                owner_type="user",
                owner_user_id=user.id,
                application_scenario="bidding",
                source_path="rollback-bidding",
            )
        )
        db.add(
            InspectionRecord(
                user_id=user.id,
                document_name="回滚合同.docx",
                document_type="contract",
                document_type_label="合同",
                overall_risk="low",
                summary="回滚",
                issues=[],
                regulation_refs=[],
                parsed_content="",
                status="completed",
            )
        )
        await db.commit()
        real_flush = db.flush

        async def flush_then_fail(*args, **kwargs):
            await real_flush(*args, **kwargs)
            raise RuntimeError("注入 flush 失败")

        db.flush = flush_then_fail
        with pytest.raises(RuntimeError, match="注入 flush 失败"):
            await backfill_legacy_data(db)
        await db.rollback()

        async with async_session() as check_db:
            assert (await check_db.scalar(select(func.count(InspectionType.id)))) == 9
            document = await check_db.scalar(select(KnowledgeDocument))
            record = await check_db.scalar(select(InspectionRecord))
        assert document is not None and document.is_active is True
        assert record is not None and record.classification_source is None
    await _clear_types()


@pytest.mark.asyncio
async def test_backfill_only_archives_bidding_and_preserves_private_types_and_contract_docs() -> None:
    try:
        async with async_session() as db:
            first = User(nickname="first-user", email="first@test.local", hashed_password="test")
            second = User(nickname="second-user", email="second@test.local", hashed_password="test")
            db.add_all([first, second])
            await db.flush()
            db.add_all(
                [
                    InspectionType(
                        key="private-first",
                        name="第一用户类别",
                        dimension="engineering",
                        owner_type="user",
                        owner_user_id=first.id,
                    ),
                    InspectionType(
                        key="private-second",
                        name="第二用户类别",
                        dimension="contract",
                        owner_type="user",
                        owner_user_id=second.id,
                    ),
                ]
            )
            subcategory = EngineeringSubcategory(category_key="scenarios-task3", name="场景测试")
            db.add(subcategory)
            await db.flush()
            documents = [
                KnowledgeDocument(
                    title="用户合同",
                    subcategory_id=subcategory.id,
                    owner_type="user",
                    owner_user_id=first.id,
                    application_scenario="contract",
                    source_path="scenario-user-contract",
                ),
                KnowledgeDocument(
                    title="第二用户合同",
                    subcategory_id=subcategory.id,
                    owner_type="user",
                    owner_user_id=second.id,
                    application_scenario="contract",
                    source_path="scenario-second-contract",
                ),
                KnowledgeDocument(
                    title="系统合同",
                    subcategory_id=subcategory.id,
                    owner_type="system",
                    application_scenario="contract",
                    source_path="scenario-system-contract",
                ),
                KnowledgeDocument(
                    title="用户招投标",
                    subcategory_id=subcategory.id,
                    owner_type="user",
                    owner_user_id=first.id,
                    application_scenario="bidding",
                    source_path="scenario-user-bidding",
                ),
                KnowledgeDocument(
                    title="已归档招投标",
                    subcategory_id=subcategory.id,
                    owner_type="user",
                    owner_user_id=first.id,
                    application_scenario="bidding",
                    is_active=False,
                    source_path="scenario-archived-bidding",
                ),
                KnowledgeDocument(
                    title="系统招投标",
                    subcategory_id=subcategory.id,
                    owner_type="system",
                    application_scenario="bidding",
                    source_path="scenario-system-bidding",
                ),
            ]
            db.add_all(documents)
            await db.commit()
            ids = [document.id for document in documents]

            await backfill_legacy_data(db)
            await db.commit()
            await backfill_legacy_data(db)
            await db.commit()

            refreshed = [await db.get(KnowledgeDocument, document_id) for document_id in ids]
            private_types = (await db.execute(select(InspectionType).where(InspectionType.owner_type == "user"))).scalars().all()

        assert [document.is_active for document in refreshed] == [True, True, True, False, False, False]
        assert {(item.key, item.name, item.owner_user_id) for item in private_types} == {
            ("private-first", "第一用户类别", first.id),
            ("private-second", "第二用户类别", second.id),
        }
    finally:
        await _clear_types()
