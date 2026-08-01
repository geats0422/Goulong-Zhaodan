from __future__ import annotations

import asyncio
import uuid
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.services.document_parser import DocumentParseError
from app.services.contract_classifier import ContractClassification
from app.workers.config import WorkerSettings
from app.workers.tasks import _persist_parsed_markdown, _serialize_inspection_result, document_processing_task
from app.workers import tasks


USER_ID = uuid.UUID("12345678-1234-1234-1234-123456789012")


def test_inspection_job_result_carries_classification_after_parsing() -> None:
    report = SimpleNamespace(issues=[], overall_risk="low", regulation_refs=[], summary="ok")
    classification = ContractClassification(
        engineering_type_key="municipal-road",
        contract_type_key="labor-subcontract",
        confidence="high",
        evidence=["市政道路", "劳务分包"],
        source="model",
        requires_confirmation=False,
    )

    payload = _serialize_inspection_result(report, classification=classification)

    assert payload.decode("utf-8").find('"classification"') >= 0
    assert '"engineering_type_key":"municipal-road"' in payload.decode("utf-8")


@pytest.fixture(scope="session")
def _ensure_schema():
    """These orchestration tests mock every persistence boundary and need no PostgreSQL."""


@pytest.fixture(autouse=True)
def _cleanup_before_test():
    """Override the integration-suite cleanup for this PG-free module."""


@pytest.fixture(autouse=True)
def _worker_boundaries(monkeypatch: pytest.MonkeyPatch):
    async def passthrough(_job, operation, **_kwargs):
        return await operation

    async def persist_index(_job, nodes):
        return SimpleNamespace(nodes=nodes, path="users/test/index.json", content_hash="c" * 64)

    monkeypatch.setattr("app.workers.tasks._run_with_lease_heartbeat", passthrough)
    monkeypatch.setattr("app.workers.tasks._load_index_artifact", AsyncMock(return_value=None))
    monkeypatch.setattr("app.workers.tasks._persist_index_artifact", persist_index)


def _job(
    *,
    stage: str = "queued",
    job_type: str = "knowledge",
    lease_version: int = 0,
    progress: int = 0,
    status: str = "queued",
    dispatch_retry_count: int = 0,
):
    return SimpleNamespace(
        job_id="doc_job_1",
        user_id=USER_ID,
        job_type=job_type,
        source_path=f"users/{USER_ID}/documents/source.pdf",
        content_hash="a" * 64,
        file_type="pdf",
        parser_version="1",
        stage=stage,
        status=status,
        progress=progress,
        retry_count=0,
        dispatch_retry_count=dispatch_retry_count,
        lease_version=lease_version,
        lease_owner="worker-1",
        mineru_task_id=None,
        mineru_upload_state=None,
        markdown_path=None,
        markdown_hash=None,
        parser_engine=None,
        index_artifact_path=None,
        index_artifact_hash=None,
        inspection_call_state=None,
        inspection_input_hash=None,
        inspection_result_path=None,
        inspection_result_hash=None,
        knowledge_version_id=7 if job_type == "knowledge" else None,
        inspection_record_id=8 if job_type == "inspection" else None,
    )


def _advanced(job, stage: str, progress: int):
    return SimpleNamespace(**{**vars(job), "stage": stage, "progress": progress, "status": "running", "lease_version": job.lease_version + 1})


def _artifact():
    return SimpleNamespace(
        user_id=USER_ID,
        markdown_path=f"users/{USER_ID}/documents/{'a' * 64}-1.md",
        markdown_hash="b" * 64,
        markdown="# 标题\n\n这是足够长的有效正文。" * 20,
        parser_engine="mineru",
    )


def test_worker_registers_document_pipeline_with_bounded_concurrency_and_timeout():
    registrations = [item for item in WorkerSettings.functions if getattr(item, "name", None) == "document_processing_task"]
    assert len(registrations) == 1
    assert registrations[0].timeout_s >= 1200
    assert 1 <= WorkerSettings.max_jobs <= 4


@pytest.mark.asyncio
async def test_markdown_is_saved_under_owner_path_with_actual_hash_and_engine(monkeypatch: pytest.MonkeyPatch):
    from app.core import config

    monkeypatch.setattr(config.settings, "data_encryption_key", "worker-artifact-test-key")
    job = _job(stage="parsing_mineru", status="running", lease_version=3)
    parsed = SimpleNamespace(
        markdown="# 标题\n\n" + "有效正文。" * 30,
        markdown_hash="b" * 64,
        content_hash=job.content_hash,
        parser_engine=SimpleNamespace(value="mineru"),
    )
    verified = _artifact()
    with (
        patch("app.services.file_storage.save_file") as save,
        patch("app.workers.tasks.prepare_markdown_artifact", new=AsyncMock(return_value=verified)) as prepare,
    ):
        result = await _persist_parsed_markdown(job, parsed)
    saved_path = save.call_args.args[0]
    assert saved_path.startswith(f"users/{USER_ID}/documents/")
    assert saved_path.endswith("-0-3.md.enc")
    assert parsed.markdown.encode() not in save.call_args.args[1]
    prepare.assert_awaited_once_with(
        USER_ID,
        saved_path,
        parser_engine="mineru",
        expected_hash=parsed.markdown_hash,
    )
    assert result is verified


def test_artifact_retention_defaults_to_thirty_days():
    from app.core.config import Settings

    assert Settings(_env_file=None).document_artifact_retention_days == 30


@pytest.mark.asyncio
async def test_parse_stored_document_passes_job_type_to_parser(monkeypatch: pytest.MonkeyPatch):
    job = _job(job_type="inspection")
    stored = SimpleNamespace(path=Path("/tmp/source.docx"), identity=object())
    parsed = SimpleNamespace(
        markdown="# 标题\n\n" + "有效正文。" * 30,
        markdown_hash="b" * 64,
        content_hash=job.content_hash,
        parser_engine=SimpleNamespace(value="markitdown"),
    )
    parse = AsyncMock(return_value=parsed)

    monkeypatch.setattr("app.services.file_storage.copy_storage_to_private_temp", lambda *_args, **_kwargs: stored)
    monkeypatch.setattr("app.services.file_storage.validate_document_snapshot", lambda *_args, **_kwargs: None)
    monkeypatch.setattr("app.workers.tasks.parse_document", parse)
    monkeypatch.setattr("app.workers.tasks.secure_unlink", lambda *_args, **_kwargs: None)

    result = await tasks._parse_stored_document(job)

    assert result.result is parsed
    assert result.job is job
    assert parse.await_args.kwargs["job_type"] == "inspection"


@pytest.mark.asyncio
async def test_knowledge_success_deletes_only_temporary_artifacts_after_commit():
    job = _job(stage="indexing", status="running", progress=85)
    job.index_artifact_path = f"users/{USER_ID}/documents/index.json.enc"
    job.inspection_result_path = f"users/{USER_ID}/documents/report.json.enc"
    artifact = _artifact()

    with (
        patch("app.workers.tasks.mark_document_job_succeeded", new=AsyncMock(return_value=SimpleNamespace())) as mark,
        patch("app.workers.tasks._delete_terminal_artifact", new=AsyncMock()) as delete,
    ):
        completed = await tasks._complete_document_job(job, artifact)

    assert completed is True
    mark.assert_awaited_once()
    assert {call.args for call in delete.await_args_list} == {
        (job.index_artifact_path,),
        (job.inspection_result_path,),
    }
    assert all(call.args[0] != artifact.markdown_path for call in delete.await_args_list)


@pytest.mark.asyncio
async def test_worker_reports_parse_and_index_progress_then_completes_knowledge_job():
    queued = _job()
    detecting = _advanced(queued, "detecting", 10)
    parsing = _advanced(detecting, "parsing_local", 30)
    indexing = _advanced(parsing, "indexing", 70)
    indexed = _advanced(indexing, "indexing", 85)
    artifact = _artifact()
    parse_result = SimpleNamespace(parser_engine=SimpleNamespace(value="mineru"))
    nodes = [SimpleNamespace(content="node")]

    with (
        patch("app.workers.tasks._load_document_job", new=AsyncMock(return_value=queued)),
        patch("app.workers.tasks._load_valid_markdown", new=AsyncMock(return_value=None)),
        patch("app.workers.tasks._advance_document_job", new=AsyncMock(side_effect=[detecting, parsing, indexing])) as advance,
        patch("app.workers.tasks._parse_stored_document", new=AsyncMock(return_value=parse_result)) as parse,
        patch("app.workers.tasks._persist_parsed_markdown", new=AsyncMock(return_value=artifact)),
        patch("app.workers.tasks._build_document_index", new=AsyncMock(return_value=nodes)) as build_index,
        patch("app.workers.tasks._commit_document_index", new=AsyncMock(return_value=indexed)) as commit_index,
        patch("app.workers.tasks._complete_document_job", new=AsyncMock(return_value=True)) as complete,
        patch("app.workers.tasks._fail_document_job", new=AsyncMock()) as fail,
    ):
        await document_processing_task({}, queued.job_id)

    assert [call.kwargs["stage"] for call in advance.await_args_list] == ["detecting", "parsing_local", "indexing"]
    parse.assert_awaited_once()
    build_index.assert_awaited_once_with(artifact)
    assert commit_index.await_args.args[:2] == (indexing, artifact)
    assert commit_index.await_args.args[2].nodes == nodes
    complete.assert_awaited_once_with(indexed, artifact)
    fail.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("failure_at", "expected_code"),
    [("parse", "mineru_failed"), ("index", "indexing_failed")],
)
async def test_worker_marks_stable_sanitized_failure(failure_at: str, expected_code: str):
    queued = _job()
    detecting = _advanced(queued, "detecting", 10)
    parsing = _advanced(detecting, "parsing_local", 30)
    artifact = _artifact()
    parse_error = DocumentParseError("mineru_failed", "secret URL") if failure_at == "parse" else None
    index_side_effect = RuntimeError("secret key") if failure_at == "index" else []

    with (
        patch("app.workers.tasks._load_document_job", new=AsyncMock(return_value=queued)),
        patch("app.workers.tasks._load_valid_markdown", new=AsyncMock(return_value=None)),
        patch("app.workers.tasks._advance_document_job", new=AsyncMock(side_effect=[detecting, parsing, _advanced(parsing, "indexing", 70)])),
        patch(
            "app.workers.tasks._parse_stored_document",
            new=AsyncMock(side_effect=parse_error, return_value=SimpleNamespace()),
        ),
        patch("app.workers.tasks._persist_parsed_markdown", new=AsyncMock(return_value=artifact)),
        patch("app.workers.tasks._build_document_index", new=AsyncMock(side_effect=index_side_effect)),
        patch("app.workers.tasks._fail_document_job", new=AsyncMock(return_value=True)) as fail,
    ):
        await document_processing_task({}, queued.job_id)

    fail.assert_awaited_once()
    assert fail.await_args.kwargs["error_code"] == expected_code
    assert "secret" not in fail.await_args.kwargs


@pytest.mark.asyncio
async def test_worker_resumes_from_valid_markdown_without_repeating_mineru():
    queued = _job()
    artifact = _artifact()
    indexing = _advanced(queued, "indexing", 70)
    indexed = _advanced(indexing, "indexing", 85)

    with (
        patch("app.workers.tasks._load_document_job", new=AsyncMock(return_value=queued)),
        patch("app.workers.tasks._load_valid_markdown", new=AsyncMock(return_value=artifact)),
        patch(
            "app.workers.tasks._load_index_artifact",
            new=AsyncMock(return_value=SimpleNamespace(nodes=[], path="index", content_hash="c" * 64)),
        ),
        patch("app.workers.tasks._advance_document_job", new=AsyncMock(return_value=indexing)) as advance,
        patch("app.workers.tasks._parse_stored_document", new=AsyncMock()) as parse,
        patch("app.workers.tasks._build_document_index", new=AsyncMock(return_value=[])),
        patch("app.workers.tasks._commit_document_index", new=AsyncMock(return_value=indexed)),
        patch("app.workers.tasks._complete_document_job", new=AsyncMock(return_value=True)),
    ):
        await document_processing_task({}, queued.job_id)

    parse.assert_not_awaited()
    assert advance.await_args.kwargs["stage"] == "indexing"
    assert advance.await_args.kwargs["artifact"] is artifact


@pytest.mark.asyncio
async def test_worker_resumes_after_committed_index_without_repeating_pageindex():
    indexed = _job(stage="indexing", status="running", progress=85, lease_version=4)
    artifact = _artifact()
    with (
        patch("app.workers.tasks._load_document_job", new=AsyncMock(return_value=indexed)),
        patch("app.workers.tasks._load_valid_markdown", new=AsyncMock(return_value=artifact)),
        patch("app.workers.tasks._advance_document_job", new=AsyncMock()) as advance,
        patch("app.workers.tasks._build_document_index", new=AsyncMock()) as build_index,
        patch("app.workers.tasks._complete_document_job", new=AsyncMock(return_value=True)) as complete,
    ):
        await document_processing_task({}, indexed.job_id)
    advance.assert_not_awaited()
    build_index.assert_not_awaited()
    complete.assert_awaited_once_with(indexed, artifact)


@pytest.mark.asyncio
async def test_restarted_inspection_claims_a_new_lease_before_deepseek():
    inspecting = _job(
        stage="inspecting",
        job_type="inspection",
        status="running",
        progress=90,
        lease_version=4,
    )
    claimed = _advanced(inspecting, "inspecting", 91)
    artifact = _artifact()
    report = SimpleNamespace(overall_risk="low")
    with (
        patch("app.workers.tasks._load_document_job", new=AsyncMock(return_value=inspecting)),
        patch("app.workers.tasks._load_valid_markdown", new=AsyncMock(return_value=artifact)),
        patch("app.workers.tasks._advance_document_job", new=AsyncMock(return_value=claimed)) as advance,
        patch(
            "app.workers.tasks._run_resumable_document_inspection",
            new=AsyncMock(return_value=SimpleNamespace(job=claimed, report=report)),
        ) as inspect,
        patch("app.workers.tasks._commit_inspection_success", new=AsyncMock(return_value=True)) as commit,
    ):
        await document_processing_task({}, inspecting.job_id)
    advance.assert_awaited_once_with(inspecting, stage="inspecting", progress=91, artifact=artifact)
    inspect.assert_awaited_once_with(claimed, [], fallback_text=artifact.markdown)
    commit.assert_awaited_once_with(claimed, artifact, report)


@pytest.mark.asyncio
async def test_completed_job_is_idempotent_noop():
    completed = _job(stage="succeeded", status="succeeded", progress=100)
    with (
        patch("app.workers.tasks._load_document_job", new=AsyncMock(return_value=completed)),
        patch("app.workers.tasks._advance_document_job", new=AsyncMock()) as advance,
        patch("app.workers.tasks._parse_stored_document", new=AsyncMock()) as parse,
    ):
        await document_processing_task({}, completed.job_id)
    advance.assert_not_awaited()
    parse.assert_not_awaited()


@pytest.mark.asyncio
async def test_inspection_branch_skips_pageindex_and_uses_markdown_text():
    queued = _job(job_type="inspection")
    artifact = _artifact()
    inspecting = _advanced(queued, "inspecting", 90)
    report = SimpleNamespace(overall_risk="low")

    with (
        patch("app.workers.tasks._load_document_job", new=AsyncMock(return_value=queued)),
        patch("app.workers.tasks._load_valid_markdown", new=AsyncMock(return_value=artifact)),
        patch("app.workers.tasks._advance_document_job", new=AsyncMock(return_value=inspecting)),
        patch("app.workers.tasks._build_document_index", new=AsyncMock()) as build_index,
        patch("app.workers.tasks._commit_document_index", new=AsyncMock()) as commit_index,
        patch(
            "app.workers.tasks._run_resumable_document_inspection",
            new=AsyncMock(return_value=SimpleNamespace(job=inspecting, report=report)),
        ) as inspect,
        patch("app.workers.tasks._commit_inspection_success", new=AsyncMock(return_value=True)) as commit,
    ):
        await document_processing_task({}, queued.job_id)

    build_index.assert_not_awaited()
    commit_index.assert_not_awaited()
    inspect.assert_awaited_once_with(inspecting, [], fallback_text=artifact.markdown)
    assert inspect.await_args.args[0].user_id == USER_ID
    commit.assert_awaited_once_with(inspecting, artifact, report)


@pytest.mark.asyncio
async def test_stale_worker_stops_when_lease_cas_is_lost():
    queued = _job()
    with (
        patch("app.workers.tasks._load_document_job", new=AsyncMock(return_value=queued)),
        patch("app.workers.tasks._load_valid_markdown", new=AsyncMock(return_value=None)),
        patch("app.workers.tasks._advance_document_job", new=AsyncMock(return_value=None)),
        patch("app.workers.tasks._parse_stored_document", new=AsyncMock()) as parse,
        patch("app.workers.tasks._fail_document_job", new=AsyncMock()) as fail,
    ):
        await document_processing_task({}, queued.job_id)
    parse.assert_not_awaited()
    fail.assert_not_awaited()


@pytest.mark.asyncio
async def test_cas_loss_never_deletes_preexisting_recovery_markdown():
    queued = _job()
    artifact = _artifact()
    with (
        patch("app.workers.tasks._load_document_job", new=AsyncMock(return_value=queued)),
        patch("app.workers.tasks._load_valid_markdown", new=AsyncMock(return_value=artifact)),
        patch("app.workers.tasks._advance_document_job", new=AsyncMock(return_value=None)),
        patch("app.services.file_storage.delete_file", return_value=True) as delete,
    ):
        await document_processing_task({}, queued.job_id)
    delete.assert_not_called()


@pytest.mark.asyncio
async def test_cancellation_cleans_up_and_is_rethrown_without_marking_failed():
    queued = _job()
    detecting = _advanced(queued, "detecting", 10)
    parsing = _advanced(detecting, "parsing_local", 30)
    with (
        patch("app.workers.tasks._load_document_job", new=AsyncMock(return_value=queued)),
        patch("app.workers.tasks._load_valid_markdown", new=AsyncMock(return_value=None)),
        patch("app.workers.tasks._advance_document_job", new=AsyncMock(side_effect=[detecting, parsing])),
        patch("app.workers.tasks._parse_stored_document", new=AsyncMock(side_effect=asyncio.CancelledError)),
        patch("app.workers.tasks._cleanup_cancelled_document_job", new=AsyncMock()) as cleanup,
        patch("app.workers.tasks._release_document_job", new=AsyncMock(return_value=True)) as release,
        patch("app.workers.tasks._fail_document_job", new=AsyncMock()) as fail,
        pytest.raises(asyncio.CancelledError),
    ):
        await document_processing_task({"job_try": 1, "max_tries": 3}, queued.job_id)
    cleanup.assert_awaited_once_with(parsing)
    release.assert_awaited_once_with(parsing, redispatch=True)
    fail.assert_not_awaited()


@pytest.mark.asyncio
async def test_explicit_cancellation_writes_cancelled_terminal_state():
    queued = _job()
    detecting = _advanced(queued, "detecting", 10)
    parsing = _advanced(detecting, "parsing_local", 30)
    with (
        patch("app.workers.tasks._load_document_job", new=AsyncMock(return_value=queued)),
        patch("app.workers.tasks._load_valid_markdown", new=AsyncMock(return_value=None)),
        patch("app.workers.tasks._advance_document_job", new=AsyncMock(side_effect=[detecting, parsing])),
        patch("app.workers.tasks._parse_stored_document", new=AsyncMock(side_effect=asyncio.CancelledError)),
        patch("app.workers.tasks._cleanup_cancelled_document_job", new=AsyncMock()),
        patch("app.workers.tasks._cancel_document_job", new=AsyncMock(return_value=True)) as cancel,
        patch("app.workers.tasks._release_document_job", new=AsyncMock()) as release,
        patch("app.workers.tasks._fail_document_job", new=AsyncMock()) as fail,
        pytest.raises(asyncio.CancelledError),
    ):
        await document_processing_task({"cancel_requested": True}, queued.job_id)
    cancel.assert_awaited_once_with(parsing)
    release.assert_not_awaited()
    fail.assert_not_awaited()


@pytest.mark.asyncio
async def test_retryable_worker_failure_keeps_progress_and_releases_for_redispatch():
    queued = _job()
    detecting = _advanced(queued, "detecting", 10)
    parsing = _advanced(detecting, "parsing_local", 60)
    with (
        patch("app.workers.tasks._load_document_job", new=AsyncMock(return_value=queued)),
        patch("app.workers.tasks._load_valid_markdown", new=AsyncMock(return_value=None)),
        patch("app.workers.tasks._advance_document_job", new=AsyncMock(side_effect=[detecting, parsing])),
        patch("app.workers.tasks._parse_stored_document", new=AsyncMock(side_effect=RuntimeError("transient"))),
        patch("app.workers.tasks._release_document_job", new=AsyncMock(return_value=True)) as release,
        patch("app.workers.tasks._fail_document_job", new=AsyncMock()) as fail,
        pytest.raises(RuntimeError, match="transient"),
    ):
        await document_processing_task({"job_try": 1, "max_tries": 3}, queued.job_id)
    release.assert_awaited_once_with(parsing, redispatch=True)
    fail.assert_not_awaited()


@pytest.mark.asyncio
async def test_worker_uses_persisted_dispatch_attempts_for_final_failure():
    indexing = _job(stage="indexing", status="running", progress=89, lease_version=4, dispatch_retry_count=2)
    artifact = _artifact()
    with (
        patch("app.workers.tasks._load_document_job", new=AsyncMock(return_value=indexing)),
        patch("app.workers.tasks._load_valid_markdown", new=AsyncMock(return_value=artifact)),
        patch("app.workers.tasks._build_document_index", new=AsyncMock(side_effect=RuntimeError("pageindex failed"))),
        patch("app.workers.tasks._release_document_job", new=AsyncMock(return_value=True)) as release,
        patch("app.workers.tasks._fail_document_job", new=AsyncMock(return_value=True)) as fail,
    ):
        await document_processing_task({"job_try": 1, "max_tries": 3}, indexing.job_id)

    release.assert_not_awaited()
    fail.assert_awaited_once()
    assert fail.await_args.kwargs["error_code"] == "indexing_failed"


@pytest.mark.asyncio
async def test_parsing_ceiling_resume_executes_parser_without_same_progress_cas():
    parsing = _job(stage="parsing_local", status="running", progress=60, lease_version=4)
    indexing = _advanced(parsing, "indexing", 70)
    artifact = _artifact()
    parsed = SimpleNamespace(parser_engine=SimpleNamespace(value="mineru"))
    with (
        patch("app.workers.tasks._load_document_job", new=AsyncMock(return_value=parsing)),
        patch("app.workers.tasks._load_valid_markdown", new=AsyncMock(return_value=None)),
        patch("app.workers.tasks._advance_document_job", new=AsyncMock(return_value=indexing)) as advance,
        patch("app.workers.tasks._parse_stored_document", new=AsyncMock(return_value=parsed)) as parse,
        patch("app.workers.tasks._persist_parsed_markdown", new=AsyncMock(return_value=artifact)),
        patch("app.workers.tasks._build_document_index", new=AsyncMock(return_value=[])),
        patch("app.workers.tasks._commit_document_index", new=AsyncMock(return_value=_advanced(indexing, "indexing", 85))),
        patch("app.workers.tasks._complete_document_job", new=AsyncMock(return_value=True)),
    ):
        await document_processing_task({}, parsing.job_id)
    parse.assert_awaited_once()
    assert [call.kwargs["stage"] for call in advance.await_args_list] == ["indexing"]


@pytest.mark.asyncio
async def test_knowledge_indexing_ceiling_resume_executes_pageindex_without_same_progress_cas():
    indexing = _job(stage="indexing", job_type="knowledge", status="running", progress=84, lease_version=4)
    artifact = _artifact()
    indexed = _advanced(indexing, "indexing", 85)
    nodes = [SimpleNamespace(content="node")]
    with (
        patch("app.workers.tasks._load_document_job", new=AsyncMock(return_value=indexing)),
        patch("app.workers.tasks._load_valid_markdown", new=AsyncMock(return_value=artifact)),
        patch("app.workers.tasks._advance_document_job", new=AsyncMock()) as advance,
        patch("app.workers.tasks._build_document_index", new=AsyncMock(return_value=nodes)) as build,
        patch("app.workers.tasks._commit_document_index", new=AsyncMock(return_value=indexed)),
        patch("app.workers.tasks._run_resumable_document_inspection", new=AsyncMock(return_value=None)),
        patch("app.workers.tasks._complete_document_job", new=AsyncMock(return_value=True)),
    ):
        await document_processing_task({}, indexing.job_id)
    advance.assert_not_awaited()
    build.assert_awaited_once_with(artifact)
