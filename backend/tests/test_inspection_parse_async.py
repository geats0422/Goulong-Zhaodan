"""异步 /inspection/parse 入口的契约测试（mock db/user，不依赖真实数据库）。

验证计划任务 10：
- 接收 UploadFile，流式保存到受控 ``users/{user_id}/documents/{uuid}.{ext}`` 路径；
- 计算 SHA-256 内容哈希并复核；
- 校验文件大小与扩展名；
- 在同事务中创建 pending InspectionRecord（text 空占位）+ inspection document job；
- 返回 202 + ``InspectionParseResponse.job_id``；
- 不再触发旧的同步解析（PDF/Word 不绕过统一解析直达 DeepSeek）。
"""

from __future__ import annotations

import hashlib
import uuid
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.v1 import inspection as inspection_api
from app.api.v1.inspection import router as inspection_router
from app.core.auth import CurrentUserContext, get_current_user
from app.core.database import get_db_session

USER_ID = uuid.UUID("22222222-2222-2222-2222-222222222222")


@pytest.fixture(autouse=True, scope="session")
def _ensure_schema() -> None:
    """Mock db/user boundary — never touch the real PostgreSQL test database."""


@pytest.fixture(autouse=True)
def _cleanup_before_test() -> None:
    """No database state is created by this module."""


class _FakeSession:
    """事务桩：直接调用 flush+commit 模式，兼容旧 begin() 模式。"""

    def __init__(self) -> None:
        self.events: list[str] = []

    @asynccontextmanager
    async def begin(self):
        self.events.append("begin")
        try:
            yield self
        except Exception:
            self.events.append("rollback")
            raise
        else:
            self.events.append("commit")

    async def commit(self):
        self.events.append("commit")

    async def rollback(self):
        self.events.append("rollback")


def _install_async_parse_mocks(monkeypatch: pytest.MonkeyPatch, *, record_id: int = 42):
    """替换 /parse 依赖的外部副作用，并捕获调用参数。"""
    captured: dict[str, object] = {}

    def fake_save_file(storage_path: str, content: bytes) -> str:
        captured["save_path"] = storage_path
        captured["save_content"] = content
        return storage_path

    async def fake_prepare_source(user_id, source_path, expected_hash, **kwargs):
        captured["prepare_user_id"] = user_id
        captured["prepare_path"] = source_path
        captured["prepare_hash"] = expected_hash
        return SimpleNamespace(
            user_id=user_id, source_path=source_path, content_hash=expected_hash
        )

    async def fake_add_record(**kwargs):
        captured["record_kwargs"] = kwargs
        return SimpleNamespace(id=record_id)

    async def fake_create_job(db, **kwargs):
        captured["job_kwargs"] = kwargs
        captured["job_db"] = db
        return SimpleNamespace(job_id="doc_job_async")

    convert_mock = MagicMock()
    extract_mock = MagicMock()
    read_inspection_text_mock = MagicMock()

    monkeypatch.setattr(inspection_api, "save_file", fake_save_file)
    monkeypatch.setattr(inspection_api, "prepare_source_artifact", fake_prepare_source)
    monkeypatch.setattr(inspection_api, "add_pending_inspection_record", fake_add_record)
    monkeypatch.setattr(inspection_api, "create_document_job", fake_create_job)
    # 旧同步解析路径必须不再被 /parse 触发。
    monkeypatch.setattr(inspection_api, "convert_to_markdown", convert_mock)
    monkeypatch.setattr(inspection_api, "_extract_inspection_text", extract_mock)
    monkeypatch.setattr(inspection_api, "_read_inspection_upload_text", read_inspection_text_mock)
    return captured, convert_mock, extract_mock, read_inspection_text_mock


@pytest.fixture
def parse_app(monkeypatch: pytest.MonkeyPatch) -> FastAPI:
    application = FastAPI()
    application.include_router(inspection_router)

    async def current_user() -> CurrentUserContext:
        return CurrentUserContext(user_id=USER_ID)

    async def session():
        yield _FakeSession()

    application.dependency_overrides[get_current_user] = current_user
    application.dependency_overrides[get_db_session] = session
    return application


@asynccontextmanager
async def _client(app: FastAPI):
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        yield client


@pytest.mark.asyncio
async def test_parse_saves_file_creates_inspection_job_and_returns_202(
    parse_app: FastAPI, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured, convert_mock, extract_mock, read_text_mock = _install_async_parse_mocks(monkeypatch)
    content = "这是一个足够长的招标文件内容，用于异步解析入口测试。".encode("utf-8")

    async with _client(parse_app) as client:
        response = await client.post(
            "/inspection/parse",
            files={"file": ("招标文件.txt", content, "text/plain")},
        )

    assert response.status_code == 202
    data = response.json()
    assert data["job_id"] == "doc_job_async"
    assert data["session_id"]
    classification = data["file"]["classification"]
    assert classification["engineering_type_key"] == "general-engineering"
    assert classification["contract_type_key"] == "other"
    assert classification["confidence"] == "low"
    assert classification["requires_confirmation"] is True

    save_path = captured["save_path"]
    assert isinstance(save_path, str)
    assert save_path.startswith(f"users/{USER_ID}/documents/")
    assert save_path.endswith(".txt")
    assert captured["save_content"] == content

    record_kwargs = captured["record_kwargs"]
    assert record_kwargs["document_name"] == "招标文件.txt"
    assert record_kwargs["text"] == ""  # 占位，由 worker 填充

    job_kwargs = captured["job_kwargs"]
    assert job_kwargs["job_type"] == "inspection"
    assert job_kwargs["inspection_record_id"] == 42
    assert job_kwargs["file_type"] == "txt"
    source = job_kwargs["source"]
    assert source.source_path == save_path

    # 同步解析链路必须保持沉默。
    convert_mock.assert_not_called()
    extract_mock.assert_not_called()
    read_text_mock.assert_not_called()


@pytest.mark.asyncio
async def test_parse_streams_content_and_computes_sha256_hash(
    parse_app: FastAPI, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured, _, _, _ = _install_async_parse_mocks(monkeypatch)
    content = b"contract body bytes for hashing"
    expected_hash = hashlib.sha256(content).hexdigest()

    async with _client(parse_app) as client:
        response = await client.post(
            "/inspection/parse",
            files={"file": ("demo.txt", content, "text/plain")},
        )

    assert response.status_code == 202
    assert captured["prepare_hash"] == expected_hash
    assert captured["prepare_user_id"] == USER_ID
    assert captured["prepare_path"] == captured["save_path"]
    source = captured["job_kwargs"]["source"]
    assert source.content_hash == expected_hash


@pytest.mark.asyncio
async def test_parse_rejects_oversized_file_with_413(
    parse_app: FastAPI, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured, _, _, _ = _install_async_parse_mocks(monkeypatch)
    big = b"x" * (inspection_api.MAX_INSPECTION_FILE_SIZE + 1)

    async with _client(parse_app) as client:
        response = await client.post(
            "/inspection/parse",
            files={"file": ("big.txt", big, "text/plain")},
        )

    assert response.status_code == 413
    # 大小超限应在保存与建 job 之前失败，避免无谓 I/O 与落库。
    assert "save_path" not in captured
    assert "job_kwargs" not in captured


@pytest.mark.asyncio
async def test_parse_rejects_unsupported_extension(
    parse_app: FastAPI, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured, _, _, _ = _install_async_parse_mocks(monkeypatch)

    async with _client(parse_app) as client:
        response = await client.post(
            "/inspection/parse",
            files={"file": ("doc.xlsx", b"fake", "application/octet-stream")},
        )

    assert response.status_code == 400
    assert "不支持的文件类型" in response.json()["detail"]
    assert "save_path" not in captured


@pytest.mark.asyncio
async def test_parse_rejects_legacy_doc_with_docx_hint(
    parse_app: FastAPI, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured, _, _, _ = _install_async_parse_mocks(monkeypatch)

    async with _client(parse_app) as client:
        response = await client.post(
            "/inspection/parse",
            files={"file": ("合同初稿.doc", b"fake", "application/msword")},
        )

    assert response.status_code == 400
    assert "另存为 .docx" in response.json()["detail"]
    assert "save_path" not in captured


@pytest.mark.asyncio
async def test_parse_persists_record_and_job_in_single_transaction(
    parse_app: FastAPI, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured, _, _, _ = _install_async_parse_mocks(monkeypatch)
    content = "甲方与乙方签订工程施工合同，约定违约责任。".encode("utf-8")

    async with _client(parse_app) as client:
        response = await client.post(
            "/inspection/parse",
            files={"file": ("施工合同.txt", content, "text/plain")},
        )

    assert response.status_code == 202
    # record 与 job 必须共享同一事务边界，避免悬空 pending 记录或孤儿任务。
    assert captured["record_kwargs"]["db"] is captured["job_db"]
