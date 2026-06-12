from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "011"
down_revision = "010"


def upgrade() -> None:
    op.add_column("user_profiles", sa.Column("phone", sa.String(32), nullable=True))
    op.add_column("user_profiles", sa.Column("email", sa.String(255), nullable=True))
    op.create_unique_constraint("uq_user_profile_phone", "user_profiles", ["phone"])
    op.create_unique_constraint("uq_user_profile_email", "user_profiles", ["email"])


def downgrade() -> None:
    op.drop_constraint("uq_user_profile_email", "user_profiles", type_="unique")
    op.drop_constraint("uq_user_profile_phone", "user_profiles", type_="unique")
    op.drop_column("user_profiles", "email")
    op.drop_column("user_profiles", "phone")
