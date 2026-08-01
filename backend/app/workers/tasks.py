from __future__ import annotations

import asyncio
import hashlib
import importlib
import json
import logging
import uuid
from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

from sqlalchemy import delete, select, update

from app.core.database import async_session
from app.core.config import settings
from app.core.data_encryption import decrypt_sensitive_artifact, encrypt_sensitive_artifact
from app.lib.private_temp import create_private_temp_file, secure_unlink, snapshot_file_identity
from app.models.document_job import DocumentProcessingJob
from app.models.knowledge import DocumentVersion, IndexNode, InspectionRecord, KnowledgeDocument
from app.services.agent_job_service import (
    mark_job_failed,
    mark_job_running,
    mark_job_succeeded,
)
from app.services.document_job_service import (
    MarkdownArtifact,
    _mark_document_job_succeeded_cas,
    cancel_document_job,
    clear_document_job_mineru_task,
    claim_document_job_lease,
    heartbeat_document_job_lease,
    mark_document_job_failed,
    mark_document_job_succeeded,
    persist_document_job_inspection_state,
    persist_document_job_mineru_task,
    prepare_markdown_artifact,
    release_document_job_lease,
    update_document_job_stage,
    validate_storage_identifier,
)
from app.services.document_parser import DocumentParseError, ParseResult, parse_document


_logger = logging.getLogger(__name__)

_DEFAULT_RULE_PACKAGE_KEY = "general-engineering-contract-rules:v1"
_ENGINEERING_TYPE_NAMES = {
    "building-construction": "房建施工",
    "municipal-road": "市政道路",
    "decoration-renovation": "装饰装修",
    "mechanical-electrical-installation": "机电安装",
    "steel-structure": "钢结构",
    "general-engineering": "通用工程",
}
_CONTRACT_TYPE_NAMES = {
    "labor-subcontract": "劳务分包",
    "professional-subcontract": "专业工程分包",
    "other": "其他类",
}


def _classification_record_values(classification: Any, regulation_base: dict[str, Any]) -> dict[str, Any]:
    """与同步审查共享分类快照写入契约。"""
    from app.services.inspection_runner import classification_record_values

    return classification_record_values(classification, regulation_base)


def _apply_worker_classification(
    record: InspectionRecord,
    classification: Any,
    regulation_base: dict[str, Any],
    *,
    input_complete: bool,
) -> None:
    """仅在未确认且输入完整时写入 worker 的新分类结果。"""
    if not input_complete or record.final_engineering_type or record.final_contract_type:
        return
    for field_name, value in _classification_record_values(classification, regulation_base).items():
        setattr(record, field_name, value)


@dataclass(frozen=True, slots=True)
class _DocumentJobSnapshot:
    job_id: str
    user_id: uuid.UUID
    job_type: str
    source_path: str
    content_hash: str
    file_type: str
    parser_version: str
    stage: str
    status: str
    progress: int
    retry_count: int
    dispatch_retry_count: int
    lease_version: int
    lease_owner: str | None
    mineru_task_id: str | None
    mineru_upload_state: str | None
    markdown_path: str | None
    markdown_hash: str | None
    parser_engine: str | None
    index_artifact_path: str | None
    index_artifact_hash: str | None
    inspection_call_state: str | None
    inspection_input_hash: str | None
    inspection_result_path: str | None
    inspection_result_hash: str | None
    knowledge_version_id: int | None
    inspection_record_id: int | None


class _DocumentWorkerBusinessError(Exception):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _snapshot(job: Any) -> _DocumentJobSnapshot:
    return _DocumentJobSnapshot(
        job_id=job.job_id,
        user_id=job.user_id,
        job_type=job.job_type,
        source_path=job.source_path,
        content_hash=job.content_hash,
        file_type=job.file_type,
        parser_version=job.parser_version,
        stage=job.stage,
        status=job.status,
        progress=job.progress,
        retry_count=job.retry_count,
        dispatch_retry_count=getattr(job, "dispatch_retry_count", 0),
        lease_version=job.lease_version,
        lease_owner=job.lease_owner,
        mineru_task_id=getattr(job, "mineru_task_id", None),
        mineru_upload_state=getattr(job, "mineru_upload_state", None),
        markdown_path=job.markdown_path,
        markdown_hash=job.markdown_hash,
        parser_engine=job.parser_engine,
        index_artifact_path=getattr(job, "index_artifact_path", None),
        index_artifact_hash=getattr(job, "index_artifact_hash", None),
        inspection_call_state=getattr(job, "inspection_call_state", None),
        inspection_input_hash=getattr(job, "inspection_input_hash", None),
        inspection_result_path=getattr(job, "inspection_result_path", None),
        inspection_result_hash=getattr(job, "inspection_result_hash", None),
        knowledge_version_id=job.knowledge_version_id,
        inspection_record_id=job.inspection_record_id,
    )


async def _load_document_job(
    job_id: str,
    *,
    lease_owner: str | None = None,
) -> _DocumentJobSnapshot | None:
    async with async_session() as db:
        if lease_owner is None:
            job = await db.scalar(select(DocumentProcessingJob).where(DocumentProcessingJob.job_id == job_id))
        else:
            async with db.begin():
                job = await claim_document_job_lease(
                    db,
                    job_id,
                    lease_owner=lease_owner,
                    lease_seconds=1860,
                )
        return _snapshot(job) if job is not None else None


async def _load_valid_markdown(job: _DocumentJobSnapshot) -> MarkdownArtifact | None:
    if not job.markdown_path or not job.markdown_hash or not job.parser_engine:
        return None
    try:
        return await prepare_markdown_artifact(
            job.user_id,
            job.markdown_path,
            parser_engine=job.parser_engine,
            expected_hash=job.markdown_hash,
        )
    except (OSError, ValueError):
        return None


async def _advance_document_job(
    job: _DocumentJobSnapshot,
    *,
    stage: str,
    progress: int,
    artifact: MarkdownArtifact | None = None,
) -> _DocumentJobSnapshot | None:
    async with async_session() as db:
        async with db.begin():
            updated = await update_document_job_stage(
                db,
                job.job_id,
                expected_stage=job.stage,
                expected_retry_count=job.retry_count,
                expected_lease_version=job.lease_version,
                lease_owner=getattr(job, "lease_owner", None),
                stage=stage,
                progress=progress,
                job_type=job.job_type,
                validated_markdown=artifact,
            )
            return _snapshot(updated) if updated is not None else None


@dataclass(frozen=True, slots=True)
class _ParsedDocument:
    result: ParseResult
    job: _DocumentJobSnapshot


async def _persist_mineru_task(
    job: _DocumentJobSnapshot,
    task_id: str,
    upload_state: str,
) -> _DocumentJobSnapshot | None:
    if job.lease_owner is None:
        return None
    async with async_session() as db:
        async with db.begin():
            updated = await persist_document_job_mineru_task(
                db,
                job.job_id,
                task_id=task_id,
                upload_state=upload_state,
                lease_owner=job.lease_owner,
                expected_lease_version=job.lease_version,
            )
            return _snapshot(updated) if updated is not None else None


async def _clear_mineru_task(job: _DocumentJobSnapshot) -> bool:
    if job.lease_owner is None:
        return False
    async with async_session() as db:
        async with db.begin():
            return await clear_document_job_mineru_task(
                db,
                job.job_id,
                lease_owner=job.lease_owner,
                expected_lease_version=job.lease_version,
            )


async def _parse_stored_document(job: _DocumentJobSnapshot) -> _ParsedDocument:
    from app.services.file_storage import (
        StoredFileValidationError,
        copy_storage_to_private_temp,
        validate_document_snapshot,
    )

    stored = None
    current = job
    try:
        stored = await asyncio.to_thread(
            copy_storage_to_private_temp,
            job.source_path,
            suffix=f".{job.file_type}",
            max_bytes=settings.document_max_parse_bytes,
            expected_hash=job.content_hash,
        )
        await asyncio.to_thread(
            validate_document_snapshot,
            stored.path,
            job.file_type,
            max_members=settings.mineru_max_zip_members,
            max_member_bytes=settings.document_max_parse_bytes,
            max_total_uncompressed_bytes=settings.mineru_max_zip_bytes,
            max_compression_ratio=settings.mineru_max_compression_ratio,
        )

        async def on_stage(stage: str) -> None:
            nonlocal current
            if stage != "parsing_mineru" or current.stage == stage:
                return
            updated = await _advance_document_job(current, stage=stage, progress=max(current.progress + 1, 50))
            if updated is None:
                raise _LeaseLostError
            current = updated

        async def on_task_created(task_id: str, upload_state: str) -> None:
            nonlocal current
            updated = await _persist_mineru_task(current, task_id, upload_state)
            if updated is None:
                raise _LeaseLostError
            current = updated

        result = await parse_document(
            stored.path,
            job.file_type,
            job_type=job.job_type,
            stage_callback=on_stage,
            existing_mineru_task_id=(
                job.mineru_task_id if job.mineru_upload_state == "uploaded" else None
            ),
            mineru_task_created_callback=on_task_created,
        )
        if result.content_hash != job.content_hash:
            raise DocumentParseError("file_read", "源文件内容已变化")
        return _ParsedDocument(result, current)
    except DocumentParseError as error:
        if current.mineru_upload_state == "pending" or (
            current.mineru_task_id is not None and error.code == "mineru_failed"
        ):
            await _clear_mineru_task(current)
        raise
    except StoredFileValidationError:
        raise DocumentParseError("file_read", "无法读取文档") from None
    finally:
        if stored is not None:
            secure_unlink(stored.path, identity=stored.identity)


def _parser_engine_name(result: ParseResult) -> str:
    value = result.parser_engine.value
    return "text" if value == "direct_text" else value


async def _persist_parsed_markdown(job: _DocumentJobSnapshot, result: ParseResult) -> MarkdownArtifact:
    from app.services.file_storage import delete_file, save_file

    if result.content_hash != job.content_hash:
        raise DocumentParseError("file_read", "源文件内容已变化")
    markdown_path = (
        f"users/{job.user_id}/documents/"
        f"{job.job_id}-{job.content_hash}-{job.parser_version}-{job.retry_count}-{job.lease_version}.md.enc"
    )
    content = result.markdown.encode("utf-8")
    await asyncio.to_thread(save_file, markdown_path, encrypt_sensitive_artifact(content))
    try:
        return await prepare_markdown_artifact(
            job.user_id,
            markdown_path,
            parser_engine=_parser_engine_name(result),
            expected_hash=result.markdown_hash,
        )
    except BaseException:
        await asyncio.to_thread(delete_file, markdown_path)
        raise


async def _delete_unreferenced_artifact(path: str | None) -> None:
    if not path:
        return
    from app.services.file_storage import delete_file

    await asyncio.to_thread(delete_file, path)


async def _delete_terminal_artifact(path: str | None, *, artifact_kind: str) -> None:
    """成功事务后的尽力删除；失败只记录不含路径的告警。"""
    if not path:
        return
    from app.services.file_storage import delete_file

    try:
        deleted = await asyncio.to_thread(delete_file, path)
    except Exception:
        _logger.warning("终态敏感产物删除失败，等待后续清理 kind=%s", artifact_kind)
        return
    if not deleted:
        _logger.warning("终态敏感产物未删除，等待后续清理 kind=%s", artifact_kind)


async def _build_document_index(artifact: MarkdownArtifact) -> list[Any]:
    from app.services.page_indexer import build_index_nodes

    temporary_path = create_private_temp_file(prefix="document-pageindex-", suffix=".md")
    identity = snapshot_file_identity(temporary_path)
    try:
        temporary_path.write_text(artifact.markdown, encoding="utf-8")
        return await build_index_nodes(artifact.markdown, md_path=str(temporary_path), strict=True)
    finally:
        secure_unlink(temporary_path, identity=identity)


@dataclass(frozen=True, slots=True)
class _IndexArtifact:
    nodes: list[Any]
    path: str
    content_hash: str


def _serialize_index_nodes(nodes: list[Any]) -> bytes:
    return json.dumps(
        [node.model_dump() if hasattr(node, "model_dump") else vars(node) for node in nodes],
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


async def _persist_index_artifact(job: _DocumentJobSnapshot, nodes: list[Any]) -> _IndexArtifact:
    from app.services.file_storage import save_file

    content = _serialize_index_nodes(nodes)
    if len(content) > settings.mineru_max_markdown_bytes:
        raise _DocumentWorkerBusinessError("indexing_failed")
    content_hash = hashlib.sha256(content).hexdigest()
    path = f"users/{job.user_id}/documents/{job.job_id}-{job.retry_count}-{job.lease_version}.index.json.enc"
    await asyncio.to_thread(save_file, path, encrypt_sensitive_artifact(content))
    return _IndexArtifact(nodes, path, content_hash)


async def _load_index_artifact(job: _DocumentJobSnapshot) -> _IndexArtifact | None:
    from app.services.page_indexer import IndexNodeCreate

    artifact_path = getattr(job, "index_artifact_path", None)
    artifact_hash = getattr(job, "index_artifact_hash", None)
    if not artifact_path or not artifact_hash:
        return None
    try:
        validate_storage_identifier(artifact_path, job.user_id)
        envelope, _ = await asyncio.to_thread(
            _read_bounded_storage,
            artifact_path,
            settings.mineru_max_markdown_bytes * 2 + 1024,
        )
        content = decrypt_sensitive_artifact(
            envelope,
            allow_legacy_plaintext=settings.environment != "production",
        )
        if len(content) > settings.mineru_max_markdown_bytes:
            raise ValueError
        actual_hash = hashlib.sha256(content).hexdigest()
        if actual_hash != artifact_hash:
            raise ValueError
        decoded = json.loads(content.decode("utf-8"))
        if not isinstance(decoded, list):
            raise ValueError
        nodes = [IndexNodeCreate.model_validate(item) for item in decoded]
        return _IndexArtifact(nodes, artifact_path, artifact_hash)
    except (OSError, UnicodeDecodeError, ValueError, json.JSONDecodeError):
        return None


def _read_bounded_storage(path: str, max_bytes: int) -> tuple[bytes, str]:
    from app.services.file_storage import iter_file_chunks

    content = bytearray()
    digest = hashlib.sha256()
    for chunk in iter_file_chunks(path):
        content.extend(chunk)
        digest.update(chunk)
        if len(content) > max_bytes:
            raise ValueError("artifact too large")
    return bytes(content), digest.hexdigest()


async def _owned_knowledge_version(db: Any, job: _DocumentJobSnapshot) -> DocumentVersion:
    version = await db.scalar(
        select(DocumentVersion)
        .join(KnowledgeDocument, KnowledgeDocument.id == DocumentVersion.document_id)
        .where(
            DocumentVersion.id == job.knowledge_version_id,
            KnowledgeDocument.owner_type == "user",
            KnowledgeDocument.owner_user_id == job.user_id,
        )
    )
    if version is None:
        raise _DocumentWorkerBusinessError("indexing_failed")
    return version


async def _commit_document_index(
    job: _DocumentJobSnapshot,
    artifact: MarkdownArtifact,
    nodes: list[Any] | _IndexArtifact,
) -> _DocumentJobSnapshot | None:
    index_artifact = nodes if isinstance(nodes, _IndexArtifact) else None
    if index_artifact is not None:
        node_values = index_artifact.nodes
    else:
        node_values = cast(list[Any], nodes)
    target_stage = "inspecting" if job.job_type == "inspection" else "indexing"
    target_progress = 90 if job.job_type == "inspection" else 85
    terminal_index_path: str | None = None
    committed: _DocumentJobSnapshot | None = None
    async with async_session() as db:
        async with db.begin():
            version = await _owned_knowledge_version(db, job) if job.job_type == "knowledge" else None
            if job.job_type == "inspection" and job.inspection_record_id is not None:
                owned_record = await db.scalar(
                    select(InspectionRecord).where(
                        InspectionRecord.id == job.inspection_record_id,
                        InspectionRecord.user_id == job.user_id,
                    )
                )
                if owned_record is None:
                    raise _DocumentWorkerBusinessError("inspection_failed")
            updated = await update_document_job_stage(
                db,
                job.job_id,
                expected_stage=job.stage,
                expected_retry_count=job.retry_count,
                expected_lease_version=job.lease_version,
                lease_owner=getattr(job, "lease_owner", None),
                stage=target_stage,
                progress=target_progress,
                job_type=job.job_type,
                validated_markdown=artifact,
            )
            if updated is None:
                return None
            if version is not None:
                await db.execute(delete(IndexNode).where(IndexNode.version_id == version.id))
                created: list[IndexNode] = []
                for node_data in node_values:
                    parent_id = None
                    if node_data.parent_index is not None and node_data.parent_index < len(created):
                        parent_id = created[node_data.parent_index].id
                    node = IndexNode(
                        version_id=version.id,
                        parent_id=parent_id,
                        node_type=node_data.node_type,
                        path_label=node_data.path_label,
                        content=node_data.content,
                        position=node_data.position,
                    )
                    db.add(node)
                    await db.flush()
                    created.append(node)
                version.markdown_path = artifact.markdown_path
                version.status = "completed"
                version.error_message = None
                await db.execute(
                    update(KnowledgeDocument)
                    .where(
                        KnowledgeDocument.id == version.document_id,
                        KnowledgeDocument.owner_type == "user",
                        KnowledgeDocument.owner_user_id == job.user_id,
                    )
                    .values(current_version_id=version.id)
                )
            if index_artifact is not None:
                if version is not None:
                    updated.index_artifact_path = None
                    updated.index_artifact_hash = None
                    terminal_index_path = index_artifact.path
                else:
                    updated.index_artifact_path = index_artifact.path
                    updated.index_artifact_hash = index_artifact.content_hash
            committed = _snapshot(updated)
    if terminal_index_path is not None:
        await _delete_terminal_artifact(terminal_index_path, artifact_kind="index")
    return committed


@dataclass(frozen=True, slots=True)
class _InspectionInput:
    document_name: str
    project_id: str
    application_scenario: str
    taboo_words: list[str]
    regulation_base: dict[str, Any]
    classification_confirmed: bool = False


async def _load_owned_inspection_input(job: _DocumentJobSnapshot) -> _InspectionInput:
    from app.services.inspection_runner import load_user_taboo_words
    from app.services.knowledge_retrieval import retrieve_regulation_base

    async with async_session() as db:
        record = None
        if job.inspection_record_id is not None:
            record = await db.scalar(
                select(InspectionRecord).where(
                    InspectionRecord.id == job.inspection_record_id,
                    InspectionRecord.user_id == job.user_id,
                )
            )
            if record is None:
                raise _DocumentWorkerBusinessError("inspection_failed")
            try:
                _ensure_current_inspection_record(record)
            except ValueError as exc:
                raise _DocumentWorkerBusinessError(str(exc)) from exc
        scenario = record.document_type if record is not None and record.document_type == "contract" else "contract"
        engineering_type_key = (
            (record.final_engineering_type or record.detected_engineering_type)
            if record is not None else "general-engineering"
        )
        contract_type_key = (
            (record.final_contract_type or record.detected_contract_type)
            if record is not None else "other"
        )
        taboo_words = await load_user_taboo_words(db, job.user_id)
        regulation_base = await retrieve_regulation_base(
            db,
            user_id=job.user_id,
            application_scenario=scenario,
            limit=8,
            engineering_type_key=engineering_type_key,
            contract_type_key=contract_type_key,
        )
        return _InspectionInput(
            document_name=(record.document_name if record is not None else Path(job.source_path).name),
            project_id=(record.project_id if record is not None else None) or "default",
            application_scenario=scenario,
            taboo_words=taboo_words,
            regulation_base=regulation_base,
            classification_confirmed=bool(
                record is not None
                and (record.final_engineering_type or record.final_contract_type)
            ),
        )


async def _run_owned_document_inspection(
    job: _DocumentJobSnapshot,
    nodes: list[Any],
    *,
    inspection_input: _InspectionInput | None = None,
    fallback_text: str | None = None,
) -> Any:
    from app.agents.inspector import run_inspection
    from app.core.deps import InspectionDeps
    from app.services.inspection_runner import allowed_regulation_refs, sanitize_inspection_result_refs

    inspection_input = inspection_input or await _load_owned_inspection_input(job)
    if nodes:
        structured_text = json.dumps(
            [
                {
                    "path": node.path_label,
                    "type": node.node_type,
                    "position": node.position,
                    "content": node.content,
                }
                for node in nodes
            ],
            ensure_ascii=False,
            separators=(",", ":"),
        )
    else:
        structured_text = fallback_text or ""
    async with async_session() as db:
        deps = InspectionDeps(
            project_id=inspection_input.project_id,
            user_id=str(job.user_id),
            document_name=getattr(inspection_input, "document_name", Path(job.source_path).name),
            application_scenario=inspection_input.application_scenario,
            regulation_base=inspection_input.regulation_base,
            taboo_words=inspection_input.taboo_words or None,
            db=db,
            usage_attempt_id=f"job:{job.job_id}",
            usage_input_hash=hashlib.sha256(structured_text.encode("utf-8")).hexdigest(),
        )
        result = await run_inspection(structured_text, deps)
        await db.commit()
    sanitize_inspection_result_refs(
        result,
        allowed_regulation_refs(inspection_input.regulation_base, inspection_input.taboo_words),
    )
    return result


def _inspection_payload(inspection_input: _InspectionInput, nodes: list[Any]) -> dict[str, Any]:
    return {
        "application_scenario": inspection_input.application_scenario,
        "nodes": [
            {
                "content": node.content,
                "path": node.path_label,
                "position": node.position,
                "type": node.node_type,
            }
            for node in nodes
        ],
        "project_id": inspection_input.project_id,
        "regulation_base": inspection_input.regulation_base,
        "taboo_words": inspection_input.taboo_words,
    }


async def _inspection_input_hash(
    job: _DocumentJobSnapshot,
    nodes: list[Any],
    *,
    inspection_input: _InspectionInput | None = None,
) -> str:
    owned_input = inspection_input or await _load_owned_inspection_input(job)
    content = json.dumps(
        _inspection_payload(owned_input, nodes),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(content).hexdigest()


async def _persist_inspection_call_state(
    job: _DocumentJobSnapshot,
    *,
    state: str,
    input_hash: str,
    result_path: str | None = None,
    result_hash: str | None = None,
) -> _DocumentJobSnapshot | None:
    if job.lease_owner is None:
        return None
    async with async_session() as db:
        async with db.begin():
            updated = await persist_document_job_inspection_state(
                db,
                job.job_id,
                user_id=job.user_id,
                state=state,
                input_hash=input_hash,
                lease_owner=job.lease_owner,
                expected_lease_version=job.lease_version,
                result_path=result_path,
                result_hash=result_hash,
            )
            return _snapshot(updated) if updated is not None else None


def _serialize_inspection_result(report: Any, *, classification: Any | None = None) -> bytes:
    payload: dict[str, Any] = {
        "issues": report.issues,
        "overall_risk": report.overall_risk,
        "regulation_refs": report.regulation_refs,
        "summary": report.summary,
    }
    if classification is not None:
        payload["classification"] = {
            "engineering_type_key": classification.engineering_type_key,
            "contract_type_key": classification.contract_type_key,
            "confidence": classification.confidence,
            "evidence": classification.evidence,
            "source": classification.source,
            "requires_confirmation": classification.requires_confirmation,
        }
    return json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


async def _load_inspection_result_artifact(job: _DocumentJobSnapshot) -> Any | None:
    inspector_module = importlib.import_module("app.agents.inspector")
    AgentInspectionResult: Any = getattr(inspector_module, "InspectionResult", SimpleNamespace)
    from app.services.contract_classifier import (
        CONTRACT_TYPE_KEYS,
        ContractClassification,
        ENGINEERING_TYPE_KEYS,
    )

    if not job.inspection_result_path or not job.inspection_result_hash:
        return None
    try:
        validate_storage_identifier(job.inspection_result_path, job.user_id)
        envelope, _ = await asyncio.to_thread(
            _read_bounded_storage,
            job.inspection_result_path,
            settings.mineru_max_markdown_bytes * 2 + 1024,
        )
        content = decrypt_sensitive_artifact(
            envelope,
            allow_legacy_plaintext=settings.environment != "production",
        )
        if len(content) > settings.mineru_max_markdown_bytes:
            raise ValueError
        actual_hash = hashlib.sha256(content).hexdigest()
        if actual_hash != job.inspection_result_hash:
            raise ValueError
        data = json.loads(content.decode("utf-8"))
        if not isinstance(data, dict):
            raise ValueError
        overall_risk = data["overall_risk"]
        summary = data["summary"]
        issues = data["issues"]
        regulation_refs = data["regulation_refs"]
        if (
            not isinstance(overall_risk, str)
            or not isinstance(summary, str)
            or not isinstance(issues, list)
            or any(not isinstance(issue, dict) for issue in issues)
            or not isinstance(regulation_refs, list)
            or any(not isinstance(ref, str) for ref in regulation_refs)
        ):
            raise ValueError
        report = AgentInspectionResult(
            overall_risk=overall_risk,
            summary=summary,
            issues=issues,
            regulation_refs=regulation_refs,
        )
        classification_data = data.get("classification")
        if isinstance(classification_data, dict):
            engineering = classification_data.get("engineering_type_key")
            contract = classification_data.get("contract_type_key")
            confidence = classification_data.get("confidence")
            evidence = classification_data.get("evidence")
            source = classification_data.get("source")
            requires_confirmation = classification_data.get("requires_confirmation")
            if (
                isinstance(engineering, str)
                and isinstance(contract, str)
                and engineering in ENGINEERING_TYPE_KEYS
                and contract in CONTRACT_TYPE_KEYS
                and confidence in {"high", "medium", "low"}
                and isinstance(evidence, list)
                and all(isinstance(item, str) for item in evidence)
                and source in {"rule", "model", "fallback", "manual"}
                and isinstance(requires_confirmation, bool)
            ):
                setattr(report, "classification", ContractClassification(
                    engineering_type_key=engineering,
                    contract_type_key=contract,
                    confidence=confidence,
                    evidence=evidence,
                    source=source,
                    requires_confirmation=requires_confirmation,
                ))
        return report
    except (KeyError, OSError, UnicodeDecodeError, ValueError, json.JSONDecodeError):
        return None


@dataclass(frozen=True, slots=True)
class _ResumableInspection:
    job: _DocumentJobSnapshot
    report: Any
    classification: Any | None = None


async def _run_resumable_document_inspection(
    job: _DocumentJobSnapshot,
    nodes: list[Any],
    *,
    fallback_text: str | None = None,
) -> _ResumableInspection | None:
    from app.services.file_storage import delete_file, save_file

    inspection_input = await _load_owned_inspection_input(job)
    input_hash = await _inspection_input_hash(job, nodes, inspection_input=inspection_input)
    if job.inspection_call_state == "completed" and job.inspection_input_hash == input_hash:
        recovered = await _load_inspection_result_artifact(job)
        if recovered is not None:
            return _ResumableInspection(job, recovered)

    started = await _persist_inspection_call_state(job, state="started", input_hash=input_hash)
    if started is None:
        return None
    classification = None
    if inspection_input.application_scenario == "contract" and (
        not inspection_input.classification_confirmed and fallback_text and fallback_text.strip()
    ):
        from app.services.inspection_runner import classify_inspection_document
        from app.services.contract_classifier import screen_contract_rules

        document_name = getattr(inspection_input, "document_name", Path(job.source_path).name)
        classification = await classify_inspection_document(
            document_name=document_name,
            text=fallback_text or "",
            rule_screening=screen_contract_rules(
                filename=document_name,
                text=fallback_text or "",
            ),
        )
    report = await _run_owned_document_inspection(
        started,
        nodes,
        inspection_input=inspection_input,
        fallback_text=fallback_text,
    )
    content = _serialize_inspection_result(report, classification=classification)
    result_hash = hashlib.sha256(content).hexdigest()
    result_path = f"users/{job.user_id}/documents/{job.job_id}-{uuid.uuid4().hex}.inspection.json.enc"
    await asyncio.to_thread(save_file, result_path, encrypt_sensitive_artifact(content))
    try:
        completed = await _persist_inspection_call_state(
            started,
            state="completed",
            input_hash=input_hash,
            result_path=result_path,
            result_hash=result_hash,
        )
    except BaseException:
        await asyncio.to_thread(delete_file, result_path)
        raise
    if completed is None:
        await asyncio.to_thread(delete_file, result_path)
        return None
    return _ResumableInspection(completed, report, classification)


async def _commit_inspection_success(
    job: _DocumentJobSnapshot,
    artifact: MarkdownArtifact,
    report: Any,
    classification: Any | None = None,
) -> bool:
    from app.core.data_encryption import encrypt_text
    from app.services.inspection_runner import DOCUMENT_TYPE_LABELS

    inspection_input = await _load_owned_inspection_input(job)
    record: InspectionRecord | None = None
    async with async_session() as db:
        async with db.begin():
            completed = await _mark_document_job_succeeded_cas(
                db,
                job.job_id,
                expected_stage=job.stage,
                expected_retry_count=job.retry_count,
                expected_lease_version=job.lease_version,
                lease_owner=getattr(job, "lease_owner", None),
                artifact=artifact,
                job_type=job.job_type,
            )
            if completed is None:
                return False
            if job.inspection_record_id is not None:
                record = await db.scalar(
                    select(InspectionRecord).where(
                        InspectionRecord.id == job.inspection_record_id,
                        InspectionRecord.user_id == job.user_id,
                    )
                )
                if record is None:
                    raise _DocumentWorkerBusinessError("inspection_failed")
            else:
                record = InspectionRecord(user_id=job.user_id, document_name=inspection_input.document_name)
                db.add(record)
                await db.flush()
                completed.inspection_record_id = record.id
            record.document_name = inspection_input.document_name
            record.document_type = inspection_input.application_scenario
            record.document_type_label = DOCUMENT_TYPE_LABELS.get(
                inspection_input.application_scenario,
                inspection_input.application_scenario,
            )
            record.project_id = inspection_input.project_id
            record.status = "completed"
            record.overall_risk = report.overall_risk
            record.summary = report.summary
            record.issues = report.issues
            record.regulation_refs = report.regulation_refs
            record.text_preview = artifact.markdown[:500]
            record.parsed_content = encrypt_text(artifact.markdown)
            record.quota_consumed = max(1, len(artifact.markdown) // 500)
            actual_classification = classification or getattr(report, "classification", None)
            if actual_classification is not None:
                _apply_worker_classification(
                    record,
                    actual_classification,
                    inspection_input.regulation_base,
                    input_complete=classification is not None,
                )
    await _delete_terminal_artifact(job.index_artifact_path, artifact_kind="index")
    await _delete_terminal_artifact(job.inspection_result_path, artifact_kind="inspection_result")
    return True


async def _complete_document_job(job: _DocumentJobSnapshot, artifact: MarkdownArtifact) -> bool:
    async with async_session() as db:
        completed = await mark_document_job_succeeded(
            db,
            job.job_id,
            expected_stage=job.stage,
            expected_retry_count=job.retry_count,
            expected_lease_version=job.lease_version,
            lease_owner=getattr(job, "lease_owner", None),
            artifact=artifact,
            job_type=job.job_type,
        )
        succeeded = completed is not None
    if succeeded:
        await _delete_terminal_artifact(job.index_artifact_path, artifact_kind="index")
        await _delete_terminal_artifact(job.inspection_result_path, artifact_kind="inspection_result")
    return succeeded


async def _fail_document_job(job: _DocumentJobSnapshot, *, error_code: str) -> bool:
    async with async_session() as db:
        async with db.begin():
            failed = await mark_document_job_failed(
                db,
                job.job_id,
                expected_stage=job.stage,
                expected_retry_count=job.retry_count,
                expected_lease_version=job.lease_version,
                lease_owner=getattr(job, "lease_owner", None),
                error_code=error_code,
            )
            if failed is not None and failed.inspection_record_id is not None:
                record = await db.scalar(
                    select(InspectionRecord).where(
                        InspectionRecord.id == failed.inspection_record_id,
                        InspectionRecord.user_id == failed.user_id,
                    )
                )
                if record is not None:
                    record.status = "failed"
    if failed is not None:
        await _delete_terminal_artifact(job.index_artifact_path, artifact_kind="index")
        await _delete_terminal_artifact(job.inspection_result_path, artifact_kind="inspection_result")
    return failed is not None


async def _cleanup_cancelled_document_job(job: _DocumentJobSnapshot) -> None:
    # Parser and PageIndex helpers own their temporary files; yielding lets their
    # cancellation-safe finally blocks finish before ARQ observes cancellation.
    await asyncio.sleep(0)


async def _heartbeat_document_job(job: _DocumentJobSnapshot) -> bool:
    owner = getattr(job, "lease_owner", None)
    if owner is None:
        return True
    async with async_session() as db:
        async with db.begin():
            return await heartbeat_document_job_lease(
                db,
                job.job_id,
                lease_owner=owner,
                expected_lease_version=job.lease_version,
                lease_seconds=1860,
            )


class _LeaseLostError(RuntimeError):
    pass


async def _run_with_lease_heartbeat(
    job: _DocumentJobSnapshot,
    operation: Any,
    *,
    interval_seconds: float = 30,
) -> Any:
    task = asyncio.create_task(operation)
    try:
        if not await _heartbeat_document_job(job):
            raise _LeaseLostError
        while True:
            done, _ = await asyncio.wait({task}, timeout=interval_seconds)
            if done:
                return await task
            if not await _heartbeat_document_job(job):
                raise _LeaseLostError
    except BaseException:
        if not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        raise


async def _release_document_job(job: _DocumentJobSnapshot, *, redispatch: bool) -> bool:
    owner = getattr(job, "lease_owner", None)
    if owner is None:
        return True
    async with async_session() as db:
        async with db.begin():
            return await release_document_job_lease(
                db,
                job.job_id,
                lease_owner=owner,
                expected_lease_version=job.lease_version,
                redispatch=redispatch,
            )


async def _cancel_document_job(job: _DocumentJobSnapshot) -> bool:
    owner = getattr(job, "lease_owner", None)
    if owner is None:
        return False
    async with async_session() as db:
        async with db.begin():
            cancelled = await cancel_document_job(
                db,
                job.job_id,
                lease_owner=owner,
                expected_lease_version=job.lease_version,
            )
            return cancelled is not None


def _is_final_attempt(ctx: dict[str, Any], job: _DocumentJobSnapshot) -> bool:
    max_tries = int(ctx.get("max_tries", 3))
    arq_attempt = int(ctx.get("job_try", max_tries))
    persisted_attempt = job.dispatch_retry_count + 1
    return arq_attempt >= max_tries or persisted_attempt >= max_tries


def _failure_code(error: BaseException, job: _DocumentJobSnapshot) -> str:
    if isinstance(error, DocumentParseError):
        return error.code
    if isinstance(error, _DocumentWorkerBusinessError):
        return error.code
    if job.stage == "indexing":
        return "indexing_failed"
    if job.stage == "inspecting":
        return "inspection_failed"
    return "processing_failed"


async def document_processing_task(ctx: dict[str, Any], job_id: str) -> None:
    """Run one recoverable document pipeline without holding DB transactions over external calls."""
    lease_owner = f"document-worker:{uuid.uuid4().hex}"
    job = await _load_document_job(job_id, lease_owner=lease_owner)
    if job is None or job.status in {"succeeded", "failed", "cancelled"}:
        return
    current = job
    unreferenced_paths: set[str] = set()
    try:
        artifact = await _load_valid_markdown(current)
        index_artifact = await _load_index_artifact(current)
        if artifact is None:
            if current.stage == "queued":
                claimed = await _advance_document_job(current, stage="detecting", progress=10)
                if claimed is None:
                    return
                current = claimed
            parsing_stage = current.stage if current.stage in {"parsing_local", "parsing_mineru"} else "parsing_local"
            parsing_progress = min(max(current.progress + 1, 30), 60) if parsing_stage == current.stage else 30
            if parsing_stage != current.stage or parsing_progress > current.progress:
                claimed = await _advance_document_job(current, stage=parsing_stage, progress=parsing_progress)
                if claimed is None:
                    return
                current = claimed
            parsed_execution = await _run_with_lease_heartbeat(current, _parse_stored_document(current))
            if isinstance(parsed_execution, _ParsedDocument):
                parsed = parsed_execution.result
                current = parsed_execution.job
            else:
                # Compatibility for injected legacy test doubles.
                parsed = parsed_execution
            artifact = await _persist_parsed_markdown(current, parsed)
            unreferenced_paths.add(artifact.markdown_path)

            if current.job_type == "inspection":
                claimed = await _advance_document_job(current, stage="inspecting", progress=90, artifact=artifact)
                if claimed is None:
                    return
                current = claimed
                inspection = await _run_with_lease_heartbeat(
                    current,
                    _run_resumable_document_inspection(current, [], fallback_text=artifact.markdown),
                )
                if inspection is None:
                    return
                current = inspection.job
                if getattr(inspection, "classification", None) is None:
                    await _commit_inspection_success(current, artifact, inspection.report)
                else:
                    await _commit_inspection_success(
                        current, artifact, inspection.report, inspection.classification
                    )
                return

        if current.job_type == "inspection":
            inspecting_progress = 90 if current.stage != "inspecting" else min(current.progress + 1, 99)
            if current.stage != "inspecting" or inspecting_progress > current.progress:
                claimed = await _advance_document_job(
                    current,
                    stage="inspecting",
                    progress=inspecting_progress,
                    artifact=artifact,
                )
                if claimed is None:
                    return
                current = claimed
            inspection = await _run_with_lease_heartbeat(
                current,
                _run_resumable_document_inspection(current, [], fallback_text=artifact.markdown),
            )
            if inspection is None:
                return
            current = inspection.job
            if getattr(inspection, "classification", None) is None:
                await _commit_inspection_success(current, artifact, inspection.report)
            else:
                await _commit_inspection_success(
                    current, artifact, inspection.report, inspection.classification
                )
            return

        if current.stage == "indexing" and current.progress >= 85:
            await _complete_document_job(current, artifact)
            return

        indexing_ceiling = 84
        indexing_progress = (
            min(max(current.progress + 1, 70), indexing_ceiling)
            if current.stage == "indexing"
            else 70
        )
        if current.stage != "indexing" or indexing_progress > current.progress:
            claimed = await _advance_document_job(
                current,
                stage="indexing",
                progress=indexing_progress,
                artifact=artifact,
            )
            if claimed is None:
                if artifact.markdown_path in unreferenced_paths:
                    await _delete_unreferenced_artifact(artifact.markdown_path)
                return
            current = claimed
            unreferenced_paths.discard(artifact.markdown_path)
        nodes = await _run_with_lease_heartbeat(current, _build_document_index(artifact))
        index_artifact = await _persist_index_artifact(current, nodes)
        unreferenced_paths.add(index_artifact.path)
        indexed = await _commit_document_index(current, artifact, index_artifact)
        if indexed is None:
            await _delete_unreferenced_artifact(index_artifact.path)
            return
        current = indexed
        unreferenced_paths.discard(index_artifact.path)
        if current.job_type == "inspection":
            inspection = await _run_with_lease_heartbeat(
                current,
                _run_resumable_document_inspection(current, index_artifact.nodes, fallback_text=artifact.markdown),
            )
            if inspection is None:
                return
            current = inspection.job
            if getattr(inspection, "classification", None) is None:
                await _commit_inspection_success(current, artifact, inspection.report)
            else:
                await _commit_inspection_success(
                    current, artifact, inspection.report, inspection.classification
                )
        else:
            await _complete_document_job(current, artifact)
    except _LeaseLostError:
        for path in unreferenced_paths:
            await asyncio.shield(_delete_unreferenced_artifact(path))
        return
    except asyncio.CancelledError:
        for path in unreferenced_paths:
            await asyncio.shield(_delete_unreferenced_artifact(path))
        await asyncio.shield(_cleanup_cancelled_document_job(current))
        if ctx.get("cancel_requested"):
            await asyncio.shield(_cancel_document_job(current))
        elif _is_final_attempt(ctx, current):
            await asyncio.shield(_fail_document_job(current, error_code="parse_timeout"))
        else:
            await asyncio.shield(_release_document_job(current, redispatch=True))
        raise
    except Exception as error:
        for path in unreferenced_paths:
            await _delete_unreferenced_artifact(path)
        if (
            current.mineru_upload_state == "pending"
            or current.mineru_task_id is not None
            and isinstance(error, DocumentParseError)
            and error.code == "mineru_failed"
        ):
            await _clear_mineru_task(current)
        if _is_final_attempt(ctx, current):
            await _fail_document_job(current, error_code=_failure_code(error, current))
        else:
            await _release_document_job(current, redispatch=True)
            raise


def _require_contract_scenario(payload: dict[str, Any]) -> str:
    scenario = payload.get("application_scenario", "contract")
    if scenario == "bidding":
        raise ValueError("deprecated_application_scenario")
    if scenario != "contract":
        raise ValueError("invalid_application_scenario")
    return "contract"


def _ensure_current_inspection_record(record: Any) -> None:
    if record.document_type == "bidding" or record.classification_source == "archived_legacy":
        raise ValueError("deprecated_application_scenario")


async def _run_inspect(ctx, job_id: str) -> dict:
    """从 job.input_payload 取文档正文，运行体检，返回结果摘要。"""
    from sqlalchemy import select

    from app.services.inspection_runner import execute_inspection
    from app.models.api_keys import AgentJob

    async with async_session() as db:
        job = (await db.execute(select(AgentJob).where(AgentJob.job_id == job_id))).scalar_one_or_none()
        if job is None:
            raise ValueError(f"job_not_found: {job_id}")

        payload = job.input_payload or {}
        text = payload.get("text")
        if not text or len(str(text).strip()) < 10:
            raise ValueError("input_payload.text 缺失或过短，无法体检")

        report = await execute_inspection(
            db=db,
            user_id=job.user_id,
            document_name=payload.get("document_name", "未命名文档"),
            text=text,
            project_id=payload.get("project_id", "default"),
            application_scenario=_require_contract_scenario(payload),
            taboo_words_input=payload.get("taboo_words", ""),
            engineering_type_key=payload.get("engineering_type_key"),
            contract_type_key=payload.get("contract_type_key"),
        )
        return {
            "record_id": report.id,
            "overall_risk": report.overall_risk,
            "document_name": report.document_name,
        }


async def _run_parse(ctx, job_id: str) -> dict:
    """从 job.input_payload 解析正文或派发统一文档解析任务。

    - 含 ``content_base64``（文件）时：保存到受控存储并创建 ``agent_parse``
      文档任务，立即返回 ``document_job_id`` 供客户端轮询
      ``/document-jobs/{id}``。文件解析复用统一解析服务（MinerU），不再在
      worker 内联 MarkItDown 同步解析。
    - 仅含纯 ``text`` 时：纯文本无需 MinerU，仍走同步解析并创建可体检的 pending record。
    """
    import base64

    from sqlalchemy import select

    from app.api.v1.inspection import _inspection_file_format, _validate_inspection_filename
    from app.core.file_magic import validate_file_magic
    from app.models.api_keys import AgentJob
    from app.services.document_job_service import create_document_job, prepare_source_artifact
    from app.services.file_storage import delete_file, save_file
    from app.services.inspection_runner import create_pending_inspection_record
    from app.services.inspection_runner import classify_inspection_document
    from app.services.contract_classifier import screen_contract_rules

    async with async_session() as db:
        job = (await db.execute(select(AgentJob).where(AgentJob.job_id == job_id))).scalar_one_or_none()
        if job is None:
            raise ValueError(f"job_not_found: {job_id}")

        payload = job.input_payload or {}
        _require_contract_scenario(payload)
        document_name = payload.get("document_name") or payload.get("filename") or "未命名文档.txt"
        text = payload.get("text")

        if text:
            # 纯文本无需 MinerU，沿用同步解析直达 pending record。
            text = str(text)
            if len(text.strip()) < 10:
                raise ValueError("input_payload.text 缺失或过短，无法解析")
            classification = await classify_inspection_document(
                document_name=document_name,
                text=text,
                rule_screening=screen_contract_rules(filename=document_name, text=text),
            )
            record = await create_pending_inspection_record(
                db=db,
                user_id=job.user_id,
                document_name=document_name,
                document_type="contract",
                document_type_label="合同",
                text=text,
                project_id=payload.get("project_id", "default"),
                classification=classification,
            )
            return {
                "record_id": record.id,
                "document_name": document_name,
                "document_type": "contract",
                "document_type_label": "合同",
                "text_preview": text[:500],
                "classification": {
                    "engineering_type_key": classification.engineering_type_key,
                    "contract_type_key": classification.contract_type_key,
                    "confidence": classification.confidence,
                    "evidence": classification.evidence,
                    "source": classification.source,
                    "requires_confirmation": classification.requires_confirmation,
                },
            }

        encoded_content = payload.get("content_base64")
        if not encoded_content:
            raise ValueError("input_payload.text 缺失或过短，无法解析")

        # 文件 payload 交给统一文档解析服务，不在 worker 内联解析。
        try:
            content = base64.b64decode(str(encoded_content), validate=True)
        except Exception as exc:
            raise ValueError("input_payload.content_base64 不是有效的 base64") from exc
        _validate_inspection_filename(document_name)
        validate_file_magic(document_name, content)

        file_ext = _inspection_file_format(document_name)
        content_hash = hashlib.sha256(content).hexdigest()
        source_path = f"users/{job.user_id}/documents/{uuid.uuid4().hex}.{file_ext}"
        save_file(source_path, content)

        try:
            source = await prepare_source_artifact(job.user_id, source_path, content_hash)
            async with db.begin():
                doc_job = await create_document_job(
                    db,
                    source=source,
                    job_type="agent_parse",
                    file_type=file_ext,
                )
                document_job_id = doc_job.job_id
        except Exception:
            delete_file(source_path)
            raise

        return {
            "document_job_id": document_job_id,
            "document_name": document_name,
            "file_type": file_ext,
        }


async def _run_knowledge_upload(ctx, job_id: str) -> dict:
    """从 job.input_payload 上传知识库文件，复用现有知识库入库 handler。"""
    import base64
    import io

    from sqlalchemy import select
    from starlette.datastructures import UploadFile

    from app.api.v1.knowledge import upload_and_ingest
    from app.models.api_keys import AgentJob

    async with async_session() as db:
        job = (await db.execute(select(AgentJob).where(AgentJob.job_id == job_id))).scalar_one_or_none()
        if job is None:
            raise ValueError(f"job_not_found: {job_id}")

        payload = job.input_payload or {}
        encoded_content = payload.get("content_base64")
        if not encoded_content:
            raise ValueError("input_payload.content_base64 缺失，无法上传知识库文件")
        try:
            content = base64.b64decode(str(encoded_content), validate=True)
        except Exception as exc:
            raise ValueError("input_payload.content_base64 不是有效的 base64") from exc
        if not content:
            raise ValueError("input_payload.content_base64 为空，无法上传知识库文件")

        filename = payload.get("document_name") or payload.get("filename") or "knowledge.pdf"
        upload_file = UploadFile(file=io.BytesIO(content), filename=filename)
        from app.core.auth import CurrentUserContext

        fake_user = CurrentUserContext(user_id=job.user_id)
        result = await upload_and_ingest(
            file=upload_file,  # type: ignore[arg-type]
            category=payload.get("category", "general"),
            application_scenario=_require_contract_scenario(payload),
            subcategory_id=payload.get("subcategory_id"),
            subcategory_name=payload.get("subcategory_name"),
            db=db,
            user=fake_user,
        )
        if hasattr(result, "model_dump"):
            return result.model_dump()
        return dict(result)


async def _execute_task(
    ctx,
    job_id: str,
    runner: Callable[..., Coroutine],
) -> None:
    async with async_session() as db:
        await mark_job_running(db, job_id)
        try:
            result = await runner(ctx, job_id)
            await mark_job_succeeded(db, job_id, result_payload=result)
        except Exception as exc:
            await mark_job_failed(db, job_id, error_message=str(exc))


async def inspect_document_task(ctx, job_id: str):
    await _execute_task(ctx, job_id, _run_inspect)


async def parse_document_task(ctx, job_id: str):
    await _execute_task(ctx, job_id, _run_parse)


async def knowledge_upload_task(ctx, job_id: str):
    await _execute_task(ctx, job_id, _run_knowledge_upload)


async def close_expired_orders_task(ctx: dict) -> dict[str, int]:
    """ARQ 定时任务：每 5 分钟关闭超时未支付的 pending 订单。"""
    from app.services.payment_service import close_expired_orders

    async with async_session() as db:
        return await close_expired_orders(db)


async def reset_monthly_free_quota_task(ctx: dict) -> dict[str, int]:
    """ARQ 定时任务：每月 1 号重置免费用户 token_used。"""
    from sqlalchemy import update
    from goulong_auth.models import Membership

    async with async_session() as db:
        result = await db.execute(
            update(Membership)
            .where(
                Membership.product == "zhaodan",
                Membership.plan == "free",
            )
            .values(token_used=0)
        )
        await db.commit()
        return {"reset_count": result.rowcount}
