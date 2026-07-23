from __future__ import annotations

import asyncio
import datetime
import hashlib
import os
import uuid
from unittest.mock import AsyncMock, Mock

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import database as db_mod
from app.core import config
from app.core.data_encryption import encrypt_sensitive_artifact
from app.core.database import async_session
from app.models.document_job import DocumentProcessingJob
from app.services.document_job_service import (
    DocumentJobOwnershipError,
    InvalidDocumentJobTransitionError,
    InvalidStorageIdentifierError,
    cancel_document_job,
    claim_document_job_lease,
    create_document_job,
    heartbeat_document_job_lease,
    mark_document_job_failed,
    mark_document_job_succeeded,
    prepare_markdown_artifact,
    prepare_source_artifact,
    persist_document_job_inspection_state,
    release_document_job_lease,
    retry_document_job,
    sanitize_document_job_error,
    update_document_job_stage,
    validate_document_job_transition,
    validate_reusable_markdown,
    validate_storage_identifier,
    _mark_document_job_succeeded_cas,
)
from goulong_auth.models import User


SOURCE = b"source bytes"
SOURCE_HASH = hashlib.sha256(SOURCE).hexdigest()
MARKDOWN = ("# 有效文档\n\n" + "这是有效的 Markdown 正文。" * 20).encode()
MARKDOWN_HASH = hashlib.sha256(MARKDOWN).hexdigest()


def _source_path(user_id: uuid.UUID) -> str:
    return f"users/{user_id}/documents/source.pdf"


def _markdown_path(user_id: uuid.UUID) -> str:
    return f"users/{user_id}/documents/source.md"


async def _chunks(content: bytes):
    for offset in range(0, len(content), 5):
        yield content[offset : offset + 5]


@pytest.mark.parametrize(
    "value",
    ["/tmp/a.pdf", "C:/a.pdf", "../a.pdf", "users/other/a.pdf", "users\\x\\a.pdf"],
)
def test_storage_identifier_rejects_arbitrary_paths(value: str) -> None:
    with pytest.raises(InvalidStorageIdentifierError):
        validate_storage_identifier(value, uuid.UUID(int=1))


@pytest.mark.asyncio
async def test_inspection_state_cas_sql_is_fenced_and_never_commits() -> None:
    db = AsyncMock(spec=AsyncSession)
    execution = Mock()
    execution.scalar_one_or_none.return_value = None
    db.execute.return_value = execution
    user_id = uuid.uuid4()

    result = await persist_document_job_inspection_state(
        db,
        "doc_job_1",
        user_id=user_id,
        state="completed",
        input_hash="a" * 64,
        result_path=f"users/{user_id}/documents/report.json",
        result_hash="b" * 64,
        lease_owner="worker-1",
        expected_lease_version=4,
    )

    sql = str(db.execute.await_args.args[0])
    for guard in (
        "document_processing_jobs.user_id",
        "document_processing_jobs.job_type",
        "document_processing_jobs.stage",
        "document_processing_jobs.status",
        "document_processing_jobs.lease_owner",
        "document_processing_jobs.lease_version",
        "document_processing_jobs.lease_expires_at >",
        "document_processing_jobs.inspection_call_state",
        "document_processing_jobs.inspection_input_hash",
    ):
        assert guard in sql
    assert result is None
    db.flush.assert_awaited_once()
    db.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_success_cas_clears_temporary_references_but_keeps_markdown() -> None:
    db = AsyncMock(spec=AsyncSession)
    execution = Mock()
    execution.scalar_one_or_none.return_value = None
    db.execute.return_value = execution
    user_id = uuid.uuid4()
    artifact = type(
        "Artifact",
        (),
        {
            "user_id": user_id,
            "markdown_path": f"users/{user_id}/documents/cache.md.enc",
            "markdown_hash": "a" * 64,
            "parser_engine": "mineru",
        },
    )()

    await _mark_document_job_succeeded_cas(
        db,
        "doc_job_1",
        expected_stage="indexing",
        expected_retry_count=0,
        expected_lease_version=2,
        artifact=artifact,
        job_type="knowledge",
    )

    params = db.execute.await_args.args[0].compile().params
    assert params["markdown_path"] == artifact.markdown_path
    assert params["index_artifact_path"] is None
    assert params["index_artifact_hash"] is None
    assert params["inspection_result_path"] is None
    assert params["inspection_result_hash"] is None


@pytest.mark.asyncio
async def test_source_hash_is_streamed_and_verified() -> None:
    user_id = uuid.uuid4()
    trusted = await prepare_source_artifact(
        user_id,
        _source_path(user_id),
        SOURCE_HASH,
        chunk_reader=lambda _path: _chunks(SOURCE),
    )
    assert trusted.content_hash == SOURCE_HASH

    with pytest.raises(ValueError, match="内容哈希不一致"):
        await prepare_source_artifact(
            user_id,
            _source_path(user_id),
            "a" * 64,
            chunk_reader=lambda _path: _chunks(SOURCE),
        )


@pytest.mark.asyncio
@pytest.mark.parametrize("content", [b"\xff", b"# short"])
async def test_markdown_requires_utf8_and_quality(content: bytes) -> None:
    user_id = uuid.uuid4()
    with pytest.raises(ValueError):
        await prepare_markdown_artifact(
            user_id,
            _markdown_path(user_id),
            chunk_reader=lambda _path: _chunks(content),
        )


@pytest.mark.asyncio
async def test_markdown_hash_is_computed_not_trusted() -> None:
    user_id = uuid.uuid4()
    artifact = await prepare_markdown_artifact(
        user_id,
        _markdown_path(user_id),
        expected_hash="a" * 64,
        chunk_reader=lambda _path: _chunks(MARKDOWN),
        require_expected_hash=False,
    )
    assert artifact.markdown_hash == MARKDOWN_HASH


@pytest.mark.asyncio
async def test_markdown_envelope_is_decrypted_before_plaintext_hash_validation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(config.settings, "data_encryption_key", "markdown-artifact-key")
    envelope = encrypt_sensitive_artifact(MARKDOWN)
    user_id = uuid.uuid4()

    artifact = await prepare_markdown_artifact(
        user_id,
        _markdown_path(user_id) + ".enc",
        expected_hash=MARKDOWN_HASH,
        chunk_reader=lambda _path: _chunks(envelope),
    )

    assert artifact.markdown_hash == MARKDOWN_HASH
    assert artifact.markdown.encode() == MARKDOWN


@pytest.mark.parametrize(
    ("code", "expected"),
    [("mineru_failed", "mineru_failed"), ("secret_internal_error", "processing_failed")],
)
def test_error_codes_are_allowlisted(code: str, expected: str) -> None:
    stable_code, message = sanitize_document_job_error(code)
    assert stable_code == expected
    assert "secret" not in message


def test_required_conversion_error_is_allowlisted_without_exposing_details() -> None:
    code, message = sanitize_document_job_error("convert_to_pdf_required")
    assert code == "convert_to_pdf_required"
    assert message == "该文档需先转换为 PDF 后重新上传"


@pytest.mark.asyncio
async def test_create_rejects_cross_owner_related_resource_before_flush() -> None:
    user_id = uuid.uuid4()
    source = await prepare_source_artifact(
        user_id,
        _source_path(user_id),
        SOURCE_HASH,
        chunk_reader=lambda _path: _chunks(SOURCE),
    )
    db = Mock(spec=AsyncSession)
    db.scalar = AsyncMock(return_value=None)
    db.flush = AsyncMock()

    with pytest.raises(DocumentJobOwnershipError, match="knowledge_version_not_owned"):
        await create_document_job(
            db,
            source=source,
            job_type="knowledge",
            file_type="pdf",
            knowledge_version_id=42,
        )

    db.flush.assert_not_awaited()


def test_cache_reuse_requires_same_user_content_hash_and_parser_version() -> None:
    user_id = uuid.uuid4()
    source = type("Source", (), {"user_id": user_id, "content_hash": SOURCE_HASH})()
    markdown = type("Markdown", (), {"user_id": user_id})()

    validate_reusable_markdown(
        source=source,
        markdown=markdown,
        parser_version="2",
        cached_content_hash=SOURCE_HASH,
        cached_parser_version="2",
    )
    for changed in (
        {"markdown": type("Markdown", (), {"user_id": uuid.uuid4()})()},
        {"cached_content_hash": "a" * 64},
        {"cached_parser_version": "1"},
    ):
        values = {
            "source": source,
            "markdown": markdown,
            "parser_version": "2",
            "cached_content_hash": SOURCE_HASH,
            "cached_parser_version": "2",
            **changed,
        }
        with pytest.raises(ValueError):
            validate_reusable_markdown(**values)


@pytest.mark.asyncio
async def test_create_flushes_and_never_commits_or_rolls_back_caller_session() -> None:
    user_id = uuid.uuid4()
    source = await prepare_source_artifact(
        user_id,
        _source_path(user_id),
        SOURCE_HASH,
        chunk_reader=lambda _path: _chunks(SOURCE),
    )
    db = Mock(spec=AsyncSession)
    db.flush = AsyncMock(side_effect=RuntimeError("flush failed"))
    db.commit = AsyncMock()
    db.rollback = AsyncMock()

    with pytest.raises(RuntimeError, match="flush failed"):
        await create_document_job(db, source=source, job_type="knowledge", file_type="pdf")

    db.commit.assert_not_awaited()
    db.rollback.assert_not_awaited()


@pytest.mark.asyncio
async def test_create_persists_dispatch_intent_in_the_caller_transaction() -> None:
    user_id = uuid.uuid4()
    source = await prepare_source_artifact(
        user_id,
        _source_path(user_id),
        SOURCE_HASH,
        chunk_reader=lambda _path: _chunks(SOURCE),
    )
    db = Mock(spec=AsyncSession)
    db.add = Mock()
    db.flush = AsyncMock()
    db.commit = AsyncMock()

    job = await create_document_job(db, source=source, job_type="knowledge", file_type="pdf")

    assert job.status is None or job.status == "queued"
    assert job.dispatch_pending is True
    assert job.dispatch_retry_count == 0
    assert job.next_dispatch_at is not None
    db.add.assert_called_once_with(job)
    db.commit.assert_not_awaited()


@pytest.mark.parametrize(
    ("current", "target", "job_type", "has_markdown"),
    [
        ("queued", "detecting", "knowledge", False),
        ("detecting", "parsing_local", "knowledge", False),
        ("detecting", "parsing_mineru", "knowledge", False),
        ("parsing_local", "parsing_mineru", "knowledge", False),
        ("parsing_local", "indexing", "knowledge", True),
        ("parsing_mineru", "indexing", "knowledge", True),
        ("parsing_local", "inspecting", "inspection", True),
        ("parsing_mineru", "inspecting", "inspection", True),
        ("indexing", "inspecting", "inspection", True),
        ("indexing", "succeeded", "knowledge", True),
        ("inspecting", "succeeded", "inspection", True),
        ("queued", "indexing", "knowledge", True),
    ],
)
def test_explicit_state_machine_accepts_legal_transitions(
    current: str, target: str, job_type: str, has_markdown: bool
) -> None:
    validate_document_job_transition(
        current_stage=current,
        target_stage=target,
        job_type=job_type,
        current_progress=20,
        target_progress=30,
        has_valid_markdown=has_markdown,
    )


@pytest.mark.parametrize(
    ("current", "target", "job_type", "current_progress", "target_progress", "has_markdown"),
    [
        ("indexing", "parsing_local", "knowledge", 70, 30, True),
        ("queued", "indexing", "knowledge", 0, 70, False),
        ("parsing_local", "inspecting", "inspection", 60, 90, False),
        ("parsing_local", "inspecting", "knowledge", 60, 90, True),
        ("parsing_mineru", "inspecting", "knowledge", 60, 90, True),
        ("indexing", "inspecting", "knowledge", 70, 90, True),
        ("inspecting", "inspecting", "knowledge", 90, 91, True),
        ("detecting", "detecting", "knowledge", 20, 20, False),
        ("detecting", "detecting", "knowledge", 20, 10, False),
    ],
)
def test_state_machine_rejects_regression_missing_artifact_and_wrong_branch(
    current: str,
    target: str,
    job_type: str,
    current_progress: int,
    target_progress: int,
    has_markdown: bool,
) -> None:
    with pytest.raises(InvalidDocumentJobTransitionError):
        validate_document_job_transition(
            current_stage=current,
            target_stage=target,
            job_type=job_type,
            current_progress=current_progress,
            target_progress=target_progress,
            has_valid_markdown=has_markdown,
        )


@pytest_asyncio.fixture(autouse=True, scope="session")
async def _ensure_schema() -> None:
    if os.environ.get("TEST_DATABASE_URL") is not None:
        from tests.conftest import _create_schema_and_tables

        await _create_schema_and_tables(db_mod.engine)


@pytest_asyncio.fixture(autouse=True)
async def _cleanup_before_test() -> None:
    if os.environ.get("TEST_DATABASE_URL") is not None:
        from tests.conftest import _cleanup_tables

        await _cleanup_tables(db_mod.engine)


@pytest_asyncio.fixture
async def session() -> AsyncSession:
    if os.environ.get("TEST_DATABASE_URL") is None:
        pytest.skip("需要显式设置 TEST_DATABASE_URL 才执行真实 PostgreSQL 并发测试")
    async with async_session() as value:
        yield value


async def _user(session: AsyncSession, label: str) -> uuid.UUID:
    user = User(nickname=label, email=f"{label}-{uuid.uuid4().hex}@test.com", hashed_password="x")
    session.add(user)
    await session.commit()
    return user.id


async def _job(session: AsyncSession, user_id: uuid.UUID, *, job_type: str = "knowledge"):
    source = await prepare_source_artifact(
        user_id,
        _source_path(user_id),
        SOURCE_HASH,
        chunk_reader=lambda _path: _chunks(SOURCE),
    )
    async with session.begin():
        job = await create_document_job(session, source=source, job_type=job_type, file_type="pdf")
    return job


@pytest.mark.asyncio
async def test_mutations_flush_without_committing_caller_transaction(session: AsyncSession) -> None:
    user_id = await _user(session, "transaction-owner")
    source = await prepare_source_artifact(
        user_id, _source_path(user_id), SOURCE_HASH, chunk_reader=lambda _path: _chunks(SOURCE)
    )
    job_id: uuid.UUID | None = None
    with pytest.raises(RuntimeError, match="orchestration failed"):
        async with session.begin():
            job = await create_document_job(session, source=source, job_type="knowledge", file_type="pdf")
            job_id = job.id
            raise RuntimeError("orchestration failed")
    assert job_id is not None
    assert await session.get(DocumentProcessingJob, job_id) is None


@pytest.mark.asyncio
async def test_same_stage_concurrent_updates_use_lease_and_monotonic_progress(session: AsyncSession) -> None:
    user_id = await _user(session, "same-stage")
    job = await _job(session, user_id)
    async with session.begin():
        claimed = await update_document_job_stage(
            session,
            job.job_id,
            expected_stage="queued",
            expected_retry_count=0,
            expected_lease_version=0,
            stage="detecting",
            progress=10,
        )
    assert claimed is not None

    async def advance(progress: int):
        async with async_session() as worker:
            async with worker.begin():
                return await update_document_job_stage(
                    worker,
                    job.job_id,
                    expected_stage="detecting",
                    expected_retry_count=0,
                    expected_lease_version=claimed.lease_version,
                    stage="detecting",
                    progress=progress,
                )

    results = await asyncio.gather(advance(20), advance(30))
    assert sum(value is not None for value in results) == 1


@pytest.mark.asyncio
async def test_running_old_worker_loses_after_new_worker_advances(session: AsyncSession) -> None:
    user_id = await _user(session, "old-worker")
    job = await _job(session, user_id)
    async with session.begin():
        first = await update_document_job_stage(
            session,
            job.job_id,
            expected_stage="queued",
            expected_retry_count=0,
            expected_lease_version=0,
            stage="detecting",
            progress=10,
        )
        second = await update_document_job_stage(
            session,
            job.job_id,
            expected_stage="detecting",
            expected_retry_count=0,
            expected_lease_version=first.lease_version,
            stage="parsing_local",
            progress=30,
        )
    async with session.begin():
        stale = await mark_document_job_failed(
            session,
            job.job_id,
            expected_stage="detecting",
            expected_retry_count=0,
            expected_lease_version=first.lease_version,
            error_code="conversion_failed",
        )
    assert second is not None
    assert stale is None


@pytest.mark.asyncio
async def test_success_and_failure_race_only_one_wins(session: AsyncSession) -> None:
    user_id = await _user(session, "terminal-race")
    job = await _job(session, user_id)
    markdown = await prepare_markdown_artifact(
        user_id, _markdown_path(user_id), chunk_reader=lambda _path: _chunks(MARKDOWN)
    )
    async with session.begin():
        indexed = await update_document_job_stage(
            session,
            job.job_id,
            expected_stage="queued",
            expected_retry_count=0,
            expected_lease_version=0,
            stage="indexing",
            progress=80,
            validated_markdown=markdown,
        )

    async def succeed():
        async with async_session() as worker:
            return await mark_document_job_succeeded(
                worker,
                job.job_id,
                expected_stage="indexing",
                expected_retry_count=0,
                expected_lease_version=indexed.lease_version,
                artifact=markdown,
                chunk_reader=lambda _path: _chunks(MARKDOWN),
            )

    async def fail():
        async with async_session() as worker:
            async with worker.begin():
                return await mark_document_job_failed(
                    worker,
                    job.job_id,
                    expected_stage="indexing",
                    expected_retry_count=0,
                    expected_lease_version=indexed.lease_version,
                    error_code="indexing_failed",
                )

    results = await asyncio.gather(succeed(), fail())
    assert sum(value is not None for value in results) == 1


@pytest.mark.asyncio
async def test_retry_invalidates_old_retry_round_and_lease(session: AsyncSession) -> None:
    user_id = await _user(session, "retry-old-round")
    job = await _job(session, user_id)
    async with session.begin():
        running = await update_document_job_stage(
            session,
            job.job_id,
            expected_stage="queued",
            expected_retry_count=0,
            expected_lease_version=0,
            stage="detecting",
            progress=10,
        )
        failed = await mark_document_job_failed(
            session,
            job.job_id,
            expected_stage="detecting",
            expected_retry_count=0,
            expected_lease_version=running.lease_version,
            error_code="parse_timeout",
        )
    failed_lease_version = failed.lease_version
    async with session.begin():
        retried = await retry_document_job(session, job.job_id, user_id, max_retries=2)
    async with session.begin():
        stale = await mark_document_job_failed(
            session,
            job.job_id,
            expected_stage="detecting",
            expected_retry_count=0,
            expected_lease_version=failed_lease_version,
            error_code="parse_timeout",
        )
    assert retried.retry_count == 1
    assert retried.lease_version > failed_lease_version
    assert stale is None


@pytest.mark.asyncio
async def test_unexpired_lease_rejects_takeover_and_expired_lease_is_fenced(session: AsyncSession) -> None:
    user_id = await _user(session, "lease-takeover")
    job = await _job(session, user_id)
    now = datetime.datetime.now(datetime.timezone.utc)
    async with session.begin():
        first = await claim_document_job_lease(
            session, job.job_id, lease_owner="owner-a", lease_seconds=60, now=now
        )
    assert first is not None
    first_lease_version = first.lease_version
    async with session.begin():
        blocked = await claim_document_job_lease(
            session,
            job.job_id,
            lease_owner="owner-b",
            lease_seconds=60,
            now=now + datetime.timedelta(seconds=30),
        )
        takeover = await claim_document_job_lease(
            session,
            job.job_id,
            lease_owner="owner-b",
            lease_seconds=60,
            now=now + datetime.timedelta(seconds=61),
        )
    assert blocked is None
    assert takeover is not None
    assert takeover.lease_owner == "owner-b"
    assert takeover.lease_version == first_lease_version + 1


@pytest.mark.asyncio
async def test_heartbeat_and_release_require_current_owner_and_fence(session: AsyncSession) -> None:
    user_id = await _user(session, "lease-heartbeat")
    job = await _job(session, user_id)
    now = datetime.datetime.now(datetime.timezone.utc)
    async with session.begin():
        claimed = await claim_document_job_lease(
            session, job.job_id, lease_owner="owner-a", lease_seconds=30, now=now
        )
    async with session.begin():
        assert not await heartbeat_document_job_lease(
            session,
            job.job_id,
            lease_owner="old-owner",
            expected_lease_version=claimed.lease_version,
            lease_seconds=30,
            now=now,
        )
        assert await heartbeat_document_job_lease(
            session,
            job.job_id,
            lease_owner="owner-a",
            expected_lease_version=claimed.lease_version,
            lease_seconds=60,
            now=now,
        )
        assert await release_document_job_lease(
            session,
            job.job_id,
            lease_owner="owner-a",
            expected_lease_version=claimed.lease_version,
        )
    async with session.begin():
        stale = await update_document_job_stage(
            session,
            job.job_id,
            expected_stage="queued",
            expected_retry_count=0,
            expected_lease_version=claimed.lease_version,
            lease_owner="owner-a",
            stage="detecting",
            progress=10,
        )
    assert stale is None


@pytest.mark.asyncio
async def test_inspection_state_cas_requires_current_unexpired_inspecting_lease(session: AsyncSession) -> None:
    user_id = await _user(session, "inspection-state-cas")
    job = await _job(session, user_id, job_type="inspection")
    now = datetime.datetime.now(datetime.timezone.utc)
    async with session.begin():
        job.status = "running"
        job.stage = "inspecting"
        job.progress = 90
        job.lease_owner = "owner-a"
        job.lease_version = 3
        job.lease_expires_at = now + datetime.timedelta(minutes=1)
    async with session.begin():
        stale = await persist_document_job_inspection_state(
            session,
            job.job_id,
            user_id=user_id,
            state="started",
            input_hash="a" * 64,
            lease_owner="owner-b",
            expected_lease_version=3,
        )
        started = await persist_document_job_inspection_state(
            session,
            job.job_id,
            user_id=user_id,
            state="started",
            input_hash="a" * 64,
            lease_owner="owner-a",
            expected_lease_version=3,
        )
    assert stale is None
    assert started is not None and started.inspection_call_state == "started"

    async with session.begin():
        started.lease_expires_at = now - datetime.timedelta(seconds=1)
    async with session.begin():
        expired = await persist_document_job_inspection_state(
            session,
            job.job_id,
            user_id=user_id,
            state="completed",
            input_hash="a" * 64,
            result_path=f"users/{user_id}/documents/report.json",
            result_hash="b" * 64,
            lease_owner="owner-a",
            expected_lease_version=3,
        )
    assert expired is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("stage", "progress", "job_type"),
    [("parsing_local", 60, "knowledge"), ("indexing", 84, "knowledge"), ("inspecting", 99, "inspection")],
)
async def test_expired_worker_can_resume_at_progress_ceiling(
    session: AsyncSession, stage: str, progress: int, job_type: str
) -> None:
    user_id = await _user(session, f"resume-{progress}")
    job = await _job(session, user_id, job_type=job_type)
    now = datetime.datetime.now(datetime.timezone.utc)
    async with session.begin():
        job.status = "running"
        job.stage = stage
        job.progress = progress
        job.lease_owner = "dead-owner"
        job.lease_expires_at = now - datetime.timedelta(seconds=1)
        await session.flush()
    async with session.begin():
        resumed = await claim_document_job_lease(
            session, job.job_id, lease_owner="new-owner", lease_seconds=60, now=now
        )
    assert resumed is not None
    assert (resumed.stage, resumed.progress) == (stage, progress)


@pytest.mark.asyncio
async def test_explicit_cancellation_is_stable_terminal_state(session: AsyncSession) -> None:
    user_id = await _user(session, "cancel-terminal")
    job = await _job(session, user_id)
    async with session.begin():
        claimed = await claim_document_job_lease(
            session, job.job_id, lease_owner="owner-a", lease_seconds=60
        )
        cancelled = await cancel_document_job(
            session,
            job.job_id,
            lease_owner="owner-a",
            expected_lease_version=claimed.lease_version,
        )
    assert cancelled is not None
    assert cancelled.status == "cancelled"
    async with session.begin():
        assert await claim_document_job_lease(
            session, job.job_id, lease_owner="owner-b", lease_seconds=60
        ) is None
