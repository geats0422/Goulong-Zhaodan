from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel
from sqlalchemy import select

from app.core.auth import CurrentUserContext, get_current_user
from app.core.config import settings
from app.core.database import get_db_session
from app.core.deps import get_client_ip
from goulong_auth.models import Membership
from app.services import subscription_service
from app.services.payment_catalog import get_product
from app.services.wechatpay_v2_client import WechatPayV2Client, WechatPayV2Error, get_wechatpay_v2_client

router = APIRouter(prefix="/subscription", tags=["订阅"])


class SubscribeCreateRequest(BaseModel):
    plan_code: str


class SubscribeCreateResponse(BaseModel):
    contract_code: str
    entrust_url: str
    plan_code: str
    plan_name: str
    amount_cents: int


class CurrentSubscriptionResponse(BaseModel):
    id: uuid.UUID | None = None
    plan_code: str
    plan_name: str
    status: str
    contract_id: str | None = None
    signed_at: str | None = None
    terminated_at: str | None = None
    next_deduct_at: str | None = None
    last_deducted_at: str | None = None
    token_quota_total: int = 0
    token_quota_used: int = 0
    is_active: bool = False


class DeductionHistoryItem(BaseModel):
    id: uuid.UUID
    out_trade_no: str
    amount_cents: int
    token_quota: int
    status: str
    trade_state: str | None = None
    paid_at: str | None = None
    created_at: str | None = None

    model_config = {"from_attributes": True}


@router.post("", response_model=SubscribeCreateResponse, status_code=status.HTTP_201_CREATED)
async def create_subscription(
    body: SubscribeCreateRequest,
    current_user: CurrentUserContext = Depends(get_current_user),
    db=Depends(get_db_session),
) -> SubscribeCreateResponse:
    if not subscription_service.is_papay_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="委托代扣功能未配置，请联系管理员",
        )
    product = get_product(body.plan_code)
    if product is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="不支持的订阅方案")
    try:
        contract, entrust_url = await subscription_service.create_subscribe_intent(
            db, current_user.user_id, body.plan_code
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from None

    return SubscribeCreateResponse(
        contract_code=contract.contract_code,
        entrust_url=entrust_url,
        plan_code=product.code,
        plan_name=product.name,
        amount_cents=product.amount_cents,
    )


@router.get("/current", response_model=CurrentSubscriptionResponse)
async def get_current_subscription(
    current_user: CurrentUserContext = Depends(get_current_user),
    db=Depends(get_db_session),
) -> CurrentSubscriptionResponse:
    user_id = current_user.user_id
    contract = await subscription_service.get_active_contract(db, user_id)
    membership = await _get_membership(db, user_id)
    token_total = membership.token_quota if membership else 0
    token_used = membership.token_used if membership else 0

    if contract is None:
        return CurrentSubscriptionResponse(
            plan_code="free",
            plan_name="Free",
            status="free",
            token_quota_total=token_total,
            token_quota_used=token_used,
            is_active=False,
        )

    product = get_product(contract.plan_code)
    return CurrentSubscriptionResponse(
        id=contract.id,
        plan_code=contract.plan_code,
        plan_name=product.name if product else contract.plan_code,
        status=contract.status,
        contract_id=contract.contract_id,
        signed_at=str(contract.signed_at) if contract.signed_at else None,
        terminated_at=str(contract.terminated_at) if contract.terminated_at else None,
        next_deduct_at=str(contract.next_deduct_at) if contract.next_deduct_at else None,
        last_deducted_at=str(contract.last_deducted_at) if contract.last_deducted_at else None,
        token_quota_total=token_total,
        token_quota_used=token_used,
        is_active=contract.status == "active",
    )


@router.delete("/{contract_id}", status_code=status.HTTP_204_NO_CONTENT)
async def cancel_subscription(
    contract_id: uuid.UUID,
    current_user: CurrentUserContext = Depends(get_current_user),
    db=Depends(get_db_session),
) -> None:
    contract = await subscription_service.get_contract_by_id(
        db, contract_id, current_user.user_id
    )
    if contract is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="订阅不存在")
    if contract.status != "active":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="订阅已终止")
    try:
        await subscription_service.cancel_contract(db, contract)
    except WechatPayV2Error as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e)) from None


@router.get("/deductions", response_model=list[DeductionHistoryItem])
async def list_deductions(
    current_user: CurrentUserContext = Depends(get_current_user),
    db=Depends(get_db_session),
) -> list[DeductionHistoryItem]:
    orders = await subscription_service.list_deduction_history(db, current_user.user_id)
    return [DeductionHistoryItem.model_validate(o) for o in orders]


@router.post("/deductions", status_code=status.HTTP_201_CREATED)
async def trigger_deduction(
    request: Request,
    current_user: CurrentUserContext = Depends(get_current_user),
    db=Depends(get_db_session),
) -> dict:
    if not subscription_service.is_papay_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="委托代扣功能未配置",
        )
    user_id = current_user.user_id
    contract = await subscription_service.get_active_contract(db, user_id)
    if contract is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="未找到有效签约")
    order = await subscription_service.create_deduction_order(
        db, user_id, contract.id, contract.plan_code
    )
    order = await subscription_service.execute_deduction(
        db, order, contract, get_client_ip(request)
    )
    if order.status == "failed":
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=order.failure_reason or "扣款失败")
    return {"order_id": str(order.id), "out_trade_no": order.out_trade_no, "status": order.status}


@router.post("/contract-notify", response_class=PlainTextResponse)
async def contract_notify(request: Request, db=Depends(get_db_session)) -> PlainTextResponse:
    body = (await request.body()).decode("utf-8")
    payload = get_wechatpay_v2_client().parse_callback_xml(body)
    if not WechatPayV2Client.verify_callback_sign(payload, settings.wechatpay_api_v2_key):
        return PlainTextResponse(
            content='<xml><return_code><![CDATA[FAIL]]></return_code><return_msg><![CDATA[签名错误]]></return_msg></xml>',
            media_type="application/xml",
        )
    await subscription_service.handle_contract_callback(db, payload)
    return PlainTextResponse(
        content='<xml><return_code><![CDATA[SUCCESS]]></return_code><return_msg><![CDATA[OK]]></return_msg></xml>',
        media_type="application/xml",
    )


@router.post("/deduction-notify", response_class=PlainTextResponse)
async def deduction_notify(request: Request, db=Depends(get_db_session)) -> PlainTextResponse:
    body = (await request.body()).decode("utf-8")
    payload = get_wechatpay_v2_client().parse_callback_xml(body)
    if not WechatPayV2Client.verify_callback_sign(payload, settings.wechatpay_api_v2_key):
        return PlainTextResponse(
            content='<xml><return_code><![CDATA[FAIL]]></return_code><return_msg><![CDATA[签名错误]]></return_msg></xml>',
            media_type="application/xml",
        )
    await subscription_service.handle_deduction_callback(db, payload)
    return PlainTextResponse(
        content='<xml><return_code><![CDATA[SUCCESS]]></return_code><return_msg><![CDATA[OK]]></return_msg></xml>',
        media_type="application/xml",
    )


async def _get_membership(db, user_id: uuid.UUID) -> Membership | None:
    result = await db.execute(
        select(Membership).where(
            Membership.user_id == user_id,
            Membership.product == "zhaodan",
        )
    )
    return result.scalar_one_or_none()
