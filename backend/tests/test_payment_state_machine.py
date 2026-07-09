import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy import select

from app.core.database import async_session
from app.models.payment import PaymentOrder, PaymentOrderEvent
from app.services import payment_service
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
async def test_transition_status_writes_event():
    async with async_session() as db:
        order = await _create_user_and_order(db)
        ok = await payment_service._transition_status(db, order, "closed", "timeout_close")
        assert ok is True
        assert order.status == "closed"
        events = (await db.execute(
            select(PaymentOrderEvent).where(PaymentOrderEvent.order_id == order.id)
        )).scalars().all()
        assert len(events) == 1


@pytest.mark.asyncio
async def test_transition_status_idempotent():
    async with async_session() as db:
        order = await _create_user_and_order(db)
        await payment_service._transition_status(db, order, "closed", "timeout_close")
        await payment_service._transition_status(db, order, "closed", "timeout_close")
        events = (await db.execute(
            select(PaymentOrderEvent).where(PaymentOrderEvent.order_id == order.id)
        )).scalars().all()
        assert len(events) == 1


@pytest.mark.asyncio
async def test_transition_status_rejects_illegal():
    async with async_session() as db:
        order = await _create_user_and_order(db, status="paid")
        ok = await payment_service._transition_status(db, order, "closed", "illegal")
        assert ok is False
        assert order.status == "paid"


@pytest.mark.asyncio
async def test_mark_paid_closed_to_paid_exception():
    async with async_session() as db:
        order = await _create_user_and_order(db, status="closed")
        await payment_service._mark_paid(db, order, "txn_late_123")
        assert order.status == "paid"
        events = (await db.execute(
            select(PaymentOrderEvent).where(PaymentOrderEvent.order_id == order.id)
        )).scalars().all()
        assert len(events) == 1
        assert events[0].event_type == "callback_paid_late"


@pytest.mark.asyncio
async def test_sync_alipay_trade_success(monkeypatch):
    async with async_session() as db:
        order = await _create_user_and_order(db, payment_method="alipay")
        mock_client = MagicMock()
        mock_client.query_order = AsyncMock(return_value={
            "trade_status": "TRADE_SUCCESS",
            "trade_no": "alipay_txn_123",
        })
        monkeypatch.setattr(payment_service, "get_alipay_client", lambda: mock_client)
        await payment_service.sync_order_status(db, order)
        assert order.status == "paid"


@pytest.mark.asyncio
async def test_sync_alipay_trade_closed(monkeypatch):
    async with async_session() as db:
        order = await _create_user_and_order(db, payment_method="alipay")
        mock_client = MagicMock()
        mock_client.query_order = AsyncMock(return_value={"trade_status": "TRADE_CLOSED"})
        monkeypatch.setattr(payment_service, "get_alipay_client", lambda: mock_client)
        await payment_service.sync_order_status(db, order)
        assert order.status == "closed"


@pytest.mark.asyncio
async def test_sync_wechat_payerror_to_failed(monkeypatch):
    async with async_session() as db:
        order = await _create_user_and_order(db, payment_method="wechat")
        mock_client = MagicMock()
        mock_client.query_order = AsyncMock(return_value={"trade_state": "PAYERROR"})
        monkeypatch.setattr(payment_service, "get_wechatpay_client", lambda: mock_client)
        await payment_service.sync_order_status(db, order)
        assert order.status == "failed"
