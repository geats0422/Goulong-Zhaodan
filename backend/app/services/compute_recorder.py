from __future__ import annotations

import datetime
import uuid

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.model_config import token_multiplier
from app.models.compute import ComputeUsageRecord
from goulong_auth.models import Membership

PRODUCT = "zhaodan"


def usage_idempotency_key(attempt_id: str, input_hash: str, business_type: str) -> str:
    """为一次稳定 attempt 的同一输入和业务阶段生成计费幂等键。"""
    return f"{attempt_id}:{input_hash}:{business_type}"


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
        values = dict(
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
        inserted = True
        if idempotency_key:
            result = await db.execute(
                pg_insert(ComputeUsageRecord)
                .values(**values)
                .on_conflict_do_nothing(index_elements=["user_id", "idempotency_key"])
                .returning(ComputeUsageRecord.quota_consumed)
            )
            quota_value = result.scalar_one_or_none()
            if quota_value is None:
                inserted = False
                existing = (
                    await db.execute(
                        select(ComputeUsageRecord.quota_consumed).where(
                            ComputeUsageRecord.user_id == user_id,
                            ComputeUsageRecord.idempotency_key == idempotency_key,
                        )
                    )
                ).scalar_one_or_none()
                if existing is None:
                    raise RuntimeError("幂等 usage 冲突后未找到原记录")
                return int(existing)
        else:
            db.add(ComputeUsageRecord(**values))

        if inserted:
            await db.execute(
                update(Membership)
                .where(
                    Membership.user_id == user_id,
                    Membership.product == PRODUCT,
                    Membership.status == "active",
                )
                .values(token_used=func.coalesce(Membership.token_used, 0) + quota_consumed)
            )

        await db.flush()
        return quota_consumed
    except IntegrityError:
        await db.rollback()
        raise
    except Exception:
        await db.rollback()
        raise
