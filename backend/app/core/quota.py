from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from goulong_auth.models import Membership

FREE_MONTHLY_TOKEN_QUOTA = 200_000

INSUFFICIENT_QUOTA_DETAIL = {
    "code": "insufficient_quota",
    "message": "算力额度不足，请购买额度包后继续使用",
}


def effective_token_quota(membership) -> int:
    if membership is None:
        return FREE_MONTHLY_TOKEN_QUOTA
    quota = int(getattr(membership, "token_quota", 0) or 0)
    if quota <= 0:
        return FREE_MONTHLY_TOKEN_QUOTA
    return quota


def remaining_tokens(membership) -> int:
    if membership is None:
        return FREE_MONTHLY_TOKEN_QUOTA
    used = int(getattr(membership, "token_used", 0) or 0)
    return max(0, effective_token_quota(membership) - used)


async def require_quota(db: AsyncSession, user_id):
    membership = (
        await db.execute(
            select(Membership).where(
                Membership.user_id == user_id,
                Membership.product == "zhaodan",
                Membership.status == "active",
            )
        )
    ).scalar_one_or_none()
    if remaining_tokens(membership) <= 0:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=INSUFFICIENT_QUOTA_DETAIL,
        )
    return membership
