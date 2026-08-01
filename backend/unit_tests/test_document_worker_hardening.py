from __future__ import annotations

import asyncio
import hashlib
import json
import sys
import types
import uuid
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

try:
    from app.agents import inspector as inspector_module
except ImportError:
    fake_pydantic_ai = sys.modules.setdefault("pydantic_ai", types.ModuleType("pydantic_ai"))
    fake_pydantic_ai.Agent = MagicMock()
    from app.agents import inspector as inspector_module
from app.lib.private_temp import FileIdentity
from app.workers import tasks


@dataclass
class _InspectionResult:
    overall_risk: str
    summary: str
    issues: list[dict]
    regulation_refs: list[str]
    total_quota_consumed: int = 0


if not hasattr(inspector_module, "InspectionResult"):
    inspector_module.InspectionResult = _InspectionResult

InspectionResult = inspector_module.InspectionResult


def _job(**changes):
    values = {
        "job_id": "doc_job_1",
        "user_id": uuid.UUID("12345678-1234-1234-1234-123456789012"),
        "job_type": "inspection",
        "source_path": "users/12345678-1234-1234-1234-123456789012/documents/source.pdf",
        "content_hash": "a" * 64,
        "file_type": "pdf",
        "parser_version": "1",
        "stage": "parsing_local",
        "status": "running",
        "progress": 30,
        "retry_count": 0,
        "lease_version": 2,
        "lease_owner": "worker-1",
        "mineru_task_id": None,
        "mineru_upload_state": None,
        "markdown_path": None,
        "markdown_hash": None,
        "parser_engine": None,
        "index_artifact_path": None,
        "index_artifact_hash": None,
        "inspection_call_state": None,
        "inspection_input_hash": None,
        "inspection_result_path": None,
        "inspection_result_hash": None,
        "knowledge_version_id": None,
        "inspection_record_id": 8,
    }
    values.update(changes)
    return SimpleNamespace(**values)


def test_historical_bidding_record_is_blocked_before_worker_inspection() -> None:
    with pytest.raises(ValueError, match="deprecated_application_scenario"):
        tasks._ensure_current_inspection_record(
            SimpleNamespace(document_type="bidding", classification_source="archived_legacy")
        )


@pytest.mark.asyncio
async def test_parser_uses_streamed_private_snapshot_validates_and_cleans(tmp_path: Path) -> None:
    private = tmp_path / "private.pdf"
    private.write_bytes(b"%PDF-1.7")
    stored = SimpleNamespace(path=private, identity=FileIdentity(1, 2))
    parsed = SimpleNamespace(content_hash="a" * 64)

    def validate_off_event_loop(*_args, **_kwargs):
        with pytest.raises(RuntimeError):
            asyncio.get_running_loop()

    with (
        patch("app.services.file_storage.copy_storage_to_private_temp", return_value=stored) as copy,
        patch("app.services.file_storage.validate_document_snapshot", side_effect=validate_off_event_loop) as validate,
        patch("app.workers.tasks.parse_document", new=AsyncMock(return_value=parsed)) as parse,
        patch("app.workers.tasks.secure_unlink", return_value=True) as unlink,
    ):
        result = await tasks._parse_stored_document(_job())
    copy.assert_called_once()
    validate.assert_called_once()
    parse.assert_awaited_once()
    unlink.assert_called_once_with(private, identity=stored.identity)
    assert result.result is parsed


@pytest.mark.asyncio
async def test_parser_callback_cas_moves_to_mineru_and_persists_remote_id(tmp_path: Path) -> None:
    private = tmp_path / "private.pdf"
    private.write_bytes(b"%PDF-1.7")
    job = _job(mineru_task_id="existing-1", mineru_upload_state="pending")
    mineru_stage = _job(stage="parsing_mineru", progress=50)
    persisted = _job(stage="parsing_mineru", progress=50, mineru_task_id="new-1")

    async def parser(path, suffix, **kwargs):
        assert kwargs["existing_mineru_task_id"] is None
        await kwargs["stage_callback"]("parsing_mineru")
        await kwargs["mineru_task_created_callback"]("new-1", "pending")
        await kwargs["mineru_task_created_callback"]("new-1", "uploaded")
        return SimpleNamespace(content_hash=job.content_hash)

    with (
        patch(
            "app.services.file_storage.copy_storage_to_private_temp",
            return_value=SimpleNamespace(path=private, identity=FileIdentity(1, 2)),
        ),
        patch("app.services.file_storage.validate_document_snapshot"),
        patch("app.workers.tasks.parse_document", new=AsyncMock(side_effect=parser)),
        patch("app.workers.tasks._advance_document_job", new=AsyncMock(return_value=mineru_stage)) as advance,
        patch("app.workers.tasks._persist_mineru_task", new=AsyncMock(side_effect=[persisted, persisted])) as persist,
        patch("app.workers.tasks.secure_unlink", return_value=True),
    ):
        result = await tasks._parse_stored_document(job)
    advance.assert_awaited_once_with(job, stage="parsing_mineru", progress=50)
    assert [call.args for call in persist.await_args_list] == [
        (mineru_stage, "new-1", "pending"),
        (persisted, "new-1", "uploaded"),
    ]
    assert result.job is persisted


@pytest.mark.asyncio
async def test_uploaded_mineru_batch_is_the_only_resumable_remote_id(tmp_path: Path) -> None:
    private = tmp_path / "private.pdf"
    private.write_bytes(b"%PDF-1.7")
    job = _job(mineru_task_id="existing-1", mineru_upload_state="uploaded")

    async def parser(_path, _suffix, **kwargs):
        assert kwargs["existing_mineru_task_id"] == "existing-1"
        return SimpleNamespace(content_hash=job.content_hash)

    with (
        patch("app.services.file_storage.copy_storage_to_private_temp", return_value=SimpleNamespace(path=private, identity=FileIdentity(1, 2))),
        patch("app.services.file_storage.validate_document_snapshot"),
        patch("app.workers.tasks.parse_document", new=AsyncMock(side_effect=parser)),
        patch("app.workers.tasks.secure_unlink", return_value=True),
    ):
        await tasks._parse_stored_document(job)


@pytest.mark.asyncio
async def test_pageindex_worker_uses_private_temp_strict_mode_and_cleans(tmp_path: Path) -> None:
    path = tmp_path / "index.md"
    path.write_text("", encoding="utf-8")
    identity = FileIdentity(1, 2)
    artifact = SimpleNamespace(markdown="# title\nbody")
    with (
        patch("app.workers.tasks.create_private_temp_file", return_value=path),
        patch("app.workers.tasks.snapshot_file_identity", return_value=identity),
        patch("app.services.page_indexer.build_index_nodes", new=AsyncMock(return_value=[])) as build,
        patch("app.workers.tasks.secure_unlink", return_value=True) as unlink,
    ):
        await tasks._build_document_index(artifact)
    build.assert_awaited_once_with(artifact.markdown, md_path=str(path), strict=True)
    unlink.assert_called_once_with(path, identity=identity)


@pytest.mark.asyncio
async def test_lease_heartbeat_cancels_long_call_when_lease_is_lost() -> None:
    cancelled = asyncio.Event()

    async def operation():
        try:
            await asyncio.sleep(10)
        finally:
            cancelled.set()

    with patch("app.workers.tasks._heartbeat_document_job", new=AsyncMock(side_effect=[True, False])) as heartbeat:
        with pytest.raises(tasks._LeaseLostError):
            await tasks._run_with_lease_heartbeat(_job(), operation(), interval_seconds=0.001)
    assert heartbeat.await_count == 2
    assert cancelled.is_set()


@pytest.mark.asyncio
async def test_inspection_prompt_is_built_from_pageindex_nodes_not_raw_markdown() -> None:
    nodes = [SimpleNamespace(path_label="第一章", content="结构化条款", node_type="section", position=1, parent_index=None)]
    raw_markdown = "RAW_MARKDOWN_MUST_NOT_BE_SENT"
    inspection_input = SimpleNamespace(
        project_id="p",
            application_scenario="contract",
        regulation_base={},
        taboo_words=[],
    )
    report = SimpleNamespace(regulation_refs=[], issues=[])
    with (
        patch("app.workers.tasks._load_owned_inspection_input", new=AsyncMock(return_value=inspection_input)),
        patch("app.agents.inspector.run_inspection", new=AsyncMock(return_value=report)) as run,
        patch("app.services.inspection_runner.sanitize_inspection_result_refs"),
    ):
        await tasks._run_owned_document_inspection(_job(), nodes)
    prompt = run.await_args.args[0]
    assert "结构化条款" in prompt
    assert raw_markdown not in prompt


@pytest.mark.asyncio
async def test_inspection_persists_started_input_identity_before_external_call_and_completed_report(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.core import config

    monkeypatch.setattr(config.settings, "data_encryption_key", "inspection-artifact-test-key")
    nodes = [SimpleNamespace(path_label="第一章", content="结构化条款", node_type="section", position=1)]
    inspection_input = SimpleNamespace(
        document_name="投标文件.pdf",
        project_id="project-1",
            application_scenario="contract",
        regulation_base={"sources": [{"title": "招标法", "content": "法规正文"}]},
        taboo_words=["绝对保证"],
    )
    report = InspectionResult("low", "通过", [], ["招标法"])
    started = _job(stage="inspecting", inspection_call_state="started")
    completed = _job(
        stage="inspecting",
        inspection_call_state="completed",
        inspection_result_path=f"users/{_job().user_id}/documents/report.json.enc",
        inspection_result_hash="d" * 64,
    )
    persisted_before_call = False

    async def persist(_job_value, *, state, input_hash, result_path=None, result_hash=None):
        nonlocal persisted_before_call
        if state == "started":
            persisted_before_call = True
            assert result_path is None and result_hash is None
            return started
        assert state == "completed"
        assert result_path.startswith(f"users/{_job().user_id}/documents/")
        assert result_path.endswith(".inspection.json.enc")
        from app.core.data_encryption import decrypt_sensitive_artifact

        assert result_hash == hashlib.sha256(decrypt_sensitive_artifact(saved.call_args.args[1])).hexdigest()
        return completed

    async def run(_text, _deps):
        assert persisted_before_call
        return report

    with (
        patch("app.workers.tasks._load_owned_inspection_input", new=AsyncMock(return_value=inspection_input)),
        patch("app.workers.tasks._persist_inspection_call_state", new=AsyncMock(side_effect=persist)) as persist_state,
        patch("app.agents.inspector.run_inspection", new=AsyncMock(side_effect=run)),
        patch("app.services.inspection_runner.sanitize_inspection_result_refs"),
        patch("app.services.file_storage.save_file") as saved,
    ):
        result = await tasks._run_resumable_document_inspection(_job(stage="inspecting"), nodes)

    started_hash = persist_state.await_args_list[0].kwargs["input_hash"]
    expected_payload = {
            "application_scenario": "contract",
        "nodes": [{"content": "结构化条款", "path": "第一章", "position": 1, "type": "section"}],
        "project_id": "project-1",
        "regulation_base": inspection_input.regulation_base,
        "taboo_words": ["绝对保证"],
    }
    expected = json.dumps(expected_payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    assert started_hash == hashlib.sha256(expected).hexdigest()
    from app.core.data_encryption import decrypt_sensitive_artifact

    saved_bytes = saved.call_args.args[1]
    assert "通过".encode() not in saved_bytes
    assert "招标法".encode() not in saved_bytes
    saved_report = json.loads(decrypt_sensitive_artifact(saved_bytes).decode("utf-8"))
    assert saved_report == {
        "classification": {
            "engineering_type_key": "general-engineering",
            "contract_type_key": "other",
            "confidence": "low",
            "evidence": [],
            "source": "fallback",
            "requires_confirmation": True,
        },
        "issues": [],
        "overall_risk": "low",
        "regulation_refs": ["招标法"],
        "summary": "通过",
    }
    assert "结构化条款".encode() not in saved_bytes
    assert result is not None and result.job is completed and result.report == report


@pytest.mark.asyncio
async def test_completed_valid_inspection_artifact_skips_supplier_call() -> None:
    report = InspectionResult("medium", "已恢复", [{"type": "format"}], [])
    completed = _job(
        stage="inspecting",
        inspection_call_state="completed",
        inspection_input_hash="e" * 64,
        inspection_result_path=f"users/{_job().user_id}/documents/report.json",
        inspection_result_hash="f" * 64,
    )
    inspection_input = SimpleNamespace(
        project_id="p", application_scenario="contract", regulation_base={}, taboo_words=[]
    )
    with (
        patch("app.workers.tasks._load_owned_inspection_input", new=AsyncMock(return_value=inspection_input)),
        patch("app.workers.tasks._inspection_input_hash", new=AsyncMock(return_value="e" * 64)),
        patch("app.workers.tasks._load_inspection_result_artifact", new=AsyncMock(return_value=report)),
        patch("app.agents.inspector.run_inspection", new=AsyncMock()) as run,
    ):
        result = await tasks._run_resumable_document_inspection(completed, [SimpleNamespace()])
    run.assert_not_awaited()
    assert result is not None and result.report == report and result.job is completed


@pytest.mark.asyncio
@pytest.mark.parametrize("call_state", ["started", "completed"])
async def test_started_without_result_or_corrupt_completed_artifact_safely_reruns(call_state: str) -> None:
    job = _job(
        stage="inspecting",
        inspection_call_state=call_state,
        inspection_input_hash="e" * 64,
        inspection_result_path=(f"users/{_job().user_id}/documents/bad.json" if call_state == "completed" else None),
        inspection_result_hash=("f" * 64 if call_state == "completed" else None),
    )
    started = _job(stage="inspecting", inspection_call_state="started", inspection_input_hash="e" * 64)
    completed = _job(stage="inspecting", inspection_call_state="completed")
    report = InspectionResult("low", "重跑完成", [], [])
    inspection_input = SimpleNamespace(
        project_id="p", application_scenario="contract", regulation_base={}, taboo_words=[]
    )
    with (
        patch("app.workers.tasks._load_owned_inspection_input", new=AsyncMock(return_value=inspection_input)),
        patch("app.workers.tasks._inspection_input_hash", new=AsyncMock(return_value="e" * 64)),
        patch("app.workers.tasks._load_inspection_result_artifact", new=AsyncMock(return_value=None)),
        patch("app.workers.tasks._persist_inspection_call_state", new=AsyncMock(side_effect=[started, completed])),
        patch("app.workers.tasks._run_owned_document_inspection", new=AsyncMock(return_value=report)) as run,
        patch("app.services.file_storage.save_file"),
    ):
        result = await tasks._run_resumable_document_inspection(job, [SimpleNamespace()])
    run.assert_awaited_once()
    assert result is not None and result.report == report


@pytest.mark.asyncio
async def test_lost_lease_after_inspection_deletes_new_report_and_never_returns_for_commit() -> None:
    started = _job(stage="inspecting", inspection_call_state="started", inspection_input_hash="e" * 64)
    report = InspectionResult("low", "孤儿结果", [], [])
    inspection_input = SimpleNamespace(
        project_id="p", application_scenario="contract", regulation_base={}, taboo_words=[]
    )
    with (
        patch("app.workers.tasks._load_owned_inspection_input", new=AsyncMock(return_value=inspection_input)),
        patch("app.workers.tasks._inspection_input_hash", new=AsyncMock(return_value="e" * 64)),
        patch("app.workers.tasks._persist_inspection_call_state", new=AsyncMock(side_effect=[started, None])),
        patch("app.workers.tasks._run_owned_document_inspection", new=AsyncMock(return_value=report)),
        patch("app.services.file_storage.save_file"),
        patch("app.services.file_storage.delete_file", return_value=True) as delete,
    ):
        result = await tasks._run_resumable_document_inspection(_job(stage="inspecting"), [SimpleNamespace()])
    assert result is None
    delete.assert_called_once()


@pytest.mark.asyncio
async def test_cancel_between_save_and_persist_deletes_new_inspection_result() -> None:
    started = _job(stage="inspecting", inspection_call_state="started", inspection_input_hash="e" * 64)
    report = InspectionResult("low", "孤儿结果", [], [])
    inspection_input = SimpleNamespace(
        project_id="p", application_scenario="contract", regulation_base={}, taboo_words=[]
    )
    saved_paths: list[str] = []

    def record_save(path, _content):
        saved_paths.append(path)

    with (
        patch("app.workers.tasks._load_owned_inspection_input", new=AsyncMock(return_value=inspection_input)),
        patch("app.workers.tasks._inspection_input_hash", new=AsyncMock(return_value="e" * 64)),
        patch("app.workers.tasks._persist_inspection_call_state", new=AsyncMock(side_effect=[started, asyncio.CancelledError()])),
        patch("app.workers.tasks._run_owned_document_inspection", new=AsyncMock(return_value=report)),
        patch("app.services.file_storage.save_file", side_effect=record_save),
        patch("app.services.file_storage.delete_file", return_value=True) as delete,
    ):
        with pytest.raises(asyncio.CancelledError):
            await tasks._run_resumable_document_inspection(_job(stage="inspecting"), [SimpleNamespace()])
    assert saved_paths
    delete.assert_called_once_with(saved_paths[0])


@pytest.mark.asyncio
async def test_inspection_result_loader_validates_hash_utf8_shape_and_whitelists_fields() -> None:
    content = json.dumps(
        {
            "overall_risk": "low",
            "summary": "有效报告",
            "issues": [],
            "regulation_refs": ["招标法"],
            "untrusted_extra": "discard me",
        },
        ensure_ascii=False,
    ).encode("utf-8")
    content_hash = hashlib.sha256(content).hexdigest()
    job = _job(
        inspection_result_path=f"users/{_job().user_id}/documents/report.json",
        inspection_result_hash=content_hash,
    )

    def read_off_event_loop(_path, _limit):
        with pytest.raises(RuntimeError):
            asyncio.get_running_loop()
        return content, content_hash

    with patch("app.workers.tasks._read_bounded_storage", side_effect=read_off_event_loop):
        report = await tasks._load_inspection_result_artifact(job)
    assert report == InspectionResult("low", "有效报告", [], ["招标法"])
    assert not hasattr(report, "untrusted_extra")

    malformed = b'{"overall_risk":"low","summary":1,"issues":[],"regulation_refs":[]}'
    with patch(
        "app.workers.tasks._read_bounded_storage",
        return_value=(malformed, hashlib.sha256(malformed).hexdigest()),
    ):
        assert await tasks._load_inspection_result_artifact(
            _job(
                inspection_result_path=job.inspection_result_path,
                inspection_result_hash=hashlib.sha256(malformed).hexdigest(),
            )
        ) is None


@pytest.mark.asyncio
async def test_index_artifact_storage_read_runs_off_event_loop() -> None:
    content = json.dumps(
        [{"node_type": "section", "path_label": "第一章", "content": "条款", "position": 1}],
        ensure_ascii=False,
    ).encode("utf-8")
    content_hash = hashlib.sha256(content).hexdigest()
    job = _job(
        index_artifact_path=f"users/{_job().user_id}/documents/index.json",
        index_artifact_hash=content_hash,
    )

    def read_off_event_loop(_path, _limit):
        with pytest.raises(RuntimeError):
            asyncio.get_running_loop()
        return content, content_hash

    with patch("app.workers.tasks._read_bounded_storage", side_effect=read_off_event_loop):
        artifact = await tasks._load_index_artifact(job)
    assert artifact is not None
    assert artifact.nodes[0].content == "条款"


@pytest.mark.asyncio
async def test_encrypted_index_loader_validates_plaintext_hash(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.core import config
    from app.core.data_encryption import encrypt_sensitive_artifact

    monkeypatch.setattr(config.settings, "data_encryption_key", "index-artifact-test-key")
    content = json.dumps(
        [{"node_type": "section", "path_label": "第一章", "content": "机密条款", "position": 1}],
        ensure_ascii=False,
    ).encode()
    envelope = encrypt_sensitive_artifact(content)
    job = _job(
        index_artifact_path=f"users/{_job().user_id}/documents/index.json.enc",
        index_artifact_hash=hashlib.sha256(content).hexdigest(),
    )

    with patch(
        "app.workers.tasks._read_bounded_storage",
        return_value=(envelope, hashlib.sha256(envelope).hexdigest()),
    ):
        artifact = await tasks._load_index_artifact(job)

    assert artifact is not None
    assert artifact.nodes[0].content == "机密条款"


@pytest.mark.asyncio
async def test_index_artifact_is_saved_as_encrypted_envelope_with_plaintext_hash(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.core import config
    from app.core.data_encryption import decrypt_sensitive_artifact

    monkeypatch.setattr(config.settings, "data_encryption_key", "index-artifact-test-key")
    node = SimpleNamespace(
        node_type="section",
        path_label="第一章",
        content="不得写入持久明文的机密条款",
        position=1,
        parent_index=None,
    )
    with patch("app.services.file_storage.save_file") as save:
        artifact = await tasks._persist_index_artifact(_job(), [node])

    saved_path, envelope = save.call_args.args
    plaintext = decrypt_sensitive_artifact(envelope)
    assert saved_path.endswith(".index.json.enc")
    assert node.content.encode() not in envelope
    assert artifact.content_hash == hashlib.sha256(plaintext).hexdigest()


@pytest.mark.asyncio
async def test_terminal_artifact_delete_failure_is_sanitized_and_does_not_raise(caplog) -> None:
    secret_path = f"users/{_job().user_id}/documents/secret-report.json.enc"
    with patch("app.services.file_storage.delete_file", side_effect=OSError(secret_path)):
        await tasks._delete_terminal_artifact(secret_path, artifact_kind="inspection_result")

    assert secret_path not in caplog.text
    assert "inspection_result" in caplog.text


@pytest.mark.asyncio
async def test_markdown_save_is_compensated_when_validation_fails() -> None:
    parsed = SimpleNamespace(
        content_hash="a" * 64,
        markdown="content",
        markdown_hash="b" * 64,
        parser_engine=SimpleNamespace(value="mineru"),
    )
    with (
        patch("app.services.file_storage.save_file"),
        patch("app.services.file_storage.delete_file", return_value=True) as delete,
        patch("app.workers.tasks.prepare_markdown_artifact", new=AsyncMock(side_effect=ValueError("bad"))),
        pytest.raises(ValueError, match="bad"),
    ):
        await tasks._persist_parsed_markdown(_job(), parsed)
    delete.assert_called_once()


@pytest.mark.asyncio
async def test_worker_deletes_new_index_artifact_when_commit_cas_is_lost() -> None:
    job = _job(stage="indexing", progress=84, job_type="knowledge")
    markdown = SimpleNamespace(
        markdown="content",
        markdown_path=f"users/{job.user_id}/documents/source.md",
    )
    index = SimpleNamespace(nodes=[], path=f"users/{job.user_id}/documents/index.json", content_hash="c" * 64)
    async def passthrough(_job, operation, **_kwargs):
        return await operation

    with (
        patch("app.workers.tasks._load_document_job", new=AsyncMock(return_value=job)),
        patch("app.workers.tasks._load_valid_markdown", new=AsyncMock(return_value=markdown)),
        patch("app.workers.tasks._load_index_artifact", new=AsyncMock(return_value=None)),
        patch("app.workers.tasks._build_document_index", new=AsyncMock(return_value=[])),
        patch("app.workers.tasks._run_with_lease_heartbeat", side_effect=passthrough),
        patch("app.workers.tasks._persist_index_artifact", new=AsyncMock(return_value=index)),
        patch("app.workers.tasks._commit_document_index", new=AsyncMock(return_value=None)),
        patch("app.services.file_storage.delete_file", return_value=True) as delete,
    ):
        await tasks.document_processing_task({}, job.job_id)
    delete.assert_called_once_with(index.path)
