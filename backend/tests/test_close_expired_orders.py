import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.database import async_session
from app.models.payment import PaymentOrder
from app.services import payment_service
from app.services.wechatpay_client import WechatPayError
from goulong_auth.models import Membership, User


async def _create_user_and_order(db, **order_kwargs):
    user = User(
        email=f"test{uuid.uuid4().hex[:8]}@example.com",
        nickname="测试",
        hashed_password="$2b$12$dummyplaceholdernotrealbutvalidlengthhash",
    )
    db.add(user)
    await db.flush()
    membership = Membership(
        user_id=user.id,
        product="zhaodan",
        plan="free",
        status="active",
        token_quota=10000,
        token_used=0,
    )
    db.add(membership)
    defaults = dict(
        user_id=user.id,
        out_trade_no=f"ZD{datetime.now(UTC).strftime('%Y%m%d%H%M%S%f')}{uuid.uuid4().hex[:8].upper()}",
        product_code="light",
        product_name="轻量包",
        product_type="addon",
        payment_method="wechat",
        amount_cents=1900,
        token_quota=100000,
        status="pending",
        expires_at=datetime.now(UTC) + timedelta(minutes=30),
    )
    defaults.update(order_kwargs)
    order = PaymentOrder(**defaults)
    db.add(order)
    await db.commit()
    await db.refresh(order)
    return order


@pytest.mark.asyncio
async def test_close_expired_only_closes_pending_expired(monkeypatch):
    async with async_session() as db:
        expired = await _create_user_and_order(
            db, status="pending", expires_at=datetime.now(UTC) - timedelta(minutes=5)
        )
        active = await _create_user_and_order(
            db, status="pending", expires_at=datetime.now(UTC) + timedelta(minutes=30)
        )
        mock_wechat = MagicMock()
        mock_wechat.query_order = AsyncMock(return_value={"trade_state": "NOTPAY"})
        mock_wechat.close_order = AsyncMock(return_value=None)
        monkeypatch.setattr(payment_service, "get_wechatpay_client", lambda: mock_wechat)

        result = await payment_service.close_expired_orders(db)
        assert result["closed"] == 1

        await db.refresh(expired)
        await db.refresh(active)
        assert expired.status == "closed"
        assert active.status == "pending"


@pytest.mark.asyncio
async def test_close_expired_query_finds_paid(monkeypatch):
    async with async_session() as db:
        expired = await _create_user_and_order(
            db, status="pending", expires_at=datetime.now(UTC) - timedelta(minutes=5)
        )
        mock_wechat = MagicMock()
        mock_wechat.query_order = AsyncMock(
            return_value={"trade_state": "SUCCESS", "transaction_id": "txn_123"}
        )
        monkeypatch.setattr(payment_service, "get_wechatpay_client", lambda: mock_wechat)

        result = await payment_service.close_expired_orders(db)
        assert result["paid_late"] == 1
        assert result["closed"] == 0

        await db.refresh(expired)
        assert expired.status == "paid"


@pytest.mark.asyncio
async def test_close_expired_query_error_skips(monkeypatch):
    async with async_session() as db:
        expired = await _create_user_and_order(
            db, status="pending", expires_at=datetime.now(UTC) - timedelta(minutes=5)
        )
        mock_wechat = MagicMock()
        mock_wechat.query_order = AsyncMock(side_effect=WechatPayError("系统错误"))
        monkeypatch.setattr(payment_service, "get_wechatpay_client", lambda: mock_wechat)

        result = await payment_service.close_expired_orders(db)
        assert result["skipped"] == 1
        assert result["closed"] == 0

        await db.refresh(expired)
        assert expired.status == "pending"
