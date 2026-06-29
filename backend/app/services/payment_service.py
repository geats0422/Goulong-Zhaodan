from __future__ import annotations

import secrets
import uuid
from datetime import UTC, datetime, timedelta

from goulong_auth.models import Membership, User
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.payment import PaymentOrder
from app.services.payment_catalog import get_product, is_addon
from app.services.wechatpay_client import WechatPayClient, WechatPayError, get_wechatpay_client

ORDER_EXPIRE_MINUTES = 30


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


async def get_order_by_id(db: AsyncSession, order_id: uuid.UUID, user_id: uuid.UUID) -> PaymentOrder | None:
    result = await db.execute(
        select(PaymentOrder).where(
            PaymentOrder.id == order_id, PaymentOrder.user_id == user_id
        )
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
    if order.status == "paid":
        return order
    client = get_wechatpay_client()
    try:
        result = await client.query_order(order.out_trade_no)
    except WechatPayError:
        return order
    trade_state = result.get("trade_state", "")
    if trade_state == "SUCCESS":
        await _mark_paid(db, order, result.get("transaction_id"))
    elif trade_state in ("CLOSED", "PAYERROR", "REVOKED"):
        order.status = "closed"
        await db.commit()
        await db.refresh(order)
    return order


async def handle_callback(
    db: AsyncSession,
    client: WechatPayClient,
    decrypted: dict,
) -> bool:
    out_trade_no = decrypted.get("out_trade_no", "")
    result = await db.execute(
        select(PaymentOrder).where(PaymentOrder.out_trade_no == out_trade_no)
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


async def _mark_paid(
    db: AsyncSession,
    order: PaymentOrder,
    transaction_id: str | None,
) -> None:
    order.status = "paid"
    order.transaction_id = transaction_id
    order.paid_at = datetime.now(UTC)
    await _apply_quota(db, order)
    await db.commit()
    await db.refresh(order)
    await _send_payment_email(db, order)


async def _send_payment_email(db: AsyncSession, order: PaymentOrder) -> None:
    import logging

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
        logging.getLogger(__name__).warning("支付通知邮件发送失败 order=%s", order.out_trade_no)


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
