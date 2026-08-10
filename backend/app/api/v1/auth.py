from __future__ import annotations

import datetime
import logging
import uuid
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from goulong_auth.models import Membership, User
from pydantic import BaseModel, Field, field_validator, model_validator
from sqlalchemy import select

from app.core.auth import (
    CurrentUserContext,
    create_access_token,
    create_refresh_token,
    decode_token,
    get_current_user,
    hash_password,
    is_refresh_token_revoked,
    revoke_all_refresh_tokens,
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
from app.models.knowledge import ZhaodanUserProfile
from app.services import email_service, sms_service

router = APIRouter(prefix="/auth", tags=["认证"])

_logger = logging.getLogger(__name__)

_REFRESH_COOKIE_NAME = "refresh_token"
_REFRESH_COOKIE_MAX_AGE = 7 * 24 * 3600


class RegisterRequest(BaseModel):
    email: str | None = None
    phone: str | None = None
    phone_code: str | None = Field(default=None, pattern=r"^[0-9]{6}$")
    email_code: str | None = Field(default=None, pattern=r"^[0-9]{6}$")
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
    scene: Literal["login", "register", "forgot_password"] = "login"


class SendEmailCodeRequest(BaseModel):
    email: str


class CodeLoginRequest(BaseModel):
    phone: str | None = None
    email: str | None = None
    code: str = Field(pattern=r"^[0-9]{6}$")

    @model_validator(mode="after")
    def check_identity(self):
        if sum(bool(identity) for identity in (self.email, self.phone)) != 1:
            raise ValueError("必须提供 email 或 phone 且只能提供一项")
        return self


class LoginRequest(BaseModel):
    email: str | None = None
    phone: str | None = None
    username: str | None = Field(
        default=None,
        min_length=3,
        max_length=50,
        pattern=r"^[a-z][a-z0-9_]{2,49}$",
    )
    password: str = Field(min_length=1, max_length=128)

    @field_validator("username", mode="before")
    @classmethod
    def trim_username(cls, v: object) -> object:
        return v.strip().lower() if isinstance(v, str) else v

    @model_validator(mode="after")
    def check_identity(self):
        if sum(bool(identity) for identity in (self.email, self.phone, self.username)) != 1:
            raise ValueError("必须提供 email、phone 或 username 且只能提供一项")
        return self

class ResetPasswordRequest(BaseModel):
    phone: str
    code: str = Field(pattern=r"^[0-9]{6}$")
    new_password: str

    @field_validator("new_password")
    @classmethod
    def validate_password_strength(cls, v: str) -> str:
        errors = validate_password(v)
        if errors:
            raise ValueError("; ".join(errors))
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


async def _verify_sms_code(phone: str, code: str) -> bool:
    try:
        return await sms_service.verify_code(phone, code)
    except sms_service.SmsVerificationInfrastructureError:
        raise HTTPException(status_code=503, detail=sms_service.SMS_SERVICE_UNAVAILABLE_MESSAGE) from None


@router.post("/send-sms-code")
async def send_sms_code(body: SendSmsCodeRequest, request: Request):
    """发送短信验证码。"""
    ip = get_client_ip(request)
    if send_code_limiter.is_limited(ip):
        raise HTTPException(status_code=429, detail="请求过于频繁，请稍后再试")
    send_code_limiter.record(ip)
    try:
        _, expires_in = await sms_service.send_code(body.phone, ip=ip, scene=body.scene)
    except sms_service.SmsInvalidPhoneError:
        raise HTTPException(status_code=400, detail="手机号格式错误") from None
    except sms_service.SmsRateLimitError:
        raise HTTPException(status_code=429, detail="请求过于频繁，请稍后再试") from None
    except sms_service.SmsSendError:
        raise HTTPException(status_code=502, detail=sms_service.SMS_SERVICE_UNAVAILABLE_MESSAGE) from None
    except Exception as exc:
        _logger.error(
            "短信验证码基础设施异常: phone=%s ip=%s error_type=%s",
            mask_phone(body.phone),
            ip,
            type(exc).__name__,
        )
        raise HTTPException(status_code=502, detail=sms_service.SMS_SERVICE_UNAVAILABLE_MESSAGE) from None
    return {"sent": True, "expires_in": expires_in}


@router.post("/send-email-code")
async def send_email_code(body: SendEmailCodeRequest, request: Request):
    """发送邮箱验证码。"""
    ip = get_client_ip(request)
    if send_code_limiter.is_limited(ip):
        raise HTTPException(status_code=429, detail="请求过于频繁，请稍后再试")
    send_code_limiter.record(ip)
    try:
        _, expires_in = await email_service.send_verification_code(body.email, ip=ip)
    except email_service.EmailInvalidAddressError:
        raise HTTPException(status_code=400, detail="邮箱格式错误") from None
    except email_service.EmailRateLimitError:
        raise HTTPException(status_code=429, detail="请求过于频繁，请稍后再试") from None
    except email_service.EmailSendError:
        _logger.warning("邮箱验证码发送失败: email=%s ip=%s", mask_email(body.email), ip)
        raise HTTPException(status_code=502, detail=email_service.EMAIL_SERVICE_UNAVAILABLE_MESSAGE) from None
    except Exception as exc:
        _logger.error(
            "邮箱验证码基础设施异常: email=%s ip=%s error_type=%s",
            mask_email(body.email),
            ip,
            type(exc).__name__,
        )
        raise HTTPException(status_code=502, detail=email_service.EMAIL_SERVICE_UNAVAILABLE_MESSAGE) from None
    return {"sent": True, "expires_in": expires_in}


@router.post("/register", status_code=201)
async def register(body: RegisterRequest, response: Response, request: Request, db=Depends(get_db_session)):
    ip = get_client_ip(request)
    if register_limiter.is_limited(ip):
        raise HTTPException(status_code=429, detail="请求过于频繁，请稍后再试")
    register_limiter.record(ip)

    # 校验验证码（手机→短信，邮箱→邮件）
    if body.phone and not await _verify_sms_code(body.phone, body.phone_code or ""):
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
        token_quota=0,
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
    if body.email:
        throttle_key = body.email
    elif body.phone:
        throttle_key = body.phone
    else:
        throttle_key = (body.username or "").strip().lower()
    wait = login_throttle.check(throttle_key)
    if wait > 0:
        raise HTTPException(
            status_code=429,
            detail=f"登录尝试过于频繁，请 {wait} 秒后再试",
            headers={"Retry-After": str(wait)},
        )

    if body.email:
        result = await db.execute(select(User).where(User.email == body.email))
    elif body.phone:
        result = await db.execute(select(User).where(User.phone == body.phone))
    else:
        result = await db.execute(select(User).where(User.username == throttle_key))
    user = result.scalar_one_or_none()

    try:
        password_valid = user is not None and verify_password(body.password, user.hashed_password)
    except ValueError:
        password_valid = False

    if not password_valid:
        login_throttle.record_failure(throttle_key)
        _logger.warning("登录失败: key=%s ip=%s", throttle_key, ip)
        raise HTTPException(status_code=401, detail="用户名/邮箱/手机号或密码错误")

    if not user.is_active:
        raise HTTPException(status_code=403, detail="账号已被停用")

    user.updated_at = datetime.datetime.now(datetime.UTC)
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
        "require_phone_binding": user.phone is None,
        "access_token": access_token,
    }


@router.post("/login/code")
async def login_by_code(
    body: CodeLoginRequest, response: Response, request: Request, db=Depends(get_db_session)
):
    """验证码登录（手机短信码或邮箱验证码，免密码）。"""
    ip = get_client_ip(request)

    if body.phone:
        if not await _verify_sms_code(body.phone, body.code):
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

    user.updated_at = datetime.datetime.now(datetime.UTC)
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
        "require_phone_binding": user.phone is None,
        "access_token": access_token,
    }


@router.post("/reset-password")
async def reset_password(body: ResetPasswordRequest, request: Request, db=Depends(get_db_session)):
    """忘记密码重置（手机号 + 短信验证码 + 新密码）。

    前端先调用 /auth/send-sms-code（scene=forgot_password）获取验证码，
    再调用本端点完成重置。验证码校验通过后更新密码哈希。
    """
    ip = get_client_ip(request)
    if not await _verify_sms_code(body.phone, body.code):
        raise HTTPException(status_code=401, detail="验证码错误或已过期")

    result = await db.execute(select(User).where(User.phone == body.phone))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail="该手机号未注册")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="账号已被停用")

    user.hashed_password = hash_password(body.new_password)
    user.password_changed_at = datetime.datetime.now(datetime.UTC)
    await revoke_all_refresh_tokens(db, user.id)
    await db.commit()
    _logger.info("密码重置成功: user_id=%s ip=%s", user.id, ip)
    return {"message": "密码重置成功"}


@router.post("/refresh")
async def refresh(request: Request, db=Depends(get_db_session)):
    token = request.cookies.get(_REFRESH_COOKIE_NAME)
    if not token:
        raise HTTPException(status_code=401, detail="Missing refresh token")

    payload = decode_token(token, "refresh")
    jti = payload.get("jti")
    if jti and await is_refresh_token_revoked(db, jti):
        raise HTTPException(status_code=401, detail="Refresh token has been revoked")

    user_id = uuid.UUID(payload["user_id"])
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=401, detail="User not found")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="账号已被停用")

    access_token = create_access_token(user_id)
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
