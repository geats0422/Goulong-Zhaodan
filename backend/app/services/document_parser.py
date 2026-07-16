"""统一编排本地文档解析、质量门禁与 MinerU 兜底。"""

from __future__ import annotations

import asyncio
import codecs
import hashlib
import logging
import multiprocessing
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Protocol

from app.core.config import settings
from app.lib.mineru import MinerUClient, MinerUError, MinerUResult
from app.lib.private_temp import (
    FileIdentity,
    create_private_temp_file,
    secure_unlink,
    snapshot_file_identity,
    validate_file_identity,
)
from app.services.document_quality import (
    PdfDocumentKind,
    QualityThresholds,
    TextQuality,
    assess_text_quality,
    quality_thresholds_from_settings,
)
from app.services.document_router import (
    ConversionFailureAction,
    DocumentRouteDecision,
    ParserEngine,
    UnsupportedDocumentTypeError,
    route_document,
    select_engine_after_quality_gate,
)
from app.services.markdown_converter import convert_to_markdown

FILE_CHUNK_SIZE = 64 * 1024
PROCESS_POLL_INTERVAL_SECONDS = 0.01
PROCESS_TERMINATE_GRACE_SECONDS = 0.2
PROCESS_KILL_GRACE_SECONDS = 0.2
logger = logging.getLogger(__name__)


class AsyncMinerUClient(Protocol):
    async def parse_pdf_async(
        self,
        file_path: str,
        *,
        existing_task_id: str | None = None,
        on_task_created: Callable[[str, str], Awaitable[None]] | None = None,
    ) -> MinerUResult: ...


StageCallback = Callable[[str], Awaitable[None]]
TaskCreatedCallback = Callable[[str, str], Awaitable[None]]


class DocumentParseError(Exception):
    """不暴露底层转换细节的稳定解析业务错误。"""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)


@dataclass(frozen=True, slots=True)
class ParseResult:
    markdown: str
    parser_engine: ParserEngine
    content_hash: str
    markdown_hash: str
    quality: TextQuality
    mineru_task_id: str | None = None


@dataclass(frozen=True, slots=True)
class _Snapshot:
    path: Path
    content_hash: str
    identity: FileIdentity


def _document_worker(
    sender: Any,
    operation: str,
    input_path: str,
    output_path: str,
    thresholds: QualityThresholds,
    max_output_bytes: int,
) -> None:
    """Spawn-compatible worker for all blocking parser library calls."""
    try:
        if operation == "convert":
            markdown = convert_to_markdown(input_path)
            with open(output_path, "wb") as output:
                written = 0
                for offset in range(0, len(markdown), FILE_CHUNK_SIZE):
                    chunk = markdown[offset : offset + FILE_CHUNK_SIZE].encode("utf-8")
                    written += len(chunk)
                    if written > max_output_bytes:
                        raise DocumentParseError("conversion_failed", "文档解析失败")
                    output.write(chunk)
            sender.send(("ok", ""))
        elif operation == "read_text":
            decoder = codecs.getincrementaldecoder("utf-8")()
            total = 0
            with open(input_path, "rb") as source, open(output_path, "wb") as output:
                while chunk := source.read(FILE_CHUNK_SIZE):
                    total += len(chunk)
                    if total > max_output_bytes:
                        raise DocumentParseError("file_too_large", "文档超过解析大小限制")
                    decoder.decode(chunk)
                    output.write(chunk)
                decoder.decode(b"", final=True)
            sender.send(("ok", ""))
        elif operation == "classify_pdf":
            sender.send(("ok", _classify_pdf(input_path, thresholds).value))
        else:
            sender.send(("error", "worker_failed"))
    except DocumentParseError as error:
        sender.send(("error", error.code))
    except UnicodeDecodeError:
        sender.send(("error", "invalid_utf8"))
    except Exception:
        code, _ = _worker_error(operation)
        sender.send(("error", code))
    finally:
        _safe_close(sender)


def _snapshot_worker(sender: Any, source_path: str, snapshot_path: str, max_bytes: int) -> None:
    digest = hashlib.sha256()
    total = 0
    try:
        with open(source_path, "rb") as source, open(snapshot_path, "wb") as snapshot:
            while chunk := source.read(FILE_CHUNK_SIZE):
                total += len(chunk)
                if total > max_bytes:
                    raise DocumentParseError("file_too_large", "文档超过解析大小限制")
                digest.update(chunk)
                snapshot.write(chunk)
        sender.send(("ok", digest.hexdigest()))
    except DocumentParseError as error:
        sender.send(("error", error.code))
    except Exception:
        sender.send(("error", "file_read"))
    finally:
        _safe_close(sender)


def _classify_pdf(path: str, thresholds: QualityThresholds) -> PdfDocumentKind:
    """Classify one page at a time so extracted PDF text is never accumulated."""
    import pymupdf

    total_pages = 0
    valid_pages = 0
    page_thresholds = replace(
        thresholds,
        min_non_whitespace_length=thresholds.min_valid_pdf_page_length,
    )
    with pymupdf.open(path) as document:
        for page in document:
            total_pages += 1
            if assess_text_quality(page.get_text("text"), page_thresholds).is_acceptable:
                valid_pages += 1
    if total_pages and valid_pages == total_pages:
        return PdfDocumentKind.TEXT
    if valid_pages == 0:
        return PdfDocumentKind.SCANNED
    return PdfDocumentKind.MIXED


async def parse_document(
    file_path: str | Path,
    suffix: str,
    *,
    mineru_client: AsyncMinerUClient | None = None,
    deadline_seconds: float | None = None,
    thresholds: QualityThresholds | None = None,
    max_parse_bytes: int | None = None,
    process_context: Any | None = None,
    stage_callback: StageCallback | None = None,
    existing_mineru_task_id: str | None = None,
    mineru_task_created_callback: TaskCreatedCallback | None = None,
) -> ParseResult:
    """Parse a bounded private snapshot of a validated local document."""
    try:
        route_document(suffix)
    except UnsupportedDocumentTypeError:
        raise
    except ValueError:
        # PDF routing legitimately requires classification after snapshot creation.
        pass
    effective_deadline = (
        settings.mineru_total_timeout_seconds
        if deadline_seconds is None
        else deadline_seconds
    )
    effective_thresholds = thresholds or quality_thresholds_from_settings(settings)
    effective_max_bytes = settings.document_max_parse_bytes if max_parse_bytes is None else max_parse_bytes
    context = process_context or multiprocessing.get_context("spawn")
    snapshot: _Snapshot | None = None

    try:
        async with asyncio.timeout(effective_deadline):
            snapshot = await _create_snapshot(Path(file_path), suffix, effective_max_bytes, context)
            _require_snapshot_identity(snapshot.path, snapshot.identity)
            decision = await _route_snapshot(snapshot.path, suffix, effective_thresholds, context)
            return await _execute_route(
                snapshot,
                suffix,
                decision,
                effective_thresholds,
                effective_max_bytes,
                mineru_client,
                context,
                stage_callback,
                existing_mineru_task_id,
                mineru_task_created_callback,
            )
    except DocumentParseError:
        raise
    except TimeoutError:
        raise DocumentParseError("parse_timeout", "文档解析超时") from None
    except UnicodeDecodeError:
        raise DocumentParseError("invalid_utf8", "文本文件必须使用 UTF-8 编码") from None
    except OSError:
        raise DocumentParseError("file_read", "无法读取文档") from None
    finally:
        if snapshot is not None:
            secure_unlink(snapshot.path, identity=snapshot.identity)


async def _create_snapshot(source: Path, suffix: str, max_bytes: int, process_context: Any) -> _Snapshot:
    if max_bytes <= 0:
        raise DocumentParseError("file_too_large", "文档超过解析大小限制")
    normalized_suffix = suffix.strip().lower()
    if normalized_suffix and not normalized_suffix.startswith("."):
        normalized_suffix = f".{normalized_suffix}"
    snapshot_path: Path | None = None
    snapshot_identity: FileIdentity | None = None
    completed = False
    receiver: Any | None = None
    sender: Any | None = None
    process: Any | None = None
    process_started = False
    try:
        await asyncio.sleep(0)
        snapshot_path = create_private_temp_file(prefix="document-parser-", suffix=normalized_suffix)
        receiver, sender = process_context.Pipe(duplex=False)
        process = process_context.Process(
            target=_snapshot_worker,
            args=(sender, str(source), str(snapshot_path), max_bytes),
            daemon=True,
        )
        process.start()
        process_started = True
        _safe_close(sender)
        while True:
            if receiver.poll():
                status, value = receiver.recv()
                if status != "ok":
                    message = "文档超过解析大小限制" if value == "file_too_large" else "无法读取文档"
                    raise DocumentParseError(value or "file_read", message) from None
                content_hash = value
                break
            if not _safe_is_alive(process, default=True):
                raise DocumentParseError("file_read", "无法读取文档") from None
            await asyncio.sleep(PROCESS_POLL_INTERVAL_SECONDS)
        snapshot_path.chmod(0o400)
        snapshot_identity = snapshot_file_identity(snapshot_path)
        completed = True
        return _Snapshot(snapshot_path, content_hash, snapshot_identity)
    except DocumentParseError:
        raise
    except OSError:
        raise DocumentParseError("file_read", "无法读取文档") from None
    finally:
        try:
            if process_started and process is not None:
                await _stop_process(process)
        finally:
            if receiver is not None:
                _safe_close(receiver)
            if sender is not None:
                _safe_close(sender)
            if snapshot_path is not None and not completed:
                secure_unlink(snapshot_path, identity=snapshot_identity)


async def _route_snapshot(
    path: Path,
    suffix: str,
    thresholds: QualityThresholds,
    process_context: Any,
) -> DocumentRouteDecision:
    _require_snapshot_identity(path)
    if suffix.strip().lower().lstrip(".") != "pdf":
        return route_document(suffix)
    kind = await _run_isolated(
        "classify_pdf",
        path,
        thresholds,
        settings.document_max_parse_bytes,
        process_context,
    )
    try:
        return route_document(suffix, PdfDocumentKind(kind))
    except ValueError:
        raise DocumentParseError("pdf_read", "无法读取 PDF 文档") from None


async def _execute_route(
    snapshot: _Snapshot,
    suffix: str,
    decision: DocumentRouteDecision,
    thresholds: QualityThresholds,
    max_bytes: int,
    mineru_client: AsyncMinerUClient | None,
    process_context: Any,
    stage_callback: StageCallback | None = None,
    existing_mineru_task_id: str | None = None,
    mineru_task_created_callback: TaskCreatedCallback | None = None,
) -> ParseResult:
    if decision.primary_engine is not ParserEngine.MINERU and stage_callback is not None:
        await stage_callback("parsing_local")
    if decision.primary_engine is ParserEngine.DIRECT_TEXT:
        try:
            _require_snapshot_identity(snapshot.path, snapshot.identity)
            markdown = _normalize_markdown(
                await _run_isolated("read_text", snapshot.path, thresholds, max_bytes, process_context)
            )
        except UnicodeDecodeError:
            raise DocumentParseError("invalid_utf8", "文本文件必须使用 UTF-8 编码") from None
        except OSError:
            raise DocumentParseError("file_read", "无法读取文档") from None
        quality = assess_text_quality(markdown, thresholds)
        if not quality.is_acceptable:
            raise DocumentParseError("low_quality", "文档文本质量不足") from None
        return _build_result(markdown, ParserEngine.DIRECT_TEXT, snapshot.content_hash, quality)

    if decision.primary_engine is ParserEngine.MINERU:
        return await _parse_with_mineru(
            snapshot,
            thresholds,
            mineru_client,
            stage_callback=stage_callback,
            existing_task_id=existing_mineru_task_id,
            task_created_callback=mineru_task_created_callback,
        )

    try:
        _require_snapshot_identity(snapshot.path, snapshot.identity)
        converted = await _run_isolated(
            "convert",
            snapshot.path,
            thresholds,
            max_bytes,
            process_context,
        )
    except DocumentParseError as error:
        if error.code != "conversion_failed":
            raise
        if decision.conversion_failure_action is ConversionFailureAction.CONVERT_TO_PDF:
            raise DocumentParseError("convert_to_pdf_required", decision.failure_message) from None
        if decision.fallback_engine is ParserEngine.MINERU:
            return await _parse_with_mineru(
                snapshot,
                thresholds,
                mineru_client,
                stage_callback=stage_callback,
                existing_task_id=existing_mineru_task_id,
                task_created_callback=mineru_task_created_callback,
            )
        raise DocumentParseError("conversion_failed", "文档解析失败") from None

    markdown = _normalize_markdown(converted)
    quality = assess_text_quality(markdown, thresholds)
    if not quality.is_acceptable and decision.conversion_failure_action is ConversionFailureAction.CONVERT_TO_PDF:
        raise DocumentParseError("convert_to_pdf_required", decision.failure_message) from None
    selected_engine = select_engine_after_quality_gate(
        decision,
        is_acceptable=quality.is_acceptable,
    )
    if selected_engine is ParserEngine.MINERU:
        return await _parse_with_mineru(
            snapshot,
            thresholds,
            mineru_client,
            stage_callback=stage_callback,
            existing_task_id=existing_mineru_task_id,
            task_created_callback=mineru_task_created_callback,
        )
    return _build_result(markdown, ParserEngine.MARKITDOWN, snapshot.content_hash, quality)


async def _parse_with_mineru(
    snapshot: _Snapshot,
    thresholds: QualityThresholds,
    client: AsyncMinerUClient | None,
    *,
    stage_callback: StageCallback | None = None,
    existing_task_id: str | None = None,
    task_created_callback: TaskCreatedCallback | None = None,
) -> ParseResult:
    try:
        _require_snapshot_identity(snapshot.path, snapshot.identity)
        if stage_callback is not None:
            await stage_callback("parsing_mineru")
        parser = client or MinerUClient()
        if existing_task_id is None and task_created_callback is None:
            result = await parser.parse_pdf_async(str(snapshot.path))
        else:
            result = await parser.parse_pdf_async(
                str(snapshot.path),
                existing_task_id=existing_task_id,
                on_task_created=task_created_callback,
            )
    except MinerUError as error:
        if error.code == "timeout":
            raise DocumentParseError("parse_timeout", "文档解析超时") from None
        raise DocumentParseError("mineru_failed", "MinerU 文档解析失败") from None
    except Exception:
        raise DocumentParseError("mineru_failed", "MinerU 文档解析失败") from None
    markdown = _normalize_markdown(result.markdown)
    quality = assess_text_quality(markdown, thresholds)
    if not quality.is_acceptable:
        raise DocumentParseError("mineru_low_quality", "MinerU 解析结果质量不足") from None
    return _build_result(
        markdown,
        ParserEngine.MINERU,
        snapshot.content_hash,
        quality,
        mineru_task_id=result.task_id,
    )


async def _run_isolated(
    operation: str,
    input_path: Path,
    thresholds: QualityThresholds,
    max_output_bytes: int,
    process_context: Any,
) -> str:
    receiver: Any | None = None
    sender: Any | None = None
    output_path: Path | None = None
    output_identity: FileIdentity | None = None
    process: Any | None = None
    started = False
    try:
        receiver, sender = process_context.Pipe(duplex=False)
        output_path = create_private_temp_file(prefix="document-parser-output-", suffix=".md")
        output_identity = snapshot_file_identity(output_path)
        process = process_context.Process(
            target=_document_worker,
            args=(sender, operation, str(input_path), str(output_path), thresholds, max_output_bytes),
            daemon=True,
        )
        process.start()
        started = True
        _safe_close(sender)
        while True:
            if receiver.poll():
                status, value = receiver.recv()
                if status != "ok":
                    message = _worker_error_message(value)
                    raise DocumentParseError(value or "worker_failed", message) from None
                if operation == "classify_pdf":
                    return value
                if not validate_file_identity(output_path, output_identity):
                    raise DocumentParseError("conversion_failed", "文档解析失败") from None
                return await _read_output(str(output_path), max_output_bytes)
            if not _safe_is_alive(process, default=True):
                code, message = _worker_error(operation)
                raise DocumentParseError(code, message) from None
            await asyncio.sleep(PROCESS_POLL_INTERVAL_SECONDS)
    except DocumentParseError:
        raise
    except (EOFError, OSError, ValueError):
        code, message = _worker_error(operation)
        raise DocumentParseError(code, message) from None
    finally:
        try:
            if started and process is not None:
                await _stop_process(process)
        finally:
            if receiver is not None:
                _safe_close(receiver)
            if sender is not None:
                _safe_close(sender)
            if output_path is not None:
                secure_unlink(output_path, identity=output_identity)


async def _read_output(path: str, max_bytes: int) -> str:
    content = bytearray()
    try:
        with open(path, "rb") as output:
            while chunk := output.read(FILE_CHUNK_SIZE):
                content.extend(chunk)
                if len(content) > max_bytes:
                    raise DocumentParseError("conversion_failed", "文档解析失败") from None
                await asyncio.sleep(0)
        return bytes(content).decode("utf-8")
    except DocumentParseError:
        raise
    except (OSError, UnicodeDecodeError):
        raise DocumentParseError("conversion_failed", "文档解析失败") from None


def _worker_error(operation: str) -> tuple[str, str]:
    if operation == "classify_pdf":
        return "pdf_read", "无法读取 PDF 文档"
    if operation == "read_text":
        return "file_read", "无法读取文档"
    return "conversion_failed", "文档解析失败"


async def _stop_process(process: Any) -> None:
    cancellation: asyncio.CancelledError | None = None
    if _safe_is_alive(process, default=True):
        _safe_process_call(process, "terminate")
    try:
        await _wait_for_process_exit(process, PROCESS_TERMINATE_GRACE_SECONDS)
    except asyncio.CancelledError as error:
        cancellation = error
    if _safe_is_alive(process, default=True):
        _safe_process_call(process, "kill")
    try:
        await _wait_for_process_exit(process, PROCESS_KILL_GRACE_SECONDS)
    except asyncio.CancelledError as error:
        cancellation = error
    _safe_process_call(process, "join", timeout=0.1)
    if _safe_is_alive(process, default=False):
        logger.error("document parser worker could not be stopped")
    if cancellation is not None:
        raise cancellation


async def _wait_for_process_exit(process: Any, timeout_seconds: float) -> None:
    end = asyncio.get_running_loop().time() + timeout_seconds
    while asyncio.get_running_loop().time() < end:
        if not _safe_is_alive(process, default=True):
            return
        await asyncio.sleep(PROCESS_POLL_INTERVAL_SECONDS)


def _safe_is_alive(process: Any, *, default: bool) -> bool:
    try:
        return bool(process.is_alive())
    except Exception:
        logger.warning("document parser worker state check failed")
        return default


def _safe_process_call(process: Any, method: str, **kwargs: Any) -> None:
    try:
        getattr(process, method)(**kwargs)
    except Exception:
        logger.warning("document parser worker control failed operation=%s", method)


def _safe_close(resource: Any) -> None:
    try:
        resource.close()
    except Exception:
        logger.warning("document parser IPC cleanup failed")


def _build_result(
    markdown: str,
    parser_engine: ParserEngine,
    content_hash: str,
    quality: TextQuality,
    *,
    mineru_task_id: str | None = None,
) -> ParseResult:
    return ParseResult(
        markdown=markdown,
        parser_engine=parser_engine,
        content_hash=content_hash,
        markdown_hash=hashlib.sha256(markdown.encode("utf-8")).hexdigest(),
        quality=quality,
        mineru_task_id=mineru_task_id,
    )


def _normalize_markdown(markdown: str) -> str:
    normalized = markdown.replace("\r\n", "\n").replace("\r", "\n")
    lines = [line.rstrip() for line in normalized.split("\n")]
    return "\n".join(lines).strip() + "\n"


def _require_snapshot_identity(path: Path, identity: FileIdentity | None = None) -> None:
    if identity is not None and not validate_file_identity(path, identity):
        raise DocumentParseError("file_read", "无法读取文档") from None


def _worker_error_message(code: str) -> str:
    if code == "pdf_read":
        return "无法读取 PDF 文档"
    if code == "invalid_utf8":
        return "文本文件必须使用 UTF-8 编码"
    if code == "file_too_large":
        return "文档超过解析大小限制"
    if code == "file_read":
        return "无法读取文档"
    return "文档解析失败"
