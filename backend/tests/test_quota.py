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
    detail = exc_info.value.detail
    assert detail["code"] == "insufficient_quota"


def test_insufficient_quota_detail_contract_is_stable_and_frontend_ready():
    """统一额度不足错误契约：稳定错误码 + 统一文案 + 前端可识别的账单跳转结构。

    所有解析/审查入口（/parse、/upload、/sessions/{id}/inspect、agent /inspect、
    知识库上传）共享同一 ``require_quota`` 门，因此该结构是后端唯一额度不足响应。
    """
    from app.core.quota import INSUFFICIENT_QUOTA_DETAIL

    # 稳定错误码：前端据此识别额度不足并打开账单弹窗。
    assert INSUFFICIENT_QUOTA_DETAIL["code"] == "insufficient_quota"
    # 统一文案：与设计稿“当前账户额度不足 / 本次审查需要更多算力额度。”一致。
    message = INSUFFICIENT_QUOTA_DETAIL["message"]
    assert "当前账户额度不足" in message
    assert "算力额度" in message
    # 前端可识别的账单跳转结构：按钮统一跳转 /settings?tab=billing，不再指向 /pricing。
    action = INSUFFICIENT_QUOTA_DETAIL["action"]
    assert action["type"] == "billing"
    assert action["path"] == "/settings?tab=billing"
    assert action["label"]  # 按钮文案非空
    # 不暴露内部实现细节：响应中不得出现模型名、内部路径或 token 数量等敏感信息。
    serialized = repr(INSUFFICIENT_QUOTA_DETAIL)
    for forbidden in ("model", "deepseek", "token_used", "token_quota", "/app/", "traceback"):
        assert forbidden not in serialized.lower(), (
            f"额度不足响应不应暴露内部实现细节：{forbidden}"
        )


@pytest.mark.asyncio
async def test_require_quota_blocks_returns_unified_402_payload(monkeypatch):
    """require_quota 抛出的 402 必须携带统一契约结构（含 action 账单跳转）。"""
    from app.core.quota import INSUFFICIENT_QUOTA_DETAIL, require_quota

    _set_environment(monkeypatch, "production")
    m = _MockMembership(token_quota=0, token_used=200_000, plan="free")
    db = MagicMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = m
    db.execute = AsyncMock(return_value=result)

    with pytest.raises(HTTPException) as exc_info:
        await require_quota(db=db, user_id="test-uid")

    assert exc_info.value.status_code == 402
    # 抛出的 detail 必须与契约常量完全一致，保证所有入口同构。
    assert exc_info.value.detail == INSUFFICIENT_QUOTA_DETAIL


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
