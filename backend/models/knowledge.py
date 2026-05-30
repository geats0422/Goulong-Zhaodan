from __future__ import annotations

import datetime

from sqlalchemy import BigInteger, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class EngineeringSubcategory(Base):
    __tablename__ = "engineering_subcategories"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    category_key: Mapped[str] = mapped_column(String(50), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        default=datetime.datetime.utcnow,
    )

    __table_args__ = (
        UniqueConstraint("category_key", "name", name="uq_category_subcategory"),
    )

    documents: Mapped[list[KnowledgeDocument]] = relationship(back_populates="subcategory")


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
    created_at: Mapped[datetime.datetime] = mapped_column(
        default=datetime.datetime.utcnow,
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow,
    )

    subcategory: Mapped[EngineeringSubcategory] = relationship(back_populates="documents")
    versions: Mapped[list[DocumentVersion]] = relationship(back_populates="document", foreign_keys="DocumentVersion.document_id")
    current_version: Mapped[DocumentVersion | None] = relationship(foreign_keys=[current_version_id])


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
        default=datetime.datetime.utcnow,
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
        default=datetime.datetime.utcnow,
    )

    version: Mapped[DocumentVersion] = relationship(back_populates="index_nodes")
    parent: Mapped[IndexNode | None] = relationship(remote_side=[id])
    children: Mapped[list[IndexNode]] = relationship(back_populates="parent")
