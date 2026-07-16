from __future__ import annotations

import asyncio
import datetime
from contextlib import asynccontextmanager, nullcontext
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.document_job_service import (
    claim_document_job_lease,
    heartbeat_document_job_lease,
    mark_document_job_dispatch_failed,
    mark_document_job_dispatched,
    release_document_job_lease,
)
from app.workers.dispatcher import dispatch_pending_document_jobs, document_job_dispatcher_task


NOW = datetime.datetime(2026, 7, 16, 12, tzinfo=datetime.timezone.utc)
OWNER = "worker-a"


class _Transaction:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return None


class _Session:
    def __init__(self) -> None:
        self.commit = AsyncMock()
        self.rollback = AsyncMock()
        self.flush = AsyncMock()

    def begin(self):
        return _Transaction()


@pytest.fixture(scope="session")
def _ensure_schema():
    """Reliability unit tests replace persistence boundaries."""


@pytest.fixture(autouse=True)
def _cleanup_before_test():
    """No database state is created by these unit tests."""


@pytest.mark.asyncio
async def test_dispatcher_uses_deterministic_id_and_confirms_after_redis_accepts(monkeypatch):
    claimed = SimpleNamespace(job_id="doc_job_1", retry_count=2, dispatch_retry_count=0, dispatch_claim_owner=OWNER)
    session = _Session()
    pool = SimpleNamespace(enqueue_job=AsyncMock(return_value=object()))
    claim = AsyncMock(return_value=[claimed])
    confirm = AsyncMock(return_value=True)
    monkeypatch.setattr("app.workers.dispatcher.claim_document_jobs_for_dispatch", claim)
    monkeypatch.setattr("app.workers.dispatcher.mark_document_job_dispatched", confirm)

    count = await dispatch_pending_document_jobs(pool, session_factory=lambda: _session(session), owner=OWNER)

    assert count == 1
    pool.enqueue_job.assert_awaited_once_with(
        "document_processing_task",
        job_id="doc_job_1",
        _job_id="document-job:doc_job_1:2:0",
    )
    confirm.assert_awaited_once_with(session, "doc_job_1", dispatch_owner=OWNER)
    session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_redis_acceptance_with_db_confirmation_failure_remains_safe_to_repeat(monkeypatch):
    claimed = SimpleNamespace(job_id="doc_job_1", retry_count=0, dispatch_retry_count=0, dispatch_claim_owner=OWNER)
    sessions = [_Session(), _Session()]
    pool = SimpleNamespace(enqueue_job=AsyncMock(return_value=object()))
    monkeypatch.setattr(
        "app.workers.dispatcher.claim_document_jobs_for_dispatch",
        AsyncMock(side_effect=[[claimed], [claimed]]),
    )
    monkeypatch.setattr(
        "app.workers.dispatcher.mark_document_job_dispatched",
        AsyncMock(side_effect=[ConnectionError("db confirm failed"), True]),
    )

    for session in sessions:
        expectation = pytest.raises(ConnectionError, match="confirm") if session is sessions[0] else nullcontext()
        with expectation:
            await dispatch_pending_document_jobs(pool, session_factory=lambda session=session: _session(session), owner=OWNER)

    assert [call.kwargs["_job_id"] for call in pool.enqueue_job.await_args_list] == [
        "document-job:doc_job_1:0:0",
        "document-job:doc_job_1:0:0",
    ]


@pytest.mark.asyncio
async def test_duplicate_dispatcher_gets_only_atomically_claimed_rows(monkeypatch):
    job = SimpleNamespace(job_id="doc_job_1", retry_count=0, dispatch_retry_count=0)
    lock = asyncio.Lock()
    available = [job]

    async def claim(*_args, **_kwargs):
        async with lock:
            return [available.pop()] if available else []

    monkeypatch.setattr("app.workers.dispatcher.claim_document_jobs_for_dispatch", claim)
    monkeypatch.setattr("app.workers.dispatcher.mark_document_job_dispatched", AsyncMock(return_value=True))
    pool = SimpleNamespace(enqueue_job=AsyncMock(return_value=object()))

    await asyncio.gather(
        dispatch_pending_document_jobs(pool, session_factory=lambda: _session(_Session()), owner="a"),
        dispatch_pending_document_jobs(pool, session_factory=lambda: _session(_Session()), owner="b"),
    )

    pool.enqueue_job.assert_awaited_once()


@pytest.mark.asyncio
async def test_dispatch_failure_is_recorded_without_committing_caller_session(monkeypatch):
    job = SimpleNamespace(job_id="doc_job_1", retry_count=0, dispatch_retry_count=0)
    session = _Session()
    failure = AsyncMock(return_value=True)
    monkeypatch.setattr("app.workers.dispatcher.claim_document_jobs_for_dispatch", AsyncMock(return_value=[job]))
    monkeypatch.setattr("app.workers.dispatcher.mark_document_job_dispatch_failed", failure)
    pool = SimpleNamespace(enqueue_job=AsyncMock(side_effect=ConnectionError("uncertain success")))

    assert await dispatch_pending_document_jobs(pool, session_factory=lambda: _session(session), owner=OWNER) == 0

    failure.assert_awaited_once()
    session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_worker_startup_and_cron_both_run_reliable_dispatcher(monkeypatch):
    dispatch = AsyncMock(return_value=3)
    monkeypatch.setattr("app.workers.dispatcher.dispatch_pending_document_jobs", dispatch)
    pool = object()

    result = await document_job_dispatcher_task({"redis": pool})

    assert result == {"dispatched": 3}
    dispatch.assert_awaited_once_with(pool)


@pytest.mark.asyncio
async def test_enqueue_none_is_not_confirmed_and_next_dispatch_uses_new_generation(monkeypatch):
    first = SimpleNamespace(job_id="doc_job_1", retry_count=0, dispatch_retry_count=0)
    second = SimpleNamespace(job_id="doc_job_1", retry_count=0, dispatch_retry_count=1)
    pool = SimpleNamespace(enqueue_job=AsyncMock(side_effect=[None, object()]))
    failure = AsyncMock(return_value=True)
    confirm = AsyncMock(return_value=True)
    monkeypatch.setattr("app.workers.dispatcher.claim_document_jobs_for_dispatch", AsyncMock(side_effect=[[first], [second]]))
    monkeypatch.setattr("app.workers.dispatcher.mark_document_job_dispatch_failed", failure)
    monkeypatch.setattr("app.workers.dispatcher.mark_document_job_dispatched", confirm)

    assert await dispatch_pending_document_jobs(pool, session_factory=lambda: _session(_Session()), owner=OWNER) == 0
    assert await dispatch_pending_document_jobs(pool, session_factory=lambda: _session(_Session()), owner=OWNER) == 1
    assert [call.kwargs["_job_id"] for call in pool.enqueue_job.await_args_list] == [
        "document-job:doc_job_1:0:0",
        "document-job:doc_job_1:0:1",
    ]
    failure.assert_awaited_once()
    confirm.assert_awaited_once()


@pytest.mark.asyncio
async def test_lease_service_methods_never_commit_caller_session():
    db = Mock(spec=AsyncSession)
    result = Mock()
    result.scalar_one_or_none.return_value = None
    db.execute = AsyncMock(return_value=result)
    db.flush = AsyncMock()
    db.commit = AsyncMock()
    db.rollback = AsyncMock()

    await claim_document_job_lease(db, "job", lease_owner=OWNER, lease_seconds=30, now=NOW)
    await heartbeat_document_job_lease(
        db, "job", lease_owner=OWNER, expected_lease_version=1, lease_seconds=30, now=NOW
    )
    await release_document_job_lease(db, "job", lease_owner=OWNER, expected_lease_version=1)
    await mark_document_job_dispatched(db, "job", dispatch_owner=OWNER)
    await mark_document_job_dispatch_failed(db, "job", dispatch_owner=OWNER, now=NOW)

    db.commit.assert_not_awaited()
    db.rollback.assert_not_awaited()


@asynccontextmanager
async def _session(value):
    yield value
