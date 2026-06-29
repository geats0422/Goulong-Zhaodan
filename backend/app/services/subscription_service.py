from __future__ import annotations

import secrets
import uuid
from datetime import UTC, datetime, timedelta

from goulong_auth.models import Membership
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.delegated_deduction import DeductionOrder, SubscriptionContract
from app.services.payment_catalog import get_product
from app.services.wechatpay_v2_client import WechatPayV2Error, get_wechatpay_v2_client


def _generate_contract_code() -> str:
    return f"ZD{uuid.uuid4().hex[:24].upper()}"


def _generate_out_trade_no(contract_id: uuid.UUID) -> str:
    ts = datetime.now(UTC).strftime("%Y%m%d%H%M%S")
    rand = secrets.token_hex(4).upper()
    return f"ZDD{ts}{rand}"[:32]


def _next_deduct_at(plan_code: str, base: datetime | None = None) -> datetime:
    base = base or datetime.now(UTC)
    if plan_code == "pro_monthly":
        return base + timedelta(days=30)
    if plan_code == "pro_quarterly":
        return base + timedelta(days=90)
    if plan_code == "pro_yearly":
        return base + timedelta(days=365)
    return base + timedelta(days=30)


async def create_subscribe_intent(
    db: AsyncSession,
    user_id: uuid.UUID,
    plan_code: str,
) -> tuple[SubscriptionContract, str]:
    product = get_product(plan_code)
    if product is None or product.product_type != "subscription":
        raise ValueError("不支持的订阅方案")

    client = get_wechatpay_v2_client()
    contract_code = _generate_contract_code()
    request_serial = client._request_serial()  # noqa: SLF001

    contract = SubscriptionContract(
        user_id=user_id,
        plan_code=plan_code,
        contract_code=contract_code,
        status="pending",
    )
    db.add(contract)
    await db.commit()
    await db.refresh(contract)

    display_account = f"用户{user_id.hex[:6].upper()}"
    entrust_url = client.build_entrust_url(
        contract_code=contract_code,
        contract_display_account=display_account,
        request_serial=request_serial,
    )
    return contract, entrust_url


async def get_active_contract(db: AsyncSession, user_id: uuid.UUID) -> SubscriptionContract | None:
    result = await db.execute(
        select(SubscriptionContract)
        .where(
            SubscriptionContract.user_id == user_id,
            SubscriptionContract.status == "active",
        )
        .order_by(SubscriptionContract.signed_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def get_contract_by_id(
    db: AsyncSession, contract_id: uuid.UUID, user_id: uuid.UUID
) -> SubscriptionContract | None:
    result = await db.execute(
        select(SubscriptionContract).where(
            SubscriptionContract.id == contract_id,
            SubscriptionContract.user_id == user_id,
        )
    )
    return result.scalar_one_or_none()


async def get_contract_by_code(db: AsyncSession, contract_code: str) -> SubscriptionContract | None:
    result = await db.execute(
        select(SubscriptionContract).where(SubscriptionContract.contract_code == contract_code)
    )
    return result.scalar_one_or_none()


async def handle_contract_callback(db: AsyncSession, payload: dict) -> bool:
    contract_code = payload.get("contract_code", "")
    change_type = payload.get("change_type", "")

    contract = await get_contract_by_code(db, contract_code)
    if contract is None:
        return False

    if change_type == "ADD":
        contract.contract_id = payload.get("contract_id", contract.contract_id)
        contract.openid = payload.get("openid", contract.openid)
        contract.status = "active"
        contract.signed_at = _parse_dt(payload.get("operate_time"))
        contract.terminated_at = None
        contract.termination_mode = None
        contract.next_deduct_at = _next_deduct_at(contract.plan_code, contract.signed_at)
        await _apply_subscription(db, contract)
    elif change_type == "DELETE":
        contract.status = "terminated"
        contract.terminated_at = _parse_dt(payload.get("operate_time"))
        try:
            contract.termination_mode = int(payload.get("contract_termination_mode", 0)) or None
        except (TypeError, ValueError):
            contract.termination_mode = None
        await _clear_subscription(db, contract)

    await db.commit()
    await db.refresh(contract)
    return True


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y%m%d%H%M%S"):
        try:
            return datetime.strptime(value, fmt).replace(tzinfo=UTC)
        except ValueError:
            continue
    return None


async def _apply_subscription(db: AsyncSession, contract: SubscriptionContract) -> None:
    product = get_product(contract.plan_code)
    if product is None:
        return
    result = await db.execute(
        select(Membership).where(
            Membership.user_id == contract.user_id,
            Membership.product == "zhaodan",
        )
    )
    membership = result.scalar_one_or_none()
    if membership is None:
        membership = Membership(
            user_id=contract.user_id,
            product="zhaodan",
            plan="pro",
            status="active",
            token_quota=product.token_quota,
            token_used=0,
        )
        db.add(membership)
    else:
        membership.plan = "pro"
        membership.status = "active"
        membership.token_quota = product.token_quota
        membership.token_used = 0
    if contract.signed_at:
        membership.started_at = contract.signed_at
    membership.expires_at = _next_deduct_at(contract.plan_code, contract.signed_at)


async def _clear_subscription(db: AsyncSession, contract: SubscriptionContract) -> None:
    result = await db.execute(
        select(Membership).where(
            Membership.user_id == contract.user_id,
            Membership.product == "zhaodan",
        )
    )
    membership = result.scalar_one_or_none()
    if membership is None:
        return
    membership.status = "active"
    membership.plan = "free"
    membership.token_quota = 0
    membership.token_used = 0
    membership.expires_at = None


async def cancel_contract(
    db: AsyncSession, contract: SubscriptionContract, remark: str = "用户主动取消订阅"
) -> None:
    client = get_wechatpay_v2_client()
    if contract.contract_id:
        try:
            await client.delete_contract(contract_id=contract.contract_id, remark=remark)
        except WechatPayV2Error:
            pass
    contract.status = "terminated"
    contract.terminated_at = datetime.now(UTC)
    contract.termination_mode = 3
    await _clear_subscription(db, contract)
    await db.commit()


async def create_deduction_order(
    db: AsyncSession,
    user_id: uuid.UUID,
    contract_id: uuid.UUID,
    plan_code: str,
) -> DeductionOrder:
    product = get_product(plan_code)
    if product is None or product.product_type != "subscription":
        raise ValueError("不支持的订阅方案")

    contract = await get_contract_by_id(db, contract_id, user_id)
    if contract is None or contract.status != "active" or not contract.contract_id:
        raise ValueError("签约关系未激活")

    out_trade_no = _generate_out_trade_no(contract_id)
    order = DeductionOrder(
        user_id=user_id,
        contract_id=contract_id,
        out_trade_no=out_trade_no,
        amount_cents=product.amount_cents,
        token_quota=product.token_quota,
        status="pending",
        request_serial=get_wechatpay_v2_client()._request_serial(),  # noqa: SLF001
    )
    db.add(order)
    await db.commit()
    await db.refresh(order)
    return order


async def execute_deduction(
    db: AsyncSession,
    order: DeductionOrder,
    contract: SubscriptionContract,
    client_ip: str,
) -> DeductionOrder:
    client = get_wechatpay_v2_client()
    try:
        await client.apply_deduction(
            out_trade_no=order.out_trade_no,
            contract_id=contract.contract_id or "",
            body=f"句龙·照胆 {contract.plan_code}",
            total_fee=order.amount_cents,
            client_ip=client_ip,
            attach=contract.plan_code,
        )
    except WechatPayV2Error as e:
        order.status = "failed"
        order.failure_reason = str(e)
        await db.commit()
        await db.refresh(order)
        return order
    order.status = "accepted"
    await db.commit()
    await db.refresh(order)
    return order


async def handle_deduction_callback(db: AsyncSession, payload: dict) -> bool:
    out_trade_no = payload.get("out_trade_no", "")
    result = await db.execute(
        select(DeductionOrder).where(DeductionOrder.out_trade_no == out_trade_no)
    )
    order = result.scalar_one_or_none()
    if order is None or order.status == "paid":
        return order is not None

    trade_state = payload.get("trade_state", "")

    if trade_state == "SUCCESS":
        order.status = "paid"
        order.trade_state = "SUCCESS"
        order.transaction_id = payload.get("transaction_id", order.transaction_id)
        time_end = payload.get("time_end", "")
        if time_end and len(time_end) == 14:
            try:
                order.paid_at = datetime.strptime(time_end, "%Y%m%d%H%M%S").replace(tzinfo=UTC)
            except ValueError:
                order.paid_at = datetime.now(UTC)
        else:
            order.paid_at = datetime.now(UTC)

        contract = await get_contract_by_id(db, order.contract_id, order.user_id)
        if contract is not None:
            contract.last_deducted_at = order.paid_at
            contract.next_deduct_at = _next_deduct_at(contract.plan_code, order.paid_at)
            await _refresh_membership_quota(db, contract)
        await db.commit()
        await db.refresh(order)
        return True
    order.status = "failed"
    order.trade_state = trade_state
    order.failure_reason = payload.get("err_code_des", "扣款失败")
    await db.commit()
    await db.refresh(order)
    return True


async def _refresh_membership_quota(db: AsyncSession, contract: SubscriptionContract) -> None:
    product = get_product(contract.plan_code)
    if product is None:
        return
    result = await db.execute(
        select(Membership).where(
            Membership.user_id == contract.user_id,
            Membership.product == "zhaodan",
        )
    )
    membership = result.scalar_one_or_none()
    if membership is None:
        return
    membership.plan = "pro"
    membership.status = "active"
    membership.token_quota = product.token_quota
    membership.token_used = 0
    membership.started_at = contract.last_deducted_at or datetime.now(UTC)
    membership.expires_at = _next_deduct_at(contract.plan_code, membership.started_at)


async def list_deduction_history(
    db: AsyncSession, user_id: uuid.UUID, limit: int = 20
) -> list[DeductionOrder]:
    result = await db.execute(
        select(DeductionOrder)
        .where(DeductionOrder.user_id == user_id)
        .order_by(DeductionOrder.created_at.desc())
        .limit(limit)
    )
    return list(result.scalars().all())


def is_papay_configured() -> bool:
    return bool(
        settings.wechatpay_app_id
        and settings.wechatpay_mch_id
        and settings.wechatpay_api_v2_key
        and settings.wechatpay_papay_plan_id
        and settings.wechatpay_papay_notify_url
        and settings.wechatpay_papay_deduct_notify_url
    )
