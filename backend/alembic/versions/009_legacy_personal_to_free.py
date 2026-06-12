from __future__ import annotations

from alembic import op


revision = "009"
down_revision = "008"


def upgrade() -> None:
    op.execute(
        "UPDATE user_profiles SET subscription_plan='free', monthly_quota=50 "
        "WHERE subscription_plan='personal' AND quota_used=0"
    )


def downgrade() -> None:
    pass
