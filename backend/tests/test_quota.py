import pytest
from dataclasses import dataclass
from unittest.mock import AsyncMock, MagicMock
from fastapi import HTTPException


@dataclass
class _MockMembership:
    token_quota: int = 0
    token_used: int = 0
    plan: str = "free"
    status: str = "active"


def test_no_membership_gets_free_quota():
    from app.core.quota import effective_token_quota, FREE_MONTHLY_TOKEN_QUOTA
    assert effective_token_quota(None) == FREE_MONTHLY_TOKEN_QUOTA
    assert FREE_MONTHLY_TOKEN_QUOTA == 200_000


def test_zero_quota_gets_free_fallback():
    from app.core.quota import effective_token_quota
    m = _MockMembership(token_quota=0, plan="free")
    assert effective_token_quota(m) == 200_000


def test_paid_quota_used_directly():
    from app.core.quota import effective_token_quota
    m = _MockMembership(token_quota=5_000_000, plan="pro")
    assert effective_token_quota(m) == 5_000_000


def test_remaining_no_used():
    from app.core.quota import remaining_tokens
    m = _MockMembership(token_quota=0, token_used=0, plan="free")
    assert remaining_tokens(m) == 200_000


def test_remaining_with_used():
    from app.core.quota import remaining_tokens
    m = _MockMembership(token_quota=0, token_used=50_000, plan="free")
    assert remaining_tokens(m) == 150_000


def test_remaining_exhausted():
    from app.core.quota import remaining_tokens
    m = _MockMembership(token_quota=0, token_used=200_000, plan="free")
    assert remaining_tokens(m) == 0


def test_remaining_no_membership():
    from app.core.quota import remaining_tokens
    assert remaining_tokens(None) == 200_000


@pytest.mark.asyncio
async def test_require_quota_allows_when_sufficient():
    from app.core.quota import require_quota
    m = _MockMembership(token_quota=0, token_used=0, plan="free")
    db = MagicMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = m
    db.execute = AsyncMock(return_value=result)
    user = MagicMock()
    user.user_id = "test-uid"
    out = await require_quota(db=db, user_id="test-uid")
    assert out is not None
    assert out.token_quota == 0


@pytest.mark.asyncio
async def test_require_quota_blocks_when_exhausted():
    from app.core.quota import require_quota
    m = _MockMembership(token_quota=0, token_used=200_000, plan="free")
    db = MagicMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = m
    db.execute = AsyncMock(return_value=result)
    with pytest.raises(HTTPException) as exc_info:
        await require_quota(db=db, user_id="test-uid")
    assert exc_info.value.status_code == 402
    assert exc_info.value.detail["code"] == "insufficient_quota"


@pytest.mark.asyncio
async def test_require_quota_free_fallback_when_no_membership():
    from app.core.quota import require_quota
    db = MagicMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    db.execute = AsyncMock(return_value=result)
    out = await require_quota(db=db, user_id="test-uid")
    assert out is None
