from __future__ import annotations

import datetime
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, field_validator, model_validator
from sqlalchemy import select

from core.auth import (
    create_access_token,
    create_refresh_token,
    decode_token,
    get_current_user,
    hash_password,
    is_refresh_token_revoked,
    store_refresh_token,
    verify_password,
)
from core.config import settings
from core.database import get_db_session
from core.login_throttle import login_throttle
from core.password_rules import validate_password
from core.rate_limit import register_limiter
from models.knowledge import User, UserProfile

router = APIRouter(prefix="/auth", tags=["认证"])

_REFRESH_COOKIE_NAME = "refresh_token"
_REFRESH_COOKIE_MAX_AGE = 7 * 24 * 3600


class RegisterRequest(BaseModel):
    email: str | None = None
    phone: str | None = None
    nickname: str
    password: str

    @model_validator(mode="after")
    def check_identity(self):
        if not self.email and not self.phone:
            raise ValueError("必须提供 email 或 phone（至少一项）")
        return self

    @field_validator("password")
    @classmethod
    def validate_password_strength(cls, v: str) -> str:
        errors = validate_password(v)
        if errors:
            raise ValueError("; ".join(errors))
        return v


class LoginRequest(BaseModel):
    email: str | None = None
    phone: str | None = None
    password: str

    @model_validator(mode="after")
    def check_identity(self):
        if not self.email and not self.phone:
            raise ValueError("必须提供 email 或 phone")
        return self


def _set_refresh_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        _REFRESH_COOKIE_NAME,
        token,
        httponly=True,
        secure=settings.environment == "production",
        max_age=_REFRESH_COOKIE_MAX_AGE,
        samesite="lax",
    )


@router.post("/register", status_code=201)
async def register(body: RegisterRequest, response: Response, request: Request, db=Depends(get_db_session)):
    ip = (request.headers.get("x-forwarded-for", "").split(",")[0].strip()
           or (request.client.host if request.client else "unknown"))
    if register_limiter.is_limited(ip):
        raise HTTPException(status_code=429, detail="请求过于频繁，请稍后再试")
    register_limiter.record(ip)

    # 按 email 或 phone 查重
    if body.email:
        result = await db.execute(select(User).where(User.email == body.email))
        if result.scalar_one_or_none() is not None:
            raise HTTPException(status_code=400, detail="该邮箱已被注册")
    if body.phone:
        result = await db.execute(select(User).where(User.phone == body.phone))
        if result.scalar_one_or_none() is not None:
            raise HTTPException(status_code=400, detail="该手机号已被注册")

    user = User(
        nickname=body.nickname,
        hashed_password=hash_password(body.password),
        email=body.email,
        phone=body.phone,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    # 创建默认 UserProfile
    profile = UserProfile(
        user_id=user.id,
        subscription_plan="free",
        monthly_quota=50,
        quota_used=0,
        burn_after_read=True,
    )
    db.add(profile)
    await db.commit()

    access_token = create_access_token(user.id)
    refresh_token, jti = create_refresh_token(user.id)
    expires_at = datetime.datetime.utcnow() + datetime.timedelta(
        days=settings.refresh_token_expire_days,
    )
    await store_refresh_token(db, user.id, jti, expires_at)
    _set_refresh_cookie(response, refresh_token)

    return {
        "id": user.id,
        "nickname": user.nickname,
        "email": user.email,
        "phone": user.phone,
        "access_token": access_token,
    }


@router.post("/login")
async def login(body: LoginRequest, response: Response, db=Depends(get_db_session)):
    throttle_key = body.email or body.phone
    wait = login_throttle.check(throttle_key)
    if wait > 0:
        raise HTTPException(
            status_code=429,
            detail=f"登录尝试过于频繁，请 {wait} 秒后再试",
            headers={"Retry-After": str(wait)},
        )

    # 按 email 或 phone 查找用户
    if body.email:
        result = await db.execute(select(User).where(User.email == body.email))
    else:
        result = await db.execute(select(User).where(User.phone == body.phone))
    user = result.scalar_one_or_none()

    if user is None or not verify_password(body.password, user.hashed_password):
        login_throttle.record_failure(throttle_key)
        raise HTTPException(status_code=401, detail="邮箱/手机号或密码错误")

    if not user.is_active:
        raise HTTPException(status_code=403, detail="账号已被停用")

    login_throttle.reset(throttle_key)

    access_token = create_access_token(user.id)
    refresh_token, jti = create_refresh_token(user.id)
    expires_at = datetime.datetime.utcnow() + datetime.timedelta(
        days=settings.refresh_token_expire_days,
    )
    await store_refresh_token(db, user.id, jti, expires_at)
    _set_refresh_cookie(response, refresh_token)

    return {
        "id": user.id,
        "nickname": user.nickname,
        "email": user.email,
        "phone": user.phone,
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

    access_token = create_access_token(uuid.UUID(payload["sub"]))
    return {"access_token": access_token}


@router.get("/me")
async def me(user: dict = Depends(get_current_user), db=Depends(get_db_session)):
    from sqlalchemy import select as sa_select

    result = await db.execute(sa_select(User).where(User.id == uuid.UUID(user["user_id"])))
    db_user = result.scalar_one_or_none()
    if db_user is None:
        raise HTTPException(status_code=401, detail="User not found")

    return {
        "id": db_user.id,
        "nickname": db_user.nickname,
        "email": db_user.email,
        "phone": db_user.phone,
        "is_active": db_user.is_active,
    }
