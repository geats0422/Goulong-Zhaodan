from __future__ import annotations

import logging
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from goulong_auth.models import Membership, User
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.payment import PaymentOrder, PaymentOrderEvent
from app.services.alipay_client import AlipayClient, AlipayError, get_alipay_client
from app.services.payment_catalog import get_product, is_addon
from app.services.wechatpay_client import WechatPayClient, WechatPayError, get_wechatpay_client

_logger = logging.getLogger(__name__)

ORDER_EXPIRE_MINUTES = 30

_ALLOWED_TRANSITIONS = {
    ("pending", "paid"),
    ("pending", "closed"),
    ("pending", "failed"),
    ("closed", "paid"),
}


def _generate_out_trade_no() -> str:
    ts = datetime.now(UTC).strftime("%Y%m%d%H%M%S")
    rand = secrets.token_hex(4).upper()
    return f"ZD{ts}{rand}"


def _client_ip_or_default(client_ip: str) -> str:
    return client_ip if client_ip and client_ip != "unknown" else "127.0.0.1"


async def create_native_order(
    db: AsyncSession,
    user_id: uuid.UUID,
    product_code: str,
    client_ip: str,
    *,
    is_pro: bool = False,
) -> PaymentOrder:
    product = get_product(product_code)
    if product is None:
        raise ValueError("不支持的支付产品")
    if product.product_type == "addon" and not product.free_user_allowed and not is_pro:
        raise ValueError("该产品仅 Pro 用户可购买")

    out_trade_no = _generate_out_trade_no()
    order = PaymentOrder(
        user_id=user_id,
        out_trade_no=out_trade_no,
        product_code=product.code,
        product_name=product.name,
        product_type=product.product_type,
        payment_method="wechat",
        amount_cents=product.amount_cents,
        token_quota=product.token_quota,
        status="pending",
        expires_at=datetime.now(UTC) + timedelta(minutes=ORDER_EXPIRE_MINUTES),
    )
    db.add(order)
    await db.commit()
    await db.refresh(order)

    client = get_wechatpay_client()
    code_url = await client.create_native_order(
        out_trade_no=out_trade_no,
        description=f"句龙·照胆 - {product.name}",
        amount_cents=product.amount_cents,
        client_ip=_client_ip_or_default(client_ip),
        attach=product.code,
    )
    order.code_url = code_url
    await db.commit()
    await db.refresh(order)
    return order


async def create_alipay_page_order(
    db: AsyncSession,
    user_id: uuid.UUID,
    product_code: str,
    *,
    is_pro: bool = False,
) -> tuple[PaymentOrder, str]:
    product = get_product(product_code)
    if product is None:
        raise ValueError("不支持的支付产品")
    if product.product_type == "addon" and not product.free_user_allowed and not is_pro:
        raise ValueError("该产品仅 Pro 用户可购买")

    out_trade_no = _generate_out_trade_no()
    order = PaymentOrder(
        user_id=user_id,
        out_trade_no=out_trade_no,
        product_code=product.code,
        product_name=product.name,
        product_type=product.product_type,
        payment_method="alipay",
        amount_cents=product.amount_cents,
        token_quota=product.token_quota,
        status="pending",
        expires_at=datetime.now(UTC) + timedelta(minutes=ORDER_EXPIRE_MINUTES),
    )
    db.add(order)
    await db.commit()
    await db.refresh(order)

    client = get_alipay_client()
    pay_url = client.build_page_pay_url(
        out_trade_no=out_trade_no,
        subject=f"句龙·照胆 - {product.name}",
        total_amount=Decimal(product.amount_cents) / Decimal(100),
        passback_params=product.code,
    )
    return order, pay_url


async def get_order_by_id(db: AsyncSession, order_id: uuid.UUID, user_id: uuid.UUID) -> PaymentOrder | None:
    result = await db.execute(
        select(PaymentOrder)
        .where(
            PaymentOrder.id == order_id, PaymentOrder.user_id == user_id
        )
        .with_for_update()
    )
    return result.scalar_one_or_none()


async def list_user_orders(db: AsyncSession, user_id: uuid.UUID, limit: int = 20) -> list[PaymentOrder]:
    result = await db.execute(
        select(PaymentOrder)
        .where(PaymentOrder.user_id == user_id)
        .order_by(PaymentOrder.created_at.desc())
        .limit(limit)
    )
    return list(result.scalars().all())


async def sync_order_status(db: AsyncSession, order: PaymentOrder) -> PaymentOrder:
    if order.status in ("paid", "closed", "failed"):
        return order
    if order.payment_method == "alipay":
        return await _sync_alipay_order(db, order)
    return await _sync_wechat_order(db, order)


async def _sync_wechat_order(db: AsyncSession, order: PaymentOrder) -> PaymentOrder:
    client = get_wechatpay_client()
    try:
        result = await client.query_order(order.out_trade_no)
    except WechatPayError:
        return order
    trade_state = result.get("trade_state", "")
    if trade_state == "SUCCESS":
        await _mark_paid(db, order, result.get("transaction_id"), event_type="sync_paid")
    elif trade_state == "CLOSED":
        await _transition_status(db, order, "closed", "sync_closed", trade_state)
    elif trade_state in ("PAYERROR", "REVOKED"):
        await _transition_status(db, order, "failed", "sync_failed", trade_state)
    return order


async def _sync_alipay_order(db: AsyncSession, order: PaymentOrder) -> PaymentOrder:
    client = get_alipay_client()
    try:
        result = await client.query_order(order.out_trade_no)
    except AlipayError:
        _logger.warning("支付宝查单失败 order=%s", order.out_trade_no)
        return order
    trade_status = result.get("trade_status", "")
    if trade_status in ("TRADE_SUCCESS", "TRADE_FINISHED"):
        await _mark_paid(db, order, result.get("trade_no"), event_type="sync_paid")
    elif trade_status == "TRADE_CLOSED":
        await _transition_status(db, order, "closed", "sync_closed", trade_status)
    return order


async def handle_callback(
    db: AsyncSession,
    client: WechatPayClient,
    decrypted: dict,
) -> bool:
    out_trade_no = decrypted.get("out_trade_no", "")
    result = await db.execute(
        select(PaymentOrder)
        .where(PaymentOrder.out_trade_no == out_trade_no)
        .with_for_update()
    )
    order = result.scalar_one_or_none()
    if order is None:
        return False
    if order.status == "paid":
        return True

    trade_state = decrypted.get("trade_state", "")
    if trade_state == "SUCCESS":
        transaction_id = decrypted.get("transaction_id")
        await _mark_paid(db, order, transaction_id)
        return True
    return False


async def handle_alipay_callback(
    db: AsyncSession,
    client: AlipayClient,
    data: dict[str, str],
) -> bool:
    out_trade_no = data.get("out_trade_no", "")
    result = await db.execute(
        select(PaymentOrder)
        .where(PaymentOrder.out_trade_no == out_trade_no)
        .with_for_update()
    )
    order = result.scalar_one_or_none()
    if order is None:
        return False
    if order.status == "paid":
        return True
    if data.get("app_id") != client.app_id:
        return False
    if client.seller_id and data.get("seller_id") != client.seller_id:
        return False
    total_amount = Decimal(data.get("total_amount", "0"))
    if total_amount != Decimal(order.amount_cents) / Decimal(100):
        return False
    if data.get("trade_status") in {"TRADE_SUCCESS", "TRADE_FINISHED"}:
        await _mark_paid(db, order, data.get("trade_no"))
        return True
    return False


async def _transition_status(
    db: AsyncSession,
    order: PaymentOrder,
    to_status: str,
    event_type: str,
    reason: str | None = None,
) -> bool:
    if order.status == to_status:
        return True
    if (order.status, to_status) not in _ALLOWED_TRANSITIONS:
        _logger.warning(
            "非法状态转换被拒绝: %s → %s order=%s",
            order.status,
            to_status,
            order.out_trade_no,
        )
        return False
    event = PaymentOrderEvent(
        order_id=order.id,
        from_status=order.status,
        to_status=to_status,
        event_type=event_type,
        reason=reason,
    )
    db.add(event)
    order.status = to_status
    await db.commit()
    await db.refresh(order)
    return True


async def _mark_paid(
    db: AsyncSession,
    order: PaymentOrder,
    transaction_id: str | None,
    *,
    event_type: str = "callback_paid",
) -> None:
    if order.status == "closed":
        event_type = "callback_paid_late"
    ok = await _transition_status(db, order, "paid", event_type)
    if not ok:
        return
    order.transaction_id = transaction_id
    order.paid_at = datetime.now(UTC)
    await _apply_quota(db, order)
    await db.commit()
    await db.refresh(order)
    await _send_payment_email(db, order)


async def _send_payment_email(db: AsyncSession, order: PaymentOrder) -> None:
    try:
        from app.services import email_service

        result = await db.execute(select(User).where(User.id == order.user_id))
        user = result.scalar_one_or_none()
        if not user or not user.email:
            return
        await email_service.send_payment_notification(
            to_address=user.email,
            username=user.nickname,
            product=order.product_name,
            plan="额度包" if is_addon(order.product_code) else "Pro 订阅",
            amount=f"{order.amount_cents / 100:.2f}",
            expire_date="永久有效" if is_addon(order.product_code) else "订阅周期内有效",
        )
    except Exception:
        _logger.warning("支付通知邮件发送失败 order=%s", order.out_trade_no)


async def _apply_quota(db: AsyncSession, order: PaymentOrder) -> None:
    result = await db.execute(
        select(Membership).where(
            Membership.user_id == order.user_id,
            Membership.product == "zhaodan",
            Membership.status == "active",
        )
    )
    membership = result.scalar_one_or_none()
    if membership is None:
        membership = Membership(
            user_id=order.user_id,
            product="zhaodan",
            plan="free",
            status="active",
            token_quota=0,
            token_used=0,
        )
        db.add(membership)
        await db.flush()

    if is_addon(order.product_code):
        membership.token_quota = (membership.token_quota or 0) + order.token_quota
    else:
        membership.plan = "pro"
        membership.token_quota = order.token_quota
        membership.started_at = datetime.now(UTC)
        if order.product_code == "pro_monthly":
            membership.expires_at = datetime.now(UTC) + timedelta(days=30)
        elif order.product_code == "pro_quarterly":
            membership.expires_at = datetime.now(UTC) + timedelta(days=90)
        elif order.product_code == "pro_yearly":
            membership.expires_at = datetime.now(UTC) + timedelta(days=365)


def is_wechatpay_configured() -> bool:
    return bool(
        settings.wechatpay_app_id
        and settings.wechatpay_mch_id
        and settings.wechatpay_api_v3_key
        and settings.wechatpay_cert_serial_no
        and (settings.wechatpay_private_key_pem or settings.wechatpay_private_key_path)
    )


def is_alipay_configured() -> bool:
    return bool(
        settings.alipay_app_id
        and settings.alipay_private_key_path
        and settings.alipay_public_key_path
        and settings.alipay_notify_url
        and settings.alipay_zhaodan_return_url
    )


async def close_expired_orders(db: AsyncSession, now: datetime | None = None) -> dict[str, int]:
    """关闭超时未支付的 pending 订单。"""
    now = now or datetime.now(UTC)
    result = await db.execute(
        select(PaymentOrder)
        .where(
            PaymentOrder.status == "pending",
            PaymentOrder.expires_at < now,
        )
    )
    orders = list(result.scalars().all())

    closed = 0
    skipped = 0
    paid_late = 0

    for order in orders:
        try:
            paid = await _query_and_close_order(db, order)
            if paid:
                paid_late += 1
            else:
                closed += 1
        except (WechatPayError, AlipayError) as e:
            _logger.warning("定时关单查单异常，跳过 order=%s err=%s", order.out_trade_no, e)
            skipped += 1

    _logger.info(
        "定时关单完成 closed=%d paid_late=%d skipped=%d total=%d",
        closed, paid_late, skipped, len(orders),
    )
    return {"closed": closed, "paid_late": paid_late, "skipped": skipped, "total": len(orders)}


async def _query_and_close_order(db: AsyncSession, order: PaymentOrder) -> bool:
    """查单并关单。返回 True 表示已支付（补救发额度），False 表示已关单。"""
    if order.payment_method == "alipay":
        alipay_client = get_alipay_client()
        result = await alipay_client.query_order(order.out_trade_no)
        trade_status = result.get("trade_status", "")
        if trade_status in ("TRADE_SUCCESS", "TRADE_FINISHED"):
            await _mark_paid(db, order, result.get("trade_no"), event_type="sync_paid")
            return True
        if trade_status == "TRADE_CLOSED":
            await _transition_status(db, order, "closed", "timeout_close", "alipay TRADE_CLOSED")
            return False
        await alipay_client.close_order(order.out_trade_no)
        await _transition_status(db, order, "closed", "timeout_close")
        return False

    wechat_client = get_wechatpay_client()
    result = await wechat_client.query_order(order.out_trade_no)
    trade_state = result.get("trade_state", "")
    if trade_state == "SUCCESS":
        await _mark_paid(db, order, result.get("transaction_id"), event_type="sync_paid")
        return True
    if trade_state in ("PAYERROR", "REVOKED"):
        await _transition_status(db, order, "failed", "sync_failed", trade_state)
        return False
    if trade_state == "CLOSED":
        await _transition_status(db, order, "closed", "timeout_close", trade_state)
        return False
    await wechat_client.close_order(order.out_trade_no)
    await _transition_status(db, order, "closed", "timeout_close")
    return False
