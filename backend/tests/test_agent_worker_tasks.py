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

from app.workers.tasks import (
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
