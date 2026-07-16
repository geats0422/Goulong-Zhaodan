from __future__ import annotations

import os
from pathlib import Path
import uuid

from alembic import command
from alembic.config import Config
import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import URL, make_url
from sqlalchemy.exc import IntegrityError


BACKEND_ROOT = Path(__file__).resolve().parents[1]
TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")

pytestmark = pytest.mark.skipif(
    TEST_DATABASE_URL is None,
    reason="需要显式设置 TEST_DATABASE_URL 才执行真实 PostgreSQL 迁移测试",
)


def _validated_test_url() -> URL:
    assert TEST_DATABASE_URL is not None
    url = make_url(TEST_DATABASE_URL.replace("+asyncpg", ""))
    if url.get_backend_name() != "postgresql" or not (url.database or "").endswith("_test"):
        pytest.skip("TEST_DATABASE_URL 必须指向名称以 _test 结尾的 PostgreSQL 测试库")
    return url


def _assert_insert_rejected(engine, values: dict[str, object]) -> None:
    payload = {
        "id": uuid.uuid4(),
        "job_id": f"job_{uuid.uuid4().hex}",
        "user_id": values.pop("user_id"),
        "job_type": "inspection",
        "source_path": "uploads/test.pdf",
        "content_hash": "a" * 64,
        "file_type": "pdf",
        "status": "queued",
        "stage": "queued",
        "progress": 0,
        "retry_count": 0,
        "parser_version": "1",
        **values,
    }
    columns = ", ".join(payload)
    parameters = ", ".join(f":{name}" for name in payload)
    connection = engine.connect()
    transaction = connection.begin()
    try:
        with pytest.raises(IntegrityError):
            connection.execute(
                text(f"INSERT INTO zhaodan.document_processing_jobs ({columns}) VALUES ({parameters})"),
                payload,
            )
    finally:
        transaction.rollback()
        connection.close()


def test_real_postgres_upgrade_constraints_and_downgrade() -> None:
    source_url = _validated_test_url()
    database_name = f"goulong_document_job_{uuid.uuid4().hex[:8]}_test"
    target_url = source_url.set(database=database_name)
    admin_engine = create_engine(source_url, isolation_level="AUTOCOMMIT")
    target_engine = None

    try:
        with admin_engine.connect() as connection:
            connection.execute(text(f'CREATE DATABASE "{database_name}"'))

        target_engine = create_engine(target_url)
        user_id = uuid.uuid4()
        with target_engine.begin() as connection:
            connection.execute(text("CREATE SCHEMA goulong_auth"))
            connection.execute(text("CREATE SCHEMA zhaodan"))
            connection.execute(text("CREATE TABLE goulong_auth.users (id UUID PRIMARY KEY)"))
            connection.execute(text("CREATE TABLE zhaodan.document_versions (id SERIAL PRIMARY KEY)"))
            connection.execute(text("CREATE TABLE zhaodan.inspection_records (id SERIAL PRIMARY KEY)"))
            connection.execute(text("INSERT INTO goulong_auth.users (id) VALUES (:id)"), {"id": user_id})

        config = Config(str(BACKEND_ROOT / "alembic.ini"))
        config.set_main_option("script_location", str(BACKEND_ROOT / "alembic"))
        config.set_main_option("sqlalchemy.url", target_url.render_as_string(hide_password=False))
        command.stamp(config, "018")
        command.upgrade(config, "022")

        inspector = inspect(target_engine)
        assert inspector.has_table("document_processing_jobs", schema="zhaodan")
        columns = {column["name"] for column in inspector.get_columns("document_processing_jobs", schema="zhaodan")}
        assert "lease_version" in columns
        assert "inspection_result_hash" in columns
        assert {
            "dispatch_pending",
            "dispatch_retry_count",
            "next_dispatch_at",
            "dispatch_claim_owner",
            "dispatch_claim_expires_at",
            "lease_owner",
            "lease_expires_at",
        } <= columns
        indexes = {index["name"] for index in inspector.get_indexes("document_processing_jobs", schema="zhaodan")}
        assert "ix_document_processing_jobs_markdown_cache" in indexes
        assert "ix_document_processing_jobs_dispatch_pending" in indexes
        assert "ix_document_processing_jobs_expired_lease" in indexes
        _assert_insert_rejected(target_engine, {"user_id": user_id, "status": "unknown"})
        _assert_insert_rejected(target_engine, {"user_id": user_id, "content_hash": "A" * 64})
        _assert_insert_rejected(target_engine, {"user_id": user_id, "markdown_hash": "a" * 63})
        _assert_insert_rejected(target_engine, {"user_id": user_id, "markdown_path": "users/x/a.md"})
        _assert_insert_rejected(
            target_engine,
            {
                "user_id": user_id,
                "status": "succeeded",
                "stage": "succeeded",
                "progress": 99,
                "finished_at": "2026-07-16T00:00:00Z",
            },
        )
        _assert_insert_rejected(
            target_engine,
            {
                "user_id": user_id,
                "status": "succeeded",
                "stage": "succeeded",
                "progress": 100,
                "finished_at": "2026-07-16T00:00:00Z",
            },
        )
        _assert_insert_rejected(
            target_engine,
            {
                "user_id": user_id,
                "status": "failed",
                "stage": "failed",
                "finished_at": "2026-07-16T00:00:00Z",
            },
        )

        command.downgrade(config, "018")
        inspector.clear_cache()
        assert not inspector.has_table("document_processing_jobs", schema="zhaodan")
    finally:
        if target_engine is not None:
            target_engine.dispose()
        with admin_engine.connect() as connection:
            connection.execute(
                text("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = :database_name"),
                {"database_name": database_name},
            )
            connection.execute(text(f'DROP DATABASE IF EXISTS "{database_name}"'))
        admin_engine.dispose()
