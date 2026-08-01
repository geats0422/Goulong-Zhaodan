from __future__ import annotations

import datetime
import logging
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.model_config import token_multiplier
from app.models.compute import ComputeUsageRecord
from goulong_auth.models import Membership

logger = logging.getLogger(__name__)

PRODUCT = "zhaodan"


def usage_idempotency_key(job_id: str, input_hash: str, business_type: str) -> str:
    return f"{job_id}:{input_hash}:{business_type}"


async def record_usage(
    db: AsyncSession,
    user_id: str | uuid.UUID,
    *,
    business_type: str,
    document_name: str,
    tokens_used: int,
    model_name: str,
    duration_seconds: float = 0.0,
    idempotency_key: str | None = None,
) -> int:
    """记录一次 LLM 调用的 token 消耗并扣减额度。

    quota_consumed = tokens_used × 模型倍率(flash=1, pro=3)。
    仅 flush 不 commit，事务由调用方管理。
    返回 quota_consumed（0 表示跳过：匿名用户或 tokens 为 0）。
    """
    try:
        tokens_used = int(tokens_used)
    except (TypeError, ValueError):
        return 0
    if tokens_used <= 0:
        return 0
    try:
        uuid.UUID(str(user_id))
    except (ValueError, TypeError):
        return 0

    multiplier = token_multiplier(model_name)
    quota_consumed = tokens_used * multiplier

    try:
        if idempotency_key:
            existing = (
                await db.execute(
                    select(ComputeUsageRecord).where(
                        ComputeUsageRecord.user_id == user_id,
                        ComputeUsageRecord.idempotency_key == idempotency_key,
                    )
                )
            ).scalar_one_or_none()
            if existing is not None:
                return existing.quota_consumed
        record = ComputeUsageRecord(
            user_id=user_id,
            document_name=document_name or "未命名文档",
            business_type=business_type,
            model_name=model_name,
            tokens_used=tokens_used,
            multiplier=multiplier,
            quota_consumed=quota_consumed,
            duration_seconds=duration_seconds,
            completed_at=datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None),
            idempotency_key=idempotency_key,
        )
        db.add(record)

        membership = (
            await db.execute(
                select(Membership).where(
                    Membership.user_id == user_id,
                    Membership.product == PRODUCT,
                    Membership.status == "active",
                )
            )
        ).scalar_one_or_none()
        if membership is not None:
            membership.token_used = (membership.token_used or 0) + quota_consumed

        await db.flush()
        return quota_consumed
    except Exception:
        logger.warning("compute_recorder.record_usage 失败 (scene=%s)", business_type, exc_info=True)
        return 0
