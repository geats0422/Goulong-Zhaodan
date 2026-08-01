"""replace usage idempotency uniqueness with a user-scoped constraint

Revision ID: 028
Revises: 027
"""
from __future__ import annotations

from typing import Sequence

from alembic import op
from sqlalchemy import inspect

revision: str = "028"
down_revision: str | None = "027"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


TABLE = "compute_usage_records"
SCHEMA = "zhaodan"


def _objects(columns: list[str]) -> tuple[list[dict], list[dict]]:
    inspector = inspect(op.get_bind())
    indexes = [
        index for index in inspector.get_indexes(TABLE, schema=SCHEMA)
        if index.get("unique") and index.get("column_names") == columns
    ]
    constraints = [
        constraint for constraint in inspector.get_unique_constraints(TABLE, schema=SCHEMA)
        if constraint.get("column_names") == columns
    ]
    return indexes, constraints


def _drop_objects(columns: list[str]) -> None:
    indexes, constraints = _objects(columns)
    for index in indexes:
        op.drop_index(index["name"], table_name=TABLE, schema=SCHEMA)
    for constraint in constraints:
        op.drop_constraint(constraint["name"], TABLE, schema=SCHEMA, type_="unique")


def _create_index_if_missing(name: str, columns: list[str]) -> None:
    indexes, constraints = _objects(columns)
    if not indexes and not constraints:
        op.create_index(name, TABLE, columns, unique=True, schema=SCHEMA)


def upgrade() -> None:
    # 027 originally creates a single-column unique index. Accommodate databases
    # where a deployer materialized that uniqueness as a named constraint.
    _drop_objects(["idempotency_key"])
    _create_index_if_missing("uq_compute_usage_user_idempotency", ["user_id", "idempotency_key"])


def downgrade() -> None:
    _drop_objects(["user_id", "idempotency_key"])
    _create_index_if_missing("ix_compute_usage_records_idempotency_key", ["idempotency_key"])
