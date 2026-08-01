from __future__ import annotations

import datetime
import uuid

import sqlalchemy as sa
from sqlalchemy import BigInteger, Boolean, CheckConstraint, ForeignKey, Index, Integer, JSON, MetaData, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def _utcnow() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)


class Base(DeclarativeBase):
    metadata = MetaData(schema="zhaodan")


from goulong_auth.base import AuthBase  # noqa: E402


def _register_auth_tables():
    for _tbl in AuthBase.metadata.tables.values():
        Base.metadata._add_table(_tbl.name, _tbl.schema, _tbl)


_register_auth_tables()


class EngineeringSubcategory(Base):
    __tablename__ = "engineering_subcategories"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    category_key: Mapped[str] = mapped_column(String(50), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        default=_utcnow,
    )

    __table_args__ = (
        UniqueConstraint("category_key", "name", name="uq_category_subcategory"),
    )

    documents: Mapped[list[KnowledgeDocument]] = relationship(back_populates="subcategory")


class InspectionType(Base):
    __tablename__ = "inspection_types"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    key: Mapped[str] = mapped_column(String(100), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    dimension: Mapped[str] = mapped_column(String(20), nullable=False)
    owner_type: Mapped[str] = mapped_column(String(20), nullable=False)
    owner_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("goulong_auth.users.id"), nullable=True,
    )
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=sa.true())
    created_at: Mapped[datetime.datetime] = mapped_column(default=_utcnow, server_default=sa.func.now())
    updated_at: Mapped[datetime.datetime] = mapped_column(
        default=_utcnow, onupdate=_utcnow, server_default=sa.func.now(),
    )

    __table_args__ = (
        CheckConstraint(
            "dimension IN ('engineering', 'contract')",
            name="ck_inspection_types_dimension",
        ),
        CheckConstraint(
            "owner_type IN ('system', 'user')",
            name="ck_inspection_types_owner_type",
        ),
        CheckConstraint(
            "(owner_type = 'system' AND owner_user_id IS NULL) OR "
            "(owner_type = 'user' AND owner_user_id IS NOT NULL)",
            name="ck_inspection_types_owner_scope",
        ),
        CheckConstraint(
            "enabled IN (TRUE, FALSE)",
            name="ck_inspection_types_enabled",
        ),
        Index(
            "uq_inspection_types_system_key", "dimension", "key",
            unique=True, postgresql_where=(owner_type == "system"),
        ),
        Index(
            "uq_inspection_types_system_name", "dimension", "name",
            unique=True, postgresql_where=(owner_type == "system"),
        ),
        Index(
            "uq_inspection_types_user_key", "dimension", "owner_user_id", "key",
            unique=True, postgresql_where=(owner_type == "user"),
        ),
        Index(
            "uq_inspection_types_user_name", "dimension", "owner_user_id", "name",
            unique=True, postgresql_where=(owner_type == "user"),
        ),
    )


class KnowledgeDocument(Base):
    __tablename__ = "knowledge_documents"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    subcategory_id: Mapped[int] = mapped_column(
        ForeignKey("engineering_subcategories.id"), nullable=False,
    )
    current_version_id: Mapped[int | None] = mapped_column(
        ForeignKey("document_versions.id"), nullable=True,
    )
    owner_type: Mapped[str] = mapped_column(String(20), nullable=False, default="user")
    owner_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("goulong_auth.users.id"), nullable=True)
    application_scenario: Mapped[str] = mapped_column(String(20), nullable=False, default="contract")
    engineering_type_key: Mapped[str | None] = mapped_column(String(100), nullable=True)
    contract_type_key: Mapped[str | None] = mapped_column(String(100), nullable=True)
    rule_package_key: Mapped[str | None] = mapped_column(String(100), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    source_path: Mapped[str | None] = mapped_column(String(1000), unique=True, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        default=_utcnow,
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        default=_utcnow, onupdate=_utcnow,
    )

    subcategory: Mapped[EngineeringSubcategory] = relationship(back_populates="documents")
    versions: Mapped[list[DocumentVersion]] = relationship(back_populates="document", foreign_keys="DocumentVersion.document_id")
    current_version: Mapped[DocumentVersion | None] = relationship(foreign_keys=[current_version_id])

    __table_args__ = (
        Index(
            "ix_knowledge_documents_retrieval",
            "application_scenario",
            "is_active",
            "owner_type",
            "owner_user_id",
            "engineering_type_key",
            "contract_type_key",
            "rule_package_key",
        ),
    )


class DocumentVersion(Base):
    __tablename__ = "document_versions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    document_id: Mapped[int] = mapped_column(
        ForeignKey("knowledge_documents.id"), nullable=False,
    )
    version_number: Mapped[int] = mapped_column(nullable=False)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    original_file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    markdown_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    file_size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    file_type: Mapped[str] = mapped_column(String(10), nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        default=_utcnow,
    )

    document: Mapped[KnowledgeDocument] = relationship(back_populates="versions", foreign_keys=[document_id])
    index_nodes: Mapped[list[IndexNode]] = relationship(back_populates="version")


class IndexNode(Base):
    __tablename__ = "index_nodes"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    version_id: Mapped[int] = mapped_column(
        ForeignKey("document_versions.id"), nullable=False,
    )
    parent_id: Mapped[int | None] = mapped_column(
        ForeignKey("index_nodes.id"), nullable=True,
    )
    node_type: Mapped[str] = mapped_column(String(20), nullable=False)
    path_label: Mapped[str] = mapped_column(String(500), nullable=False)
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    position: Mapped[int] = mapped_column(nullable=False)
    page_index_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        default=_utcnow,
    )

    version: Mapped[DocumentVersion] = relationship(back_populates="index_nodes")
    parent: Mapped[IndexNode | None] = relationship(remote_side=[id])
    children: Mapped[list[IndexNode]] = relationship(back_populates="parent")


class ZhaodanUserProfile(Base):
    __tablename__ = "user_profiles"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("goulong_auth.users.id"), unique=True, nullable=False)
    legacy_id: Mapped[int | None] = mapped_column(Integer, unique=True, nullable=True)
    burn_after_read: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    model_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(default=_utcnow)
    updated_at: Mapped[datetime.datetime] = mapped_column(
        default=_utcnow, onupdate=_utcnow,
    )


class TabooWord(Base):
    __tablename__ = "taboo_words"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("goulong_auth.users.id"), nullable=False)
    word: Mapped[str] = mapped_column(String(100), nullable=False)
    replacement: Mapped[str | None] = mapped_column(String(100), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(default=_utcnow)
    updated_at: Mapped[datetime.datetime] = mapped_column(
        default=_utcnow, onupdate=_utcnow,
    )

    __table_args__ = (
        UniqueConstraint("user_id", "word", name="uq_user_taboo_word"),
    )


class KnowledgeDocumentSetting(Base):
    __tablename__ = "knowledge_document_settings"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("goulong_auth.users.id"), nullable=False)
    document_id: Mapped[int] = mapped_column(ForeignKey("knowledge_documents.id"), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    updated_at: Mapped[datetime.datetime] = mapped_column(
        default=_utcnow, onupdate=_utcnow,
    )

    __table_args__ = (
        UniqueConstraint("user_id", "document_id", name="uq_user_knowledge_document_setting"),
    )


class InspectionRecord(Base):
    __tablename__ = "inspection_records"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("goulong_auth.users.id"), nullable=False)
    document_name: Mapped[str] = mapped_column(String(255), nullable=False)
    document_type: Mapped[str] = mapped_column(String(20), nullable=False)
    document_type_label: Mapped[str] = mapped_column(String(50), nullable=False)
    project_id: Mapped[str] = mapped_column(String(100), nullable=False, default="default")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="processing", server_default="processing")
    overall_risk: Mapped[str] = mapped_column(String(20), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    issues: Mapped[list[dict]] = mapped_column(JSON, nullable=False, default=list)
    regulation_refs: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    text_preview: Mapped[str] = mapped_column(Text, nullable=False, default="")
    parsed_content: Mapped[str] = mapped_column(Text, nullable=False, default="")
    quota_consumed: Mapped[int] = mapped_column(nullable=False, default=1)
    detected_engineering_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    final_engineering_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    detected_contract_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    final_contract_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    classification_confidence: Mapped[str | None] = mapped_column(String(20), nullable=True)
    rule_package_key: Mapped[str | None] = mapped_column(String(100), nullable=True)
    rule_package_keys_snapshot: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    classification_source: Mapped[str | None] = mapped_column(String(30), nullable=True)
    engineering_type_snapshot: Mapped[str | None] = mapped_column(String(100), nullable=True)
    contract_type_snapshot: Mapped[str | None] = mapped_column(String(100), nullable=True)
    knowledge_sources_snapshot: Mapped[list | None] = mapped_column(JSON, nullable=True)
    classification_evidence: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(default=_utcnow)

    __table_args__ = (
        CheckConstraint(
            "status IN ('uploaded', 'processing', 'completed', 'failed', 'cancelled')",
            name="ck_inspection_records_status",
        ),
        CheckConstraint(
            "classification_confidence IS NULL OR classification_confidence IN ('high', 'medium', 'low')",
            name="ck_inspection_records_classification_confidence",
        ),
        CheckConstraint(
            "classification_source IS NULL OR classification_source IN "
            "('legacy', 'archived_legacy', 'rule', 'model', 'manual', 'fallback')",
            name="ck_inspection_records_classification_source",
        ),
        Index("ix_inspection_records_user_created_at", "user_id", "created_at"),
        Index("ix_inspection_records_user_project_created_at", "user_id", "project_id", "created_at"),
        Index("ix_inspection_records_user_status_created_at", "user_id", "status", "created_at"),
    )
