import pytest
from dataclasses import dataclass
from unittest.mock import AsyncMock, MagicMock
from fastapi import HTTPException

from app.core import config


@dataclass
class _MockMembership:
    token_quota: int = 0
    token_used: int = 0
    plan: str = "free"
    status: str = "active"


def _set_environment(monkeypatch, value: str) -> None:
    """统一修改全局 settings.environment，覆盖 quota 模块持有的同一实例。"""
    monkeypatch.setattr(config.settings, "environment", value)


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


def test_is_quota_enforced_reflects_environment(monkeypatch):
    """额度拦截仅在 production 生效。"""
    from app.core.quota import is_quota_enforced

    for value in ("local", "development"):
        _set_environment(monkeypatch, value)
        assert is_quota_enforced() is False
    _set_environment(monkeypatch, "production")
    assert is_quota_enforced() is True


@pytest.mark.asyncio
async def test_require_quota_skips_in_local_environment(monkeypatch):
    """local 只记录使用量不拦截：不查询 DB，直接放行。"""
    from app.core.quota import require_quota

    _set_environment(monkeypatch, "local")
    db = MagicMock()
    db.execute = AsyncMock()
    out = await require_quota(db=db, user_id="test-uid")
    assert out is None
    db.execute.assert_not_called()


@pytest.mark.asyncio
async def test_require_quota_skips_in_development_environment(monkeypatch):
    """development 按 local 处理，同样不拦截。"""
    from app.core.quota import require_quota

    _set_environment(monkeypatch, "development")
    db = MagicMock()
    db.execute = AsyncMock()
    out = await require_quota(db=db, user_id="test-uid")
    assert out is None
    db.execute.assert_not_called()


@pytest.mark.asyncio
async def test_require_quota_allows_when_sufficient(monkeypatch):
    from app.core.quota import require_quota

    _set_environment(monkeypatch, "production")
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
async def test_require_quota_blocks_when_exhausted(monkeypatch):
    from app.core.quota import require_quota

    _set_environment(monkeypatch, "production")
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
async def test_require_quota_free_fallback_when_no_membership(monkeypatch):
    from app.core.quota import require_quota

    _set_environment(monkeypatch, "production")
    db = MagicMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    db.execute = AsyncMock(return_value=result)
    out = await require_quota(db=db, user_id="test-uid")
    assert out is None


@pytest.mark.asyncio
async def test_usage_recording_not_blocked_in_local_environment(monkeypatch):
    """调用量记录不被本地环境阻断：local 下额度门放行，record_usage 仍照常记录。"""
    from app.core.quota import require_quota
    from app.services.compute_recorder import record_usage

    _set_environment(monkeypatch, "local")

    # 额度门不拦截
    gate_db = MagicMock()
    gate_db.execute = AsyncMock()
    assert await require_quota(db=gate_db, user_id="test-uid") is None

    # record_usage 与环境无关，仍尝试写入使用量（无幂等键 → db.add 分支）
    record_db = MagicMock()
    record_db.execute = AsyncMock(return_value=MagicMock())
    record_db.flush = AsyncMock()
    consumed = await record_usage(
        record_db,
        "12345678-1234-1234-1234-123456789012",
        business_type="inspection_summary",
        document_name="合同.txt",
        tokens_used=100,
        model_name="deepseek-v4-flash",
    )
    assert consumed == 100
    record_db.add.assert_called_once()
