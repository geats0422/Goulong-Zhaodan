from __future__ import annotations

import sys
import types
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

for mod_name in [
    "markitdown",
    "pageindex",
    "pydantic_ai",
    "pydantic_ai.agent",
    "pydantic_ai.models",
]:
    if mod_name not in sys.modules:
        sys.modules[mod_name] = types.ModuleType(mod_name)

if "markitdown" not in sys.modules or not hasattr(sys.modules.get("markitdown"), "MarkItDown"):
    _fake_md = types.ModuleType("markitdown")
    _fake_md.MarkItDown = MagicMock()
    sys.modules["markitdown"] = _fake_md

if "app.agents.inspector" not in sys.modules:
    _fake_inspector = types.ModuleType("app.agents.inspector")

    async def _fake_run_inspection(*args, **kwargs):
        from types import SimpleNamespace

        return SimpleNamespace(overall_risk="low", summary="", issues=[], regulation_refs=[])

    _fake_inspector.run_inspection = _fake_run_inspection
    sys.modules["app.agents.inspector"] = _fake_inspector

from app.workers.tasks import (  # noqa: E402
    _run_inspect,
    _run_knowledge_upload,
    _run_parse,
    inspect_document_task,
    knowledge_upload_task,
    parse_document_task,
)


def _make_mock_session_ctx():
    session = AsyncMock()
    ctx_mgr = MagicMock()
    ctx_mgr.__aenter__ = AsyncMock(return_value=session)
    ctx_mgr.__aexit__ = AsyncMock(return_value=False)
    return session, ctx_mgr


@pytest.mark.asyncio
async def test_inspect_task_success():
    mock_session, mock_ctx = _make_mock_session_ctx()

    with (
        patch("app.workers.tasks.async_session", return_value=mock_ctx),
        patch("app.workers.tasks.mark_job_running", new_callable=AsyncMock) as mock_running,
        patch("app.workers.tasks.mark_job_succeeded", new_callable=AsyncMock) as mock_succeeded,
        patch("app.workers.tasks.mark_job_failed", new_callable=AsyncMock) as mock_failed,
        patch("app.workers.tasks._run_inspect", new_callable=AsyncMock, return_value={"record_id": 1, "overall_risk": "low"}),
    ):
        await inspect_document_task({}, "job_abc123")

        mock_running.assert_awaited_once_with(mock_session, "job_abc123")
        mock_succeeded.assert_awaited_once()
        assert mock_succeeded.call_args[0][0] is mock_session
        assert mock_succeeded.call_args[0][1] == "job_abc123"
        mock_failed.assert_not_awaited()


@pytest.mark.asyncio
async def test_inspect_task_failure():
    mock_session, mock_ctx = _make_mock_session_ctx()

    with (
        patch("app.workers.tasks.async_session", return_value=mock_ctx),
        patch("app.workers.tasks.mark_job_running", new_callable=AsyncMock) as mock_running,
        patch("app.workers.tasks.mark_job_succeeded", new_callable=AsyncMock) as mock_succeeded,
        patch("app.workers.tasks.mark_job_failed", new_callable=AsyncMock) as mock_failed,
        patch(
            "app.workers.tasks._run_inspect",
            new_callable=AsyncMock,
            side_effect=RuntimeError("审查服务不可用"),
        ),
    ):
        await inspect_document_task({}, "job_fail_inspect")

        mock_running.assert_awaited_once_with(mock_session, "job_fail_inspect")
        mock_succeeded.assert_not_awaited()
        mock_failed.assert_awaited_once()
        assert mock_failed.call_args[0][0] is mock_session
        assert mock_failed.call_args[0][1] == "job_fail_inspect"
        assert "审查服务不可用" in mock_failed.call_args.kwargs["error_message"]


@pytest.mark.asyncio
async def test_parse_task_success():
    mock_session, mock_ctx = _make_mock_session_ctx()

    with (
        patch("app.workers.tasks.async_session", return_value=mock_ctx),
        patch("app.workers.tasks.mark_job_running", new_callable=AsyncMock) as mock_running,
        patch("app.workers.tasks.mark_job_succeeded", new_callable=AsyncMock) as mock_succeeded,
        patch("app.workers.tasks.mark_job_failed", new_callable=AsyncMock) as mock_failed,
        patch("app.workers.tasks._run_parse", new_callable=AsyncMock, return_value={"record_id": 1}),
    ):
        await parse_document_task({}, "job_parse_ok")

        mock_running.assert_awaited_once_with(mock_session, "job_parse_ok")
        mock_succeeded.assert_awaited_once()
        assert mock_succeeded.call_args[0][0] is mock_session
        assert mock_succeeded.call_args[0][1] == "job_parse_ok"
        mock_failed.assert_not_awaited()


@pytest.mark.asyncio
async def test_parse_task_failure():
    mock_session, mock_ctx = _make_mock_session_ctx()

    with (
        patch("app.workers.tasks.async_session", return_value=mock_ctx),
        patch("app.workers.tasks.mark_job_running", new_callable=AsyncMock) as mock_running,
        patch("app.workers.tasks.mark_job_succeeded", new_callable=AsyncMock) as mock_succeeded,
        patch("app.workers.tasks.mark_job_failed", new_callable=AsyncMock) as mock_failed,
        patch(
            "app.workers.tasks._run_parse",
            new_callable=AsyncMock,
            side_effect=RuntimeError("文档格式不支持"),
        ),
    ):
        await parse_document_task({}, "job_parse_fail")

        mock_running.assert_awaited_once_with(mock_session, "job_parse_fail")
        mock_succeeded.assert_not_awaited()
        mock_failed.assert_awaited_once()
        assert mock_failed.call_args[0][0] is mock_session
        assert mock_failed.call_args[0][1] == "job_parse_fail"
        assert "文档格式不支持" in mock_failed.call_args.kwargs["error_message"]


@pytest.mark.asyncio
async def test_knowledge_upload_task_success():
    mock_session, mock_ctx = _make_mock_session_ctx()

    with (
        patch("app.workers.tasks.async_session", return_value=mock_ctx),
        patch("app.workers.tasks.mark_job_running", new_callable=AsyncMock) as mock_running,
        patch("app.workers.tasks.mark_job_succeeded", new_callable=AsyncMock) as mock_succeeded,
        patch("app.workers.tasks.mark_job_failed", new_callable=AsyncMock) as mock_failed,
        patch("app.workers.tasks._run_knowledge_upload", new_callable=AsyncMock, return_value={"document_id": 1}),
    ):
        await knowledge_upload_task({}, "job_ku_ok")

        mock_running.assert_awaited_once_with(mock_session, "job_ku_ok")
        mock_succeeded.assert_awaited_once()
        assert mock_succeeded.call_args[0][0] is mock_session
        assert mock_succeeded.call_args[0][1] == "job_ku_ok"
        mock_failed.assert_not_awaited()


@pytest.mark.asyncio
async def test_knowledge_upload_task_failure():
    mock_session, mock_ctx = _make_mock_session_ctx()

    with (
        patch("app.workers.tasks.async_session", return_value=mock_ctx),
        patch("app.workers.tasks.mark_job_running", new_callable=AsyncMock) as mock_running,
        patch("app.workers.tasks.mark_job_succeeded", new_callable=AsyncMock) as mock_succeeded,
        patch("app.workers.tasks.mark_job_failed", new_callable=AsyncMock) as mock_failed,
        patch(
            "app.workers.tasks._run_knowledge_upload",
            new_callable=AsyncMock,
            side_effect=RuntimeError("知识库写入失败"),
        ),
    ):
        await knowledge_upload_task({}, "job_ku_fail")

        mock_running.assert_awaited_once_with(mock_session, "job_ku_fail")
        mock_succeeded.assert_not_awaited()
        mock_failed.assert_awaited_once()
        assert mock_failed.call_args[0][0] is mock_session
        assert mock_failed.call_args[0][1] == "job_ku_fail"
        assert "知识库写入失败" in mock_failed.call_args.kwargs["error_message"]


@pytest.mark.asyncio
async def test_run_inspect_executes_inspection_with_payload():
    """_run_inspect 从 job.input_payload 取参，调 execute_inspection，返回结果摘要。"""
    import uuid
    from types import SimpleNamespace

    mock_session, mock_ctx = _make_mock_session_ctx()
    mock_job = SimpleNamespace(
        job_id="job_inspect_1",
        user_id=uuid.UUID("12345678-1234-1234-1234-123456789012"),
        input_payload={
            "document_name": "测试招标.pdf",
            "text": "本项目为公开招标采购，投标人须具备相应资质。",
            "application_scenario": "bidding",
        },
    )
    mock_db_result = MagicMock()
    mock_db_result.scalar_one_or_none = MagicMock(return_value=mock_job)
    mock_session.execute = AsyncMock(return_value=mock_db_result)

    with (
        patch("app.workers.tasks.async_session", return_value=mock_ctx),
        patch("app.services.inspection_runner.execute_inspection", new_callable=AsyncMock) as mock_exec,
        pytest.raises(ValueError, match="deprecated_application_scenario"),
    ):
        await _run_inspect({}, "job_inspect_1")
    mock_exec.assert_not_awaited()


@pytest.mark.asyncio
async def test_run_inspect_raises_on_missing_text():
    """input_payload.text 缺失或过短时 _run_inspect 应 raise（_execute_task 会标记 failed）。"""
    from types import SimpleNamespace

    mock_session, mock_ctx = _make_mock_session_ctx()
    mock_job = SimpleNamespace(job_id="job_empty", user_id=None, input_payload={"document_name": "x.pdf"})
    mock_db_result = MagicMock()
    mock_db_result.scalar_one_or_none = MagicMock(return_value=mock_job)
    mock_session.execute = AsyncMock(return_value=mock_db_result)

    with (
        patch("app.workers.tasks.async_session", return_value=mock_ctx),
        pytest.raises(ValueError, match="text"),
    ):
        await _run_inspect({}, "job_empty")


@pytest.mark.asyncio
async def test_run_parse_creates_pending_record_with_text_payload():
    """_run_parse 应从 job.input_payload.text 创建可后续体检的 pending record。"""
    import uuid
    from types import SimpleNamespace

    mock_session, mock_ctx = _make_mock_session_ctx()
    mock_job = SimpleNamespace(
        job_id="job_parse_1",
        user_id=uuid.UUID("12345678-1234-1234-1234-123456789012"),
        input_payload={
            "document_name": "异步招标.txt",
            "text": "本项目为公开招标采购，投标人须提交完整投标文件。",
            "project_id": "async-project",
        },
    )
    mock_db_result = MagicMock()
    mock_db_result.scalar_one_or_none = MagicMock(return_value=mock_job)
    mock_session.execute = AsyncMock(return_value=mock_db_result)
    fake_record = SimpleNamespace(id=99)

    with (
        patch("app.workers.tasks.async_session", return_value=mock_ctx),
        patch("app.services.inspection_runner.create_pending_inspection_record", new_callable=AsyncMock, return_value=fake_record) as mock_create,
    ):
        result = await _run_parse({}, "job_parse_1")

    assert result["record_id"] == 99
    assert result["document_name"] == "异步招标.txt"
    assert result["document_type"] == "contract"
    assert "公开招标" in result["text_preview"]
    mock_create.assert_awaited_once()
    call_kwargs = mock_create.call_args.kwargs
    assert str(call_kwargs["user_id"]) == "12345678-1234-1234-1234-123456789012"
    assert call_kwargs["project_id"] == "async-project"


@pytest.mark.asyncio
async def test_run_parse_raises_on_missing_text():
    """input_payload.text 缺失或过短时 _run_parse 应 raise（_execute_task 会标记 failed）。"""
    from types import SimpleNamespace

    mock_session, mock_ctx = _make_mock_session_ctx()
    mock_job = SimpleNamespace(job_id="job_parse_empty", user_id=None, input_payload={"document_name": "x.txt"})
    mock_db_result = MagicMock()
    mock_db_result.scalar_one_or_none = MagicMock(return_value=mock_job)
    mock_session.execute = AsyncMock(return_value=mock_db_result)

    with (
        patch("app.workers.tasks.async_session", return_value=mock_ctx),
        pytest.raises(ValueError, match="text"),
    ):
        await _run_parse({}, "job_parse_empty")


@pytest.mark.asyncio
async def test_run_knowledge_upload_uses_existing_ingestion_handler():
    """_run_knowledge_upload 应把 base64 文件 payload 交给现有知识库入库逻辑处理。"""
    import base64
    import uuid
    from types import SimpleNamespace

    mock_session, mock_ctx = _make_mock_session_ctx()
    mock_job = SimpleNamespace(
        job_id="job_knowledge_1",
        user_id=uuid.UUID("12345678-1234-1234-1234-123456789012"),
        input_payload={
            "document_name": "法规.pdf",
            "content_base64": base64.b64encode(b"%PDF-1.4 fake").decode("ascii"),
            "category": "general",
            "subcategory_name": "测试法规",
            "application_scenario": "bidding",
        },
    )
    mock_db_result = MagicMock()
    mock_db_result.scalar_one_or_none = MagicMock(return_value=mock_job)
    mock_session.execute = AsyncMock(return_value=mock_db_result)
    fake_response = SimpleNamespace(model_dump=lambda: {"document_id": 7, "version_id": 8, "status": "completed"})

    with (
        patch("app.workers.tasks.async_session", return_value=mock_ctx),
        patch("app.api.v1.knowledge.upload_and_ingest", new_callable=AsyncMock, return_value=fake_response) as mock_upload,
        pytest.raises(ValueError, match="deprecated_application_scenario"),
    ):
        await _run_knowledge_upload({}, "job_knowledge_1")
    mock_upload.assert_not_awaited()


@pytest.mark.asyncio
async def test_run_knowledge_upload_raises_on_missing_content():
    """content_base64 缺失时 _run_knowledge_upload 应 raise（_execute_task 会标记 failed）。"""
    from types import SimpleNamespace

    mock_session, mock_ctx = _make_mock_session_ctx()
    mock_job = SimpleNamespace(job_id="job_knowledge_empty", user_id=None, input_payload={"document_name": "法规.pdf"})
    mock_db_result = MagicMock()
    mock_db_result.scalar_one_or_none = MagicMock(return_value=mock_job)
    mock_session.execute = AsyncMock(return_value=mock_db_result)

    with (
        patch("app.workers.tasks.async_session", return_value=mock_ctx),
        pytest.raises(ValueError, match="content_base64"),
    ):
        await _run_knowledge_upload({}, "job_knowledge_empty")


@pytest.mark.asyncio
async def test_run_parse_creates_document_job_with_content_base64():
    """含 content_base64 的 _run_parse 应派发统一文档任务并返回 document_job_id，不内联解析。"""
    import base64
    import hashlib
    import uuid
    from types import SimpleNamespace

    mock_session, mock_ctx = _make_mock_session_ctx()
    user_id = uuid.UUID("12345678-1234-1234-1234-123456789012")
    content = b"%PDF-1.4 fake pdf body content for parse"
    mock_job = SimpleNamespace(
        job_id="job_parse_file",
        user_id=user_id,
        input_payload={
            "document_name": "招标文件.pdf",
            "content_base64": base64.b64encode(content).decode("ascii"),
        },
    )
    mock_db_result = MagicMock()
    mock_db_result.scalar_one_or_none = MagicMock(return_value=mock_job)
    mock_session.execute = AsyncMock(return_value=mock_db_result)
    # ``async with db.begin():`` 占位，create_document_job 在其中被调用。
    mock_session.begin = MagicMock(return_value=AsyncMock())

    fake_source = SimpleNamespace(
        user_id=user_id,
        source_path="users/.../documents/abc.pdf",
        content_hash=hashlib.sha256(content).hexdigest(),
    )
    fake_doc_job = SimpleNamespace(job_id="doc_job_xyz")

    with (
        patch("app.workers.tasks.async_session", return_value=mock_ctx),
        patch("app.services.file_storage.save_file") as mock_save,
        patch("app.services.file_storage.delete_file") as mock_delete,
        patch(
            "app.services.document_job_service.prepare_source_artifact",
            new_callable=AsyncMock,
            return_value=fake_source,
        ) as mock_prepare,
        patch(
            "app.services.document_job_service.create_document_job",
            new_callable=AsyncMock,
            return_value=fake_doc_job,
        ) as mock_create,
    ):
        result = await _run_parse({}, "job_parse_file")

    assert result["document_job_id"] == "doc_job_xyz"
    assert result["document_name"] == "招标文件.pdf"
    assert result["file_type"] == "pdf"
    # 源文件应先落盘，再由 prepare_source_artifact 复核哈希。
    mock_save.assert_called_once()
    saved_path = mock_save.call_args.args[0]
    mock_prepare.assert_awaited_once()
    assert mock_prepare.call_args.args[0] == user_id
    assert mock_prepare.call_args.args[1] == saved_path
    assert mock_prepare.call_args.args[2] == hashlib.sha256(content).hexdigest()
    # 统一文档任务类型应为 agent_parse，复用统一解析服务。
    mock_create.assert_awaited_once()
    create_kwargs = mock_create.call_args.kwargs
    assert create_kwargs["job_type"] == "agent_parse"
    assert create_kwargs["source"] is fake_source
    assert create_kwargs["file_type"] == "pdf"
    # 成功路径不应删除已落盘源文件。
    mock_delete.assert_not_called()


@pytest.mark.asyncio
async def test_run_parse_cleans_up_source_when_document_job_create_fails():
    """create_document_job 失败时应删除已落盘源文件，避免产生孤儿产物。"""
    import base64
    import hashlib
    import uuid
    from types import SimpleNamespace

    mock_session, mock_ctx = _make_mock_session_ctx()
    user_id = uuid.UUID("12345678-1234-1234-1234-123456789012")
    content = b"%PDF-1.4 fake pdf body content for parse"
    mock_job = SimpleNamespace(
        job_id="job_parse_fail",
        user_id=user_id,
        input_payload={
            "document_name": "招标文件.pdf",
            "content_base64": base64.b64encode(content).decode("ascii"),
        },
    )
    mock_db_result = MagicMock()
    mock_db_result.scalar_one_or_none = MagicMock(return_value=mock_job)
    mock_session.execute = AsyncMock(return_value=mock_db_result)
    mock_session.begin = MagicMock(return_value=AsyncMock())

    fake_source = SimpleNamespace(
        user_id=user_id,
        source_path="users/.../documents/abc.pdf",
        content_hash=hashlib.sha256(content).hexdigest(),
    )

    with (
        patch("app.workers.tasks.async_session", return_value=mock_ctx),
        patch("app.services.file_storage.save_file") as mock_save,
        patch("app.services.file_storage.delete_file") as mock_delete,
        patch(
            "app.services.document_job_service.prepare_source_artifact",
            new_callable=AsyncMock,
            return_value=fake_source,
        ),
        patch(
            "app.services.document_job_service.create_document_job",
            new_callable=AsyncMock,
            side_effect=RuntimeError("db down"),
        ),
    ):
        with pytest.raises(RuntimeError, match="db down"):
            await _run_parse({}, "job_parse_fail")

    mock_save.assert_called_once()
    saved_path = mock_save.call_args.args[0]
    mock_delete.assert_called_once_with(saved_path)
