"""add contract inspection types and classification snapshots

Revision ID: 025
Revises: 024
"""
from __future__ import annotations

from typing import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "025"
down_revision: str | None = "024"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

SCHEMA = "zhaodan"


def upgrade() -> None:
    op.create_table(
        "inspection_types",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("key", sa.String(length=100), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("dimension", sa.String(length=20), nullable=False),
        sa.Column("owner_type", sa.String(length=20), nullable=False),
        sa.Column("owner_user_id", sa.UUID(), nullable=True),
        sa.Column("enabled", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "dimension IN ('engineering', 'contract')",
            name="ck_inspection_types_dimension",
        ),
        sa.CheckConstraint(
            "owner_type IN ('system', 'user')",
            name="ck_inspection_types_owner_type",
        ),
        sa.CheckConstraint(
            "(owner_type = 'system' AND owner_user_id IS NULL) OR "
            "(owner_type = 'user' AND owner_user_id IS NOT NULL)",
            name="ck_inspection_types_owner_scope",
        ),
        sa.CheckConstraint(
            "enabled IN (TRUE, FALSE)",
            name="ck_inspection_types_enabled",
        ),
        sa.ForeignKeyConstraint(["owner_user_id"], ["goulong_auth.users.id"]),
        sa.PrimaryKeyConstraint("id"),
        schema=SCHEMA,
    )
    op.create_index(
        "uq_inspection_types_system_key", "inspection_types", ["dimension", "key"],
        unique=True, schema=SCHEMA, postgresql_where=sa.text("owner_type = 'system'"),
    )
    op.create_index(
        "uq_inspection_types_system_name", "inspection_types", ["dimension", "name"],
        unique=True, schema=SCHEMA, postgresql_where=sa.text("owner_type = 'system'"),
    )
    op.create_index(
        "uq_inspection_types_user_key", "inspection_types", ["dimension", "owner_user_id", "key"],
        unique=True, schema=SCHEMA, postgresql_where=sa.text("owner_type = 'user'"),
    )
    op.create_index(
        "uq_inspection_types_user_name", "inspection_types", ["dimension", "owner_user_id", "name"],
        unique=True, schema=SCHEMA, postgresql_where=sa.text("owner_type = 'user'"),
    )

    for table, columns in {
        "knowledge_documents": {
            "engineering_type_key": sa.String(length=100),
            "contract_type_key": sa.String(length=100),
            "is_active": sa.Boolean(),
        },
        "inspection_records": {
            "detected_engineering_type": sa.String(length=100),
            "final_engineering_type": sa.String(length=100),
            "detected_contract_type": sa.String(length=100),
            "final_contract_type": sa.String(length=100),
            "classification_confidence": sa.String(length=20),
            "rule_package_key": sa.String(length=100),
            "classification_source": sa.String(length=30),
            "engineering_type_snapshot": sa.String(length=100),
            "contract_type_snapshot": sa.String(length=100),
            "knowledge_sources_snapshot": sa.JSON(),
        },
    }.items():
        for name, column_type in columns.items():
            kwargs = {"server_default": sa.true()} if name == "is_active" else {}
            op.add_column(table, sa.Column(name, column_type, nullable=name != "is_active", **kwargs), schema=SCHEMA)
    op.create_check_constraint(
        "ck_inspection_records_classification_confidence",
        "inspection_records",
        "classification_confidence IS NULL OR classification_confidence IN ('high', 'medium', 'low')",
        schema=SCHEMA,
    )
    op.create_check_constraint(
        "ck_inspection_records_classification_source",
        "inspection_records",
        "classification_source IS NULL OR classification_source IN "
        "('legacy', 'archived_legacy', 'rule', 'model', 'manual', 'fallback')",
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_inspection_records_classification_source", "inspection_records", schema=SCHEMA,
    )
    op.drop_constraint(
        "ck_inspection_records_classification_confidence", "inspection_records", schema=SCHEMA,
    )
    for name in (
        "knowledge_sources_snapshot",
        "contract_type_snapshot",
        "engineering_type_snapshot",
        "classification_source",
        "rule_package_key",
        "classification_confidence",
        "final_contract_type",
        "detected_contract_type",
        "final_engineering_type",
        "detected_engineering_type",
    ):
        op.drop_column("inspection_records", name, schema=SCHEMA)
    for name in ("is_active", "contract_type_key", "engineering_type_key"):
        op.drop_column("knowledge_documents", name, schema=SCHEMA)
    for name in (
        "uq_inspection_types_user_name",
        "uq_inspection_types_user_key",
        "uq_inspection_types_system_name",
        "uq_inspection_types_system_key",
    ):
        op.drop_index(name, table_name="inspection_types", schema=SCHEMA)
    op.drop_table("inspection_types", schema=SCHEMA)
