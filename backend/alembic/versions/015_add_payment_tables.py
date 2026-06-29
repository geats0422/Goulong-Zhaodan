"""add payment_orders, subscription_contracts, deduction_orders tables

Revision ID: 015
Revises: 014
Create Date: 2026-06-29
"""
from __future__ import annotations

from typing import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


revision: str = "015"
down_revision: str | None = "014"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "payment_orders",
        sa.Column("id", UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", UUID(as_uuid=True), nullable=False),
        sa.Column("out_trade_no", sa.String(32), nullable=False),
        sa.Column("product_code", sa.String(50), nullable=False),
        sa.Column("product_name", sa.String(100), nullable=False),
        sa.Column("product_type", sa.String(20), nullable=False),
        sa.Column("amount_cents", sa.Integer(), nullable=False),
        sa.Column("token_quota", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("code_url", sa.String(512), nullable=True),
        sa.Column("transaction_id", sa.String(64), nullable=True),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["goulong_auth.users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("out_trade_no"),
    )
    op.create_index("ix_payment_orders_user_id", "payment_orders", ["user_id"])
    op.create_index("ix_payment_orders_out_trade_no", "payment_orders", ["out_trade_no"])

    op.create_table(
        "subscription_contracts",
        sa.Column("id", UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", UUID(as_uuid=True), nullable=False),
        sa.Column("plan_code", sa.String(50), nullable=False),
        sa.Column("contract_code", sa.String(128), nullable=False),
        sa.Column("contract_id", sa.String(32), nullable=True),
        sa.Column("openid", sa.String(128), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("signed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("terminated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("termination_mode", sa.Integer(), nullable=True),
        sa.Column("next_deduct_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_deducted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["goulong_auth.users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("contract_code"),
        sa.UniqueConstraint("contract_id"),
    )
    op.create_index("ix_subscription_contracts_user_id", "subscription_contracts", ["user_id"])
    op.create_index("ix_subscription_contracts_contract_code", "subscription_contracts", ["contract_code"])

    op.create_table(
        "deduction_orders",
        sa.Column("id", UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", UUID(as_uuid=True), nullable=False),
        sa.Column("contract_id", UUID(as_uuid=True), nullable=False),
        sa.Column("out_trade_no", sa.String(32), nullable=False),
        sa.Column("transaction_id", sa.String(32), nullable=True),
        sa.Column("amount_cents", sa.Integer(), nullable=False),
        sa.Column("token_quota", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("trade_state", sa.String(32), nullable=True),
        sa.Column("failure_reason", sa.String(256), nullable=True),
        sa.Column("request_serial", sa.BigInteger(), nullable=False),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["goulong_auth.users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["contract_id"], ["subscription_contracts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("out_trade_no"),
    )
    op.create_index("ix_deduction_orders_user_id", "deduction_orders", ["user_id"])
    op.create_index("ix_deduction_orders_contract_id", "deduction_orders", ["contract_id"])
    op.create_index("ix_deduction_orders_out_trade_no", "deduction_orders", ["out_trade_no"])


def downgrade() -> None:
    op.drop_table("deduction_orders")
    op.drop_table("subscription_contracts")
    op.drop_table("payment_orders")
