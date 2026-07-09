from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse, PlainTextResponse
from pydantic import BaseModel
from sqlalchemy import select

from app.core.auth import CurrentUserContext, get_current_user
from app.core.database import get_db_session
from app.core.deps import get_client_ip
from goulong_auth.models import Membership
from app.services import payment_service
from app.services.alipay_client import AlipayError, get_alipay_client
from app.services.wechatpay_client import WechatPayError, get_wechatpay_client

router = APIRouter(prefix="/payment", tags=["支付"])


class NativeOrderRequest(BaseModel):
    product_code: str


class NativeOrderResponse(BaseModel):
    order_id: uuid.UUID
    out_trade_no: str
    product_code: str
    product_name: str
    amount_cents: int
    code_url: str


class AlipayPageOrderRequest(BaseModel):
    product_code: str


class AlipayPageOrderResponse(BaseModel):
    order_id: uuid.UUID
    out_trade_no: str
    product_code: str
    product_name: str
    amount_cents: int
    pay_url: str


class PaymentOrderStatusResponse(BaseModel):
    id: uuid.UUID
    out_trade_no: str
    product_code: str
    product_name: str
    amount_cents: int
    status: str
    code_url: str | None = None
    transaction_id: str | None = None
    paid_at: str | None = None
    created_at: str | None = None

    model_config = {"from_attributes": True}


class PaymentOrderListItem(BaseModel):
    id: uuid.UUID
    out_trade_no: str
    product_code: str
    product_name: str
    amount_cents: int
    status: str
    paid_at: str | None = None
    created_at: str | None = None

    model_config = {"from_attributes": True}


@router.post("/native", response_model=NativeOrderResponse, status_code=status.HTTP_201_CREATED)
async def create_native_order(
    body: NativeOrderRequest,
    request: Request,
    current_user: CurrentUserContext = Depends(get_current_user),
    db=Depends(get_db_session),
) -> NativeOrderResponse:
    user_id = current_user.user_id
    try:
        order = await payment_service.create_native_order(
            db,
            user_id,
            body.product_code,
            get_client_ip(request),
            is_pro=await _user_is_pro(db, user_id),
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from None
    except WechatPayError as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail=f"微信支付下单失败: {e}"
        ) from None
    return NativeOrderResponse(
        order_id=order.id,
        out_trade_no=order.out_trade_no,
        product_code=order.product_code,
        product_name=order.product_name,
        amount_cents=order.amount_cents,
        code_url=order.code_url or "",
    )


@router.post("/alipay/page", response_model=AlipayPageOrderResponse, status_code=status.HTTP_201_CREATED)
async def create_alipay_page_order(
    body: AlipayPageOrderRequest,
    current_user: CurrentUserContext = Depends(get_current_user),
    db=Depends(get_db_session),
) -> AlipayPageOrderResponse:
    user_id = current_user.user_id
    try:
        order, pay_url = await payment_service.create_alipay_page_order(
            db,
            user_id,
            body.product_code,
            is_pro=await _user_is_pro(db, user_id),
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from None
    except AlipayError as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail=f"支付宝下单失败: {e}"
        ) from None
    return AlipayPageOrderResponse(
        order_id=order.id,
        out_trade_no=order.out_trade_no,
        product_code=order.product_code,
        product_name=order.product_name,
        amount_cents=order.amount_cents,
        pay_url=pay_url,
    )


@router.get("/orders/{order_id}", response_model=PaymentOrderStatusResponse)
async def get_order_status(
    order_id: uuid.UUID,
    current_user: CurrentUserContext = Depends(get_current_user),
    db=Depends(get_db_session),
) -> PaymentOrderStatusResponse:
    order = await payment_service.get_order_by_id(db, order_id, current_user.user_id)
    if order is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="订单不存在")
    order = await payment_service.sync_order_status(db, order)
    return PaymentOrderStatusResponse.model_validate(order)


@router.get("/orders", response_model=list[PaymentOrderListItem])
async def list_orders(
    current_user: CurrentUserContext = Depends(get_current_user),
    db=Depends(get_db_session),
) -> list[PaymentOrderListItem]:
    orders = await payment_service.list_user_orders(db, current_user.user_id)
    return [PaymentOrderListItem.model_validate(o) for o in orders]


@router.post("/notify")
async def wechatpay_notify(request: Request, db=Depends(get_db_session)) -> JSONResponse:
    import json

    body = await request.body()
    body_text = body.decode()

    timestamp = request.headers.get("Wechatpay-Timestamp", "")
    nonce = request.headers.get("Wechatpay-Nonce", "")
    signature = request.headers.get("Wechatpay-Signature", "")
    serial = request.headers.get("Wechatpay-Serial", "")

    client = get_wechatpay_client()
    await client.ensure_platform_cert(serial)

    if not client.verify_callback(
        timestamp=timestamp,
        nonce=nonce,
        body=body_text,
        signature_b64=signature,
        serial=serial,
    ):
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"code": "FAIL", "message": "验签失败"},
        )

    try:
        notification = json.loads(body_text)
        resource = notification.get("resource", {})
        decrypted = client.decrypt_callback(resource)
    except Exception:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"code": "FAIL", "message": "解密失败"},
        )

    handled = await payment_service.handle_callback(db, client, decrypted)
    if not handled:
        import logging as _logging
        _logging.getLogger(__name__).error(
            "微信回调业务处理失败（订单不存在/状态不符）decrypted=%s", decrypted
        )
    return JSONResponse(status_code=status.HTTP_200_OK, content={})


@router.post("/alipay/notify", response_class=PlainTextResponse)
async def alipay_notify(request: Request, db=Depends(get_db_session)) -> PlainTextResponse:
    form = await request.form()
    data = {key: str(value) for key, value in form.items()}
    client = get_alipay_client()
    if not client.verify_notify(data):
        return PlainTextResponse("fail", status_code=status.HTTP_400_BAD_REQUEST)
    handled = await payment_service.handle_alipay_callback(db, client, data)
    if not handled:
        import logging as _logging
        _logging.getLogger(__name__).error(
            "支付宝回调业务处理失败（订单不存在/金额不匹配）data=%s", data
        )
    return PlainTextResponse("success")


async def _user_is_pro(db, user_id: uuid.UUID) -> bool:
    result = await db.execute(
        select(Membership).where(
            Membership.user_id == user_id,
            Membership.product == "zhaodan",
            Membership.plan == "pro",
            Membership.status == "active",
        )
    )
    return result.scalar_one_or_none() is not None
