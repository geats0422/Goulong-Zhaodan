from __future__ import annotations

import datetime
import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, field_validator, model_validator
from sqlalchemy import select

from app.core.auth import (
    create_access_token,
    create_refresh_token,
    decode_token,
    CurrentUserContext,
    get_current_user,
    hash_password,
    is_refresh_token_revoked,
    store_refresh_token,
    verify_password,
)
from app.core.config import settings
from app.core.database import get_db_session
from app.core.deps import get_client_ip
from app.core.login_throttle import login_throttle
from app.core.password_rules import validate_password
from app.core.pii_masking import mask_email, mask_phone
from app.core.rate_limit import register_limiter, send_code_limiter
from app.core.turnstile import TurnstileError, verify_token
from goulong_auth.models import Membership, User
from app.models.knowledge import ZhaodanUserProfile
from app.services import email_service, sms_service

router = APIRouter(prefix="/auth", tags=["认证"])

_logger = logging.getLogger(__name__)

_REFRESH_COOKIE_NAME = "refresh_token"
_REFRESH_COOKIE_MAX_AGE = 7 * 24 * 3600


class RegisterRequest(BaseModel):
    email: str | None = None
    phone: str | None = None
    phone_code: str | None = None
    email_code: str | None = None
    turnstile_token: str = ""
    nickname: str
    password: str

    @model_validator(mode="after")
    def check_identity_and_code(self):
        if not self.email and not self.phone:
            raise ValueError("必须提供 email 或 phone（至少一项）")
        if self.phone and not self.phone_code:
            raise ValueError("手机号注册必须提供 phone_code")
        if self.email and not self.email_code:
            raise ValueError("邮箱注册必须提供 email_code")
        return self

    @field_validator("password")
    @classmethod
    def validate_password_strength(cls, v: str) -> str:
        errors = validate_password(v)
        if errors:
            raise ValueError("; ".join(errors))
        return v


class SendSmsCodeRequest(BaseModel):
    phone: str
    scene: str = "login"
    turnstile_token: str = ""


class SendEmailCodeRequest(BaseModel):
    email: str
    turnstile_token: str = ""


class CodeLoginRequest(BaseModel):
    phone: str | None = None
    email: str | None = None
    code: str

    @model_validator(mode="after")
    def check_identity(self):
        if not self.email and not self.phone:
            raise ValueError("必须提供 email 或 phone")
        return self


class LoginRequest(BaseModel):
    email: str | None = None
    phone: str | None = None
    password: str

    @model_validator(mode="after")
    def check_identity(self):
        if not self.email and not self.phone:
            raise ValueError("必须提供 email 或 phone")
        return self

    @field_validator("password")
    @classmethod
    def validate_password_length(cls, v: str) -> str:
        if len(v) > 128:
            raise ValueError("密码长度不能超过 128 位")
        return v


def _set_refresh_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        _REFRESH_COOKIE_NAME,
        token,
        httponly=True,
        secure=settings.environment == "production",
        max_age=_REFRESH_COOKIE_MAX_AGE,
        samesite="lax",
    )


@router.post("/send-sms-code")
async def send_sms_code(body: SendSmsCodeRequest, request: Request):
    """发送短信验证码。"""
    ip = get_client_ip(request)
    try:
        await verify_token(body.turnstile_token, ip)
    except TurnstileError as e:
        raise HTTPException(status_code=403, detail=str(e)) from None
    if send_code_limiter.is_limited(ip):
        raise HTTPException(status_code=429, detail="请求过于频繁，请稍后再试")
    send_code_limiter.record(ip)
    try:
        _, expires_in = await sms_service.send_code(body.phone, ip=ip, scene=body.scene)
    except sms_service.SmsInvalidPhoneError:
        raise HTTPException(status_code=400, detail="手机号格式错误") from None
    except sms_service.SmsRateLimitError:
        raise HTTPException(status_code=429, detail="请求过于频繁，请稍后再试") from None
    except sms_service.SmsSendError as e:
        raise HTTPException(status_code=502, detail=str(e)) from None
    return {"sent": True, "expires_in": expires_in}


@router.post("/send-email-code")
async def send_email_code(body: SendEmailCodeRequest, request: Request):
    """发送邮箱验证码。"""
    ip = get_client_ip(request)
    try:
        await verify_token(body.turnstile_token, ip)
    except TurnstileError as e:
        raise HTTPException(status_code=403, detail=str(e)) from None
    if send_code_limiter.is_limited(ip):
        raise HTTPException(status_code=429, detail="请求过于频繁，请稍后再试")
    send_code_limiter.record(ip)
    try:
        _, expires_in = await email_service.send_verification_code(body.email, ip=ip)
    except email_service.EmailInvalidAddressError:
        raise HTTPException(status_code=400, detail="邮箱格式错误") from None
    except email_service.EmailRateLimitError:
        raise HTTPException(status_code=429, detail="请求过于频繁，请稍后再试") from None
    except email_service.EmailSendError as e:
        raise HTTPException(status_code=502, detail=str(e)) from None
    return {"sent": True, "expires_in": expires_in}


@router.post("/register", status_code=201)
async def register(body: RegisterRequest, response: Response, request: Request, db=Depends(get_db_session)):
    ip = get_client_ip(request)
    try:
        await verify_token(body.turnstile_token, ip)
    except TurnstileError as e:
        raise HTTPException(status_code=403, detail=str(e)) from None
    if register_limiter.is_limited(ip):
        raise HTTPException(status_code=429, detail="请求过于频繁，请稍后再试")
    register_limiter.record(ip)

    # 校验验证码（手机→短信，邮箱→邮件）
    if body.phone and not await sms_service.verify_code(body.phone, body.phone_code or ""):
        raise HTTPException(status_code=401, detail="手机验证码错误或已过期")
    if body.email and not await email_service.verify_code(body.email, body.email_code or ""):
        raise HTTPException(status_code=401, detail="邮箱验证码错误或已过期")

    # 按 email 或 phone 查重
    if body.email:
        result = await db.execute(select(User).where(User.email == body.email))
        if result.scalar_one_or_none() is not None:
            raise HTTPException(status_code=400, detail="注册信息无效或已存在")
    if body.phone:
        result = await db.execute(select(User).where(User.phone == body.phone))
        if result.scalar_one_or_none() is not None:
            raise HTTPException(status_code=400, detail="注册信息无效或已存在")

    user = User(
        nickname=body.nickname,
        hashed_password=hash_password(body.password),
        email=body.email,
        phone=body.phone,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    # 创建默认 ZhaodanUserProfile
    profile = ZhaodanUserProfile(
        user_id=user.id,
        burn_after_read=True,
    )
    db.add(profile)

    # 创建默认 Membership（zhaodan 产品）
    membership = Membership(
        user_id=user.id,
        product="zhaodan",
        plan="free",
        status="active",
        token_quota=50,
        token_used=0,
    )
    db.add(membership)
    await db.commit()

    access_token = create_access_token(user.id)
    refresh_token, jti = create_refresh_token(user.id)
    expires_at = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None) + datetime.timedelta(
        days=settings.refresh_token_expire_days,
    )
    await store_refresh_token(db, user.id, jti, expires_at)
    _set_refresh_cookie(response, refresh_token)

    _logger.info("用户注册: user_id=%s ip=%s", user.id, ip)

    return {
        "id": user.id,
        "nickname": user.nickname,
        "email": mask_email(user.email),
        "phone": mask_phone(user.phone),
        "access_token": access_token,
    }


@router.post("/login")
async def login(body: LoginRequest, response: Response, request: Request, db=Depends(get_db_session)):
    ip = get_client_ip(request)
    throttle_key = body.email or body.phone
    wait = login_throttle.check(throttle_key)
    if wait > 0:
        raise HTTPException(
            status_code=429,
            detail=f"登录尝试过于频繁，请 {wait} 秒后再试",
            headers={"Retry-After": str(wait)},
        )

    if body.email:
        result = await db.execute(select(User).where(User.email == body.email))
    else:
        result = await db.execute(select(User).where(User.phone == body.phone))
    user = result.scalar_one_or_none()

    if user is None or not verify_password(body.password, user.hashed_password):
        login_throttle.record_failure(throttle_key)
        _logger.warning("登录失败: key=%s ip=%s", throttle_key, ip)
        raise HTTPException(status_code=401, detail="邮箱/手机号或密码错误")

    if not user.is_active:
        raise HTTPException(status_code=403, detail="账号已被停用")

    login_throttle.reset(throttle_key)

    access_token = create_access_token(user.id)
    refresh_token, jti = create_refresh_token(user.id)
    expires_at = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None) + datetime.timedelta(
        days=settings.refresh_token_expire_days,
    )
    await store_refresh_token(db, user.id, jti, expires_at)
    _set_refresh_cookie(response, refresh_token)

    _logger.info("用户登录: user_id=%s ip=%s", user.id, ip)

    return {
        "id": user.id,
        "nickname": user.nickname,
        "email": mask_email(user.email),
        "phone": mask_phone(user.phone),
        "access_token": access_token,
    }


@router.post("/login/code")
async def login_by_code(
    body: CodeLoginRequest, response: Response, request: Request, db=Depends(get_db_session)
):
    """验证码登录（手机短信码或邮箱验证码，免密码）。"""
    ip = get_client_ip(request)

    if body.phone:
        if not await sms_service.verify_code(body.phone, body.code):
            raise HTTPException(status_code=401, detail="验证码错误或已过期")
        result = await db.execute(select(User).where(User.phone == body.phone))
    else:
        email = body.email or ""
        if not await email_service.verify_code(email, body.code):
            raise HTTPException(status_code=401, detail="验证码错误或已过期")
        result = await db.execute(select(User).where(User.email == email))

    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=401, detail="账号不存在，请先注册")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="账号已被停用")

    access_token = create_access_token(user.id)
    refresh_token, jti = create_refresh_token(user.id)
    expires_at = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None) + datetime.timedelta(
        days=settings.refresh_token_expire_days,
    )
    await store_refresh_token(db, user.id, jti, expires_at)
    _set_refresh_cookie(response, refresh_token)

    _logger.info("验证码登录: user_id=%s ip=%s", user.id, ip)

    return {
        "id": user.id,
        "nickname": user.nickname,
        "email": mask_email(user.email),
        "phone": mask_phone(user.phone),
        "access_token": access_token,
    }


@router.post("/refresh")
async def refresh(request: Request, db=Depends(get_db_session)):
    token = request.cookies.get(_REFRESH_COOKIE_NAME)
    if not token:
        raise HTTPException(status_code=401, detail="Missing refresh token")

    payload = decode_token(token, "refresh")
    jti = payload.get("jti")
    if jti and await is_refresh_token_revoked(db, jti):
        raise HTTPException(status_code=401, detail="Refresh token has been revoked")

    access_token = create_access_token(uuid.UUID(payload["user_id"]))
    return {"access_token": access_token}


@router.get("/me")
async def me(user: CurrentUserContext = Depends(get_current_user), db=Depends(get_db_session)):
    from sqlalchemy import select as sa_select

    result = await db.execute(sa_select(User).where(User.id == user.user_id))
    db_user = result.scalar_one_or_none()
    if db_user is None:
        raise HTTPException(status_code=401, detail="User not found")

    return {
        "id": db_user.id,
        "nickname": db_user.nickname,
        "email": mask_email(db_user.email),
        "phone": mask_phone(db_user.phone),
        "is_active": db_user.is_active,
    }
