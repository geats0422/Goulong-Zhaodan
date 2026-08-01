from __future__ import annotations

import asyncio
import datetime
import uuid
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.router import router as api_router
from app.api.v1 import document_jobs as document_jobs_api
from app.core.auth import CurrentUserContext, get_current_user
from app.core.database import get_db_session
from app.core.auth import create_refresh_token
from app.services.document_job_service import (
    DocumentJobNotFoundError,
    InvalidDocumentJobTransitionError,
    RetryLimitExceededError,
)


USER_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
NOW = datetime.datetime(2026, 7, 16, 8, 30, tzinfo=datetime.timezone.utc)


@pytest.fixture(autouse=True, scope="session")
def _ensure_schema() -> None:
    """These API unit tests replace the database at the dependency boundary."""


@pytest.fixture(autouse=True)
def _cleanup_before_test(monkeypatch: pytest.MonkeyPatch) -> None:
    """No database state is created by this module."""
    monkeypatch.setattr(document_jobs_api, "consume_retry_rate_limit", AsyncMock(return_value=True))


class FakeSession:
    def __init__(self, events: list[str] | None = None) -> None:
        self.events = events if events is not None else []

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


def _job(**changes):
    values = {
        "job_id": "doc_job_public_id",
        "user_id": USER_ID,
        "job_type": "knowledge",
        "status": "failed",
        "stage": "failed",
        "progress": 62,
        "parser_engine": "mineru",
        "retry_count": 1,
        "lease_version": 4,
        "knowledge_version_id": 17,
        "inspection_record_id": None,
        "created_at": NOW,
        "updated_at": NOW,
        "finished_at": NOW,
        "error_code": "secret_internal_exception",
        "error_message": (
            "Traceback /private/source.pdf https://mineru.example/upload?token=secret"
        ),
        "source_path": "users/secret/source.pdf",
        "markdown_path": None,
        "markdown_hash": None,
        "content_hash": "b" * 64,
    }
    values.update(changes)
    return SimpleNamespace(**values)


@pytest.fixture
def app() -> FastAPI:
    value = FastAPI()
    value.include_router(api_router)
    return value


@pytest.fixture
def authenticated_app(app: FastAPI) -> FastAPI:
    async def current_user() -> CurrentUserContext:
        return CurrentUserContext(user_id=USER_ID)

    async def session():
        yield FakeSession()

    app.dependency_overrides[get_current_user] = current_user
    app.dependency_overrides[get_db_session] = session
    return app


@asynccontextmanager
async def _client(app: FastAPI):
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        yield client


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("get", "/api/v1/document-jobs/doc_job_public_id"),
        ("post", "/api/v1/document-jobs/doc_job_public_id/retry"),
    ],
)
async def test_document_job_endpoints_require_authentication(
    app: FastAPI, method: str, path: str
) -> None:
    async with _client(app) as client:
        response = await getattr(client, method)(path)

    assert response.status_code == 401


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("get", "/api/v1/document-jobs/doc_job_public_id"),
        ("post", "/api/v1/document-jobs/doc_job_public_id/retry"),
    ],
)
async def test_refresh_token_cannot_be_used_as_document_job_bearer(
    app: FastAPI,
    method: str,
    path: str,
) -> None:
    refresh_token, _ = create_refresh_token(USER_ID)

    async with _client(app) as client:
        response = await getattr(client, method)(
            path,
            headers={"Authorization": f"Bearer {refresh_token}"},
        )

    assert response.status_code == 401


@pytest.mark.asyncio
@pytest.mark.parametrize("case", ["missing", "other-user"])
@pytest.mark.parametrize("method", ["get", "post"])
async def test_endpoints_hide_missing_and_cross_user_jobs_as_404(
    authenticated_app: FastAPI,
    monkeypatch: pytest.MonkeyPatch,
    case: str,
    method: str,
) -> None:
    get_job = AsyncMock(side_effect=DocumentJobNotFoundError(case))
    monkeypatch.setattr(document_jobs_api, "get_document_job", get_job)

    async with _client(authenticated_app) as client:
        suffix = "/retry" if method == "post" else ""
        response = await getattr(client, method)(f"/api/v1/document-jobs/{case}{suffix}")

    assert response.status_code == 404
    assert get_job.await_args.args[2] == USER_ID


@pytest.mark.asyncio
async def test_status_returns_only_polling_shape_and_sanitized_error(
    authenticated_app: FastAPI,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(document_jobs_api, "get_document_job", AsyncMock(return_value=_job()))

    async with _client(authenticated_app) as client:
        response = await client.get("/api/v1/document-jobs/doc_job_public_id")

    assert response.status_code == 200
    payload = response.json()
    assert set(payload) == {
        "id",
        "type",
        "status",
        "stage",
        "progress",
        "message",
        "parser_engine",
        "retry_count",
        "max_retries",
        "knowledge_version_id",
        "inspection_record_id",
        "created_at",
        "updated_at",
        "finished_at",
        "error",
        "classification",
    }
    assert payload["id"] == "doc_job_public_id"
    assert payload["type"] == "knowledge"
    assert payload["max_retries"] == document_jobs_api.DOCUMENT_JOB_MAX_RETRIES
    assert payload["message"] == "任务处理失败"
    assert payload["error"] == {
        "code": "processing_failed",
        "message": "文档处理失败，请稍后重试",
    }
    serialized = response.text
    for secret in ("source_path", "markdown_path", "content_hash", "mineru.example", "Traceback"):
        assert secret not in serialized


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("service_error", "expected_detail"),
    [
        (InvalidDocumentJobTransitionError("raw state"), "任务当前不可重试"),
        (RetryLimitExceededError("raw limit"), "任务重试次数已达上限"),
    ],
)
async def test_retry_rejects_non_failed_or_exhausted_jobs_without_enqueue(
    authenticated_app: FastAPI,
    monkeypatch: pytest.MonkeyPatch,
    service_error: Exception,
    expected_detail: str,
) -> None:
    monkeypatch.setattr(document_jobs_api, "get_document_job", AsyncMock(return_value=_job()))
    monkeypatch.setattr(document_jobs_api, "retry_document_job", AsyncMock(side_effect=service_error))

    async with _client(authenticated_app) as client:
        response = await client.post("/api/v1/document-jobs/doc_job_public_id/retry")

    assert response.status_code == 409
    assert response.json() == {"detail": expected_detail}


@pytest.mark.asyncio
async def test_concurrent_retry_enqueues_only_the_winning_lease(
    authenticated_app: FastAPI,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = _job()
    lock = asyncio.Lock()

    async def get_job(*_args):
        return state

    async def retry_job(*_args, **_kwargs):
        async with lock:
            if state.status != "failed":
                raise InvalidDocumentJobTransitionError("already retried")
            state.status = "queued"
            state.stage = "queued"
            state.progress = 0
            state.retry_count += 1
            state.lease_version += 1
            state.finished_at = None
            state.error_code = None
            state.error_message = None
            state.dispatch_pending = True
            return state

    monkeypatch.setattr(document_jobs_api, "get_document_job", get_job)
    monkeypatch.setattr(document_jobs_api, "retry_document_job", retry_job)

    async with _client(authenticated_app) as client:
        responses = await asyncio.gather(
            client.post("/api/v1/document-jobs/doc_job_public_id/retry"),
            client.post("/api/v1/document-jobs/doc_job_public_id/retry"),
        )

    assert sorted(response.status_code for response in responses) == [200, 409]
    assert state.dispatch_pending is True


@pytest.mark.asyncio
async def test_retry_commits_dispatch_intent_and_returns_queued_without_direct_dispatch(
    app: FastAPI,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[str] = []
    state = _job()

    async def current_user() -> CurrentUserContext:
        return CurrentUserContext(user_id=USER_ID)

    async def session():
        yield FakeSession(events)

    async def retry_job(*_args, **_kwargs):
        state.status = "queued"
        state.stage = "queued"
        state.progress = 0
        state.retry_count = 2
        state.lease_version = 5
        state.finished_at = None
        state.error_code = None
        state.error_message = None
        state.dispatch_pending = True
        return state

    app.dependency_overrides[get_current_user] = current_user
    app.dependency_overrides[get_db_session] = session
    monkeypatch.setattr(document_jobs_api, "get_document_job", AsyncMock(return_value=state))
    monkeypatch.setattr(document_jobs_api, "retry_document_job", retry_job)

    async with _client(app) as client:
        response = await client.post("/api/v1/document-jobs/doc_job_public_id/retry")

    assert response.status_code == 200
    assert response.json()["status"] == "queued"
    assert events == ["commit"]
    assert state.dispatch_pending is True


@pytest.mark.asyncio
async def test_retry_rate_limit_exceeded_reads_valid_job_but_does_not_change_it(
    authenticated_app: FastAPI,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    get_job = AsyncMock(return_value=_job())
    retry_job = AsyncMock()
    monkeypatch.setattr(document_jobs_api, "get_document_job", get_job)
    monkeypatch.setattr(document_jobs_api, "retry_document_job", retry_job)
    monkeypatch.setattr(document_jobs_api, "consume_retry_rate_limit", AsyncMock(return_value=False))

    async with _client(authenticated_app) as client:
        response = await client.post("/api/v1/document-jobs/doc_job_public_id/retry")

    assert response.status_code == 429
    get_job.assert_awaited_once()
    retry_job.assert_not_awaited()


@pytest.mark.asyncio
async def test_retry_redis_unavailable_returns_503_without_db_state_change(
    app: FastAPI,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[str] = []

    async def current_user() -> CurrentUserContext:
        return CurrentUserContext(user_id=USER_ID)

    async def session():
        yield FakeSession(events)

    app.dependency_overrides[get_current_user] = current_user
    app.dependency_overrides[get_db_session] = session
    monkeypatch.setattr(
        document_jobs_api,
        "consume_retry_rate_limit",
        AsyncMock(side_effect=document_jobs_api.RetryRateLimitUnavailableError),
    )
    get_job = AsyncMock(return_value=_job())
    retry_job = AsyncMock()
    monkeypatch.setattr(document_jobs_api, "get_document_job", get_job)
    monkeypatch.setattr(document_jobs_api, "retry_document_job", retry_job)

    async with _client(app) as client:
        response = await client.post("/api/v1/document-jobs/doc_job_public_id/retry")

    assert response.status_code == 503
    assert events == []
    get_job.assert_awaited_once()
    retry_job.assert_not_awaited()


@pytest.mark.asyncio
async def test_status_get_does_not_consume_retry_rate_limit(
    authenticated_app: FastAPI,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    limiter = AsyncMock(return_value=True)
    monkeypatch.setattr(document_jobs_api, "consume_retry_rate_limit", limiter)
    monkeypatch.setattr(document_jobs_api, "get_document_job", AsyncMock(return_value=_job()))

    async with _client(authenticated_app) as client:
        response = await client.get("/api/v1/document-jobs/doc_job_public_id")

    assert response.status_code == 200
    limiter.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("job", "expected_status"),
    [
        (_job(status="running", stage="indexing"), 409),
        (_job(retry_count=document_jobs_api.DOCUMENT_JOB_MAX_RETRIES), 409),
    ],
)
async def test_invalid_retry_state_does_not_consume_rate_limit(
    authenticated_app: FastAPI,
    monkeypatch: pytest.MonkeyPatch,
    job: SimpleNamespace,
    expected_status: int,
) -> None:
    limiter = AsyncMock(return_value=True)
    monkeypatch.setattr(document_jobs_api, "consume_retry_rate_limit", limiter)
    monkeypatch.setattr(document_jobs_api, "get_document_job", AsyncMock(return_value=job))
    monkeypatch.setattr(document_jobs_api, "retry_document_job", AsyncMock())

    async with _client(authenticated_app) as client:
        response = await client.post("/api/v1/document-jobs/doc_job_public_id/retry")

    assert response.status_code == expected_status
    limiter.assert_not_awaited()
