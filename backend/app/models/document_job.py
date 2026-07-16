from __future__ import annotations

import datetime
import uuid

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.knowledge import Base


DOCUMENT_JOB_TYPES = ("inspection", "knowledge", "agent_parse")
DOCUMENT_JOB_STATUSES = ("queued", "running", "succeeded", "failed", "cancelled")
DOCUMENT_JOB_STAGES = (
    "queued",
    "detecting",
    "parsing_local",
    "parsing_mineru",
    "indexing",
    "inspecting",
    "succeeded",
    "failed",
)
DOCUMENT_PARSER_ENGINES = ("text", "markitdown", "mineru")

_STATE_CONSISTENCY_SQL = (
    "(status = 'queued' AND stage = 'queued' AND progress = 0 AND finished_at IS NULL AND error_code IS NULL) OR "
    "(status = 'running' AND stage IN ('detecting', 'parsing_local', 'parsing_mineru', 'indexing', 'inspecting') "
    "AND progress BETWEEN 0 AND 99 AND finished_at IS NULL AND error_code IS NULL) OR "
    "(status = 'succeeded' AND stage = 'succeeded' AND progress = 100 AND finished_at IS NOT NULL AND "
    "error_code IS NULL) OR "
    "(status = 'failed' AND stage = 'failed' AND finished_at IS NOT NULL AND error_code IS NOT NULL) OR "
    "(status = 'cancelled' AND stage NOT IN ('succeeded', 'failed') AND progress BETWEEN 0 AND 99 AND "
    "finished_at IS NOT NULL AND error_code IS NULL)"
)


def _in_constraint(column: str, values: tuple[str, ...]) -> str:
    allowed = ", ".join(f"'{value}'" for value in values)
    return f"{column} IN ({allowed})"


def _utcnow() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


class DocumentProcessingJob(Base):
    __tablename__ = "document_processing_jobs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_id: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("goulong_auth.users.id", ondelete="CASCADE"),
        nullable=False,
    )
    job_type: Mapped[str] = mapped_column(String(50), nullable=False)
    source_path: Mapped[str] = mapped_column(String(1000), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    file_type: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="queued",
        server_default="queued",
    )
    stage: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="queued",
        server_default="queued",
    )
    progress: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    parser_engine: Mapped[str | None] = mapped_column(String(50), nullable=True)
    mineru_task_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    mineru_upload_state: Mapped[str | None] = mapped_column(String(20), nullable=True)
    markdown_path: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    markdown_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    index_artifact_path: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    index_artifact_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    inspection_call_state: Mapped[str | None] = mapped_column(String(20), nullable=True)
    inspection_input_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    inspection_result_path: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    inspection_result_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    knowledge_version_id: Mapped[int | None] = mapped_column(
        ForeignKey("zhaodan.document_versions.id", ondelete="SET NULL"),
        nullable=True,
    )
    inspection_record_id: Mapped[int | None] = mapped_column(
        ForeignKey("zhaodan.inspection_records.id", ondelete="SET NULL"),
        nullable=True,
    )
    error_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    dispatch_pending: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=text("true"))
    dispatch_retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    next_dispatch_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow, server_default=func.now()
    )
    dispatch_claim_owner: Mapped[str | None] = mapped_column(String(100), nullable=True)
    dispatch_claim_expires_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    lease_version: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    lease_owner: Mapped[str | None] = mapped_column(String(100), nullable=True)
    lease_expires_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    parser_version: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="1",
        server_default="1",
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        server_default=func.now(),
        onupdate=_utcnow,
    )
    finished_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        CheckConstraint(
            _in_constraint("status", DOCUMENT_JOB_STATUSES),
            name="ck_document_processing_jobs_status",
        ),
        CheckConstraint(
            _in_constraint("stage", DOCUMENT_JOB_STAGES),
            name="ck_document_processing_jobs_stage",
        ),
        CheckConstraint(
            _in_constraint("job_type", DOCUMENT_JOB_TYPES),
            name="ck_document_processing_jobs_job_type",
        ),
        CheckConstraint(
            f"parser_engine IS NULL OR {_in_constraint('parser_engine', DOCUMENT_PARSER_ENGINES)}",
            name="ck_document_processing_jobs_parser_engine",
        ),
        CheckConstraint(
            "content_hash ~ '^[0-9a-f]{64}$'",
            name="ck_document_processing_jobs_content_hash",
        ),
        CheckConstraint(
            "markdown_hash IS NULL OR markdown_hash ~ '^[0-9a-f]{64}$'",
            name="ck_document_processing_jobs_markdown_hash",
        ),
        CheckConstraint(
            "index_artifact_hash IS NULL OR index_artifact_hash ~ '^[0-9a-f]{64}$'",
            name="ck_document_processing_jobs_index_artifact_hash",
        ),
        CheckConstraint(
            "inspection_input_hash IS NULL OR inspection_input_hash ~ '^[0-9a-f]{64}$'",
            name="ck_document_processing_jobs_inspection_input_hash",
        ),
        CheckConstraint(
            "inspection_result_hash IS NULL OR inspection_result_hash ~ '^[0-9a-f]{64}$'",
            name="ck_document_processing_jobs_inspection_result_hash",
        ),
        CheckConstraint(
            "progress BETWEEN 0 AND 100",
            name="ck_document_processing_jobs_progress_range",
        ),
        CheckConstraint(
            "retry_count >= 0",
            name="ck_document_processing_jobs_retry_count_nonnegative",
        ),
        CheckConstraint(
            "lease_version >= 0",
            name="ck_document_processing_jobs_lease_version_nonnegative",
        ),
        CheckConstraint(
            "dispatch_retry_count >= 0",
            name="ck_document_processing_jobs_dispatch_retry_nonnegative",
        ),
        CheckConstraint(
            "(dispatch_claim_owner IS NULL) = (dispatch_claim_expires_at IS NULL)",
            name="ck_document_processing_jobs_dispatch_claim_pair",
        ),
        CheckConstraint(
            "(lease_owner IS NULL) = (lease_expires_at IS NULL)",
            name="ck_document_processing_jobs_lease_pair",
        ),
        CheckConstraint(
            "(mineru_task_id IS NULL AND mineru_upload_state IS NULL) OR "
            "(mineru_task_id IS NOT NULL AND mineru_upload_state IN ('pending', 'uploaded'))",
            name="ck_document_processing_jobs_mineru_upload_state",
        ),
        CheckConstraint(
            "(markdown_path IS NULL AND markdown_hash IS NULL) OR "
            "(markdown_path IS NOT NULL AND markdown_hash IS NOT NULL)",
            name="ck_document_processing_jobs_markdown_pair",
        ),
        CheckConstraint(
            "(index_artifact_path IS NULL) = (index_artifact_hash IS NULL)",
            name="ck_document_processing_jobs_index_artifact_pair",
        ),
        CheckConstraint(
            "(inspection_result_path IS NULL) = (inspection_result_hash IS NULL)",
            name="ck_document_processing_jobs_inspection_result_pair",
        ),
        CheckConstraint(
            "inspection_call_state IS NULL OR inspection_call_state IN ('started', 'completed')",
            name="ck_document_processing_jobs_inspection_call_state",
        ),
        CheckConstraint(
            "status <> 'succeeded' OR "
            "(parser_engine IS NOT NULL AND markdown_path IS NOT NULL AND markdown_hash IS NOT NULL)",
            name="ck_document_processing_jobs_succeeded_artifact",
        ),
        CheckConstraint(
            _STATE_CONSISTENCY_SQL,
            name="ck_document_processing_jobs_state_consistency",
        ),
        Index(
            "ix_document_processing_jobs_user_created_at",
            "user_id",
            "created_at",
        ),
        Index("ix_document_processing_jobs_status", "status"),
        Index(
            "ix_document_processing_jobs_dispatch_pending",
            "dispatch_pending",
            "next_dispatch_at",
            postgresql_where=text("dispatch_pending"),
        ),
        Index(
            "ix_document_processing_jobs_expired_lease",
            "status",
            "lease_expires_at",
            postgresql_where=text("status = 'running'"),
        ),
        Index(
            "ix_document_processing_jobs_user_hash_parser_version",
            "user_id",
            "content_hash",
            "parser_version",
        ),
        Index(
            "ix_document_processing_jobs_markdown_cache",
            "user_id",
            "content_hash",
            "parser_version",
            "status",
            "finished_at",
            postgresql_where=text("status = 'succeeded'"),
        ),
    )
