"""微信统一回调端点。

合并 V3 Native 支付成功 + V2 PAPay 签约/扣款回调。
根据 Content-Type 分发：JSON → V3 Native，XML → V2 PAPay。

商户平台只支持配一个回调 URL，因此所有微信回调走此端点。
"""
from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import JSONResponse, PlainTextResponse

from app.core.config import settings
from app.core.deps import DbSession
from app.services import payment_service, subscription_service
from app.services.wechatpay_client import get_wechatpay_client
from app.services.wechatpay_v2_client import WechatPayV2Client, get_wechatpay_v2_client

router = APIRouter(prefix="/payments", tags=["wechat-callback"])


_V2_SUCCESS_XML = (
    '<xml><return_code><![CDATA[SUCCESS]]></return_code>'
    '<return_msg><![CDATA[OK]]></return_msg></xml>'
)


@router.post("/wechat-callback")
async def wechat_unified_callback(request: Request, db: DbSession):
    """统一微信回调：Content-Type 分发到 V3 Native / V2 PAPay。"""
    content_type = (request.headers.get("content-type") or "").lower()
    body = await request.body()

    if "json" in content_type:
        return await _handle_v3_native(request, body, db)
    if "xml" in content_type:
        return await _handle_v2_papay(body, db)
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=f"不支持的 Content-Type: {content_type}",
    )


async def _handle_v3_native(request: Request, body: bytes, db):
    """V3 Native 支付成功回调：RSA 验签 + AES-GCM 解密 + 开通额度。"""
    body_text = body.decode()
    timestamp = request.headers.get("Wechatpay-Timestamp", "")
    nonce = request.headers.get("Wechatpay-Nonce", "")
    signature = request.headers.get("Wechatpay-Signature", "")
    serial = request.headers.get("Wechatpay-Serial", "")

    client = get_wechatpay_client()
    await client.ensure_platform_cert(serial)
    if not client.verify_callback(
        timestamp=timestamp, nonce=nonce, body=body_text, signature_b64=signature, serial=serial,
    ):
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"code": "FAIL", "message": "验签失败"},
        )

    try:
        notification = json.loads(body_text)
        decrypted = client.decrypt_callback(notification.get("resource", {}))
    except Exception:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"code": "FAIL", "message": "解密失败"},
        )

    await payment_service.handle_callback(db=db, client=client, decrypted=decrypted)
    return JSONResponse(status_code=status.HTTP_200_OK, content={})


async def _handle_v2_papay(body: bytes, db):
    """V2 PAPay 签约/扣款回调：MD5 验签 + 业务分发。"""
    payload = get_wechatpay_v2_client().parse_callback_xml(body.decode())
    if not WechatPayV2Client.verify_callback_sign(payload, settings.wechatpay_api_v2_key):
        return PlainTextResponse(
            content=(
                '<xml><return_code><![CDATA[FAIL]]></return_code>'
                '<return_msg><![CDATA[签名错误]]></return_msg></xml>'
            ),
            media_type="application/xml",
        )
    if "change_type" in payload:
        await subscription_service.handle_contract_callback(db=db, payload=payload)
    elif "trade_state" in payload:
        await subscription_service.handle_deduction_callback(db=db, payload=payload)
    return PlainTextResponse(content=_V2_SUCCESS_XML, media_type="application/xml")