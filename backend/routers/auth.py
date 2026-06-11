from __future__ import annotations

import datetime
import re

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, field_validator
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
from models.knowledge import User

router = APIRouter(prefix="/auth", tags=["认证"])

_USERNAME_RE = re.compile(r"^[a-zA-Z0-9_]+$")
_REFRESH_COOKIE_NAME = "refresh_token"
_REFRESH_COOKIE_MAX_AGE = 7 * 24 * 3600


class RegisterRequest(BaseModel):
    username: str
    password: str

    @field_validator("username")
    @classmethod
    def validate_username(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 3 or len(v) > 50:
            raise ValueError("用户名长度须为 3-50 字符")
        if not _USERNAME_RE.match(v):
            raise ValueError("用户名仅支持字母、数字和下划线")
        return v

    @field_validator("password")
    @classmethod
    def validate_password_strength(cls, v: str) -> str:
        errors = validate_password(v)
        if errors:
            raise ValueError("; ".join(errors))
        return v


class LoginRequest(BaseModel):
    username: str
    password: str

    @field_validator("username")
    @classmethod
    def normalize_username(cls, v: str) -> str:
        return v.strip()


def _set_refresh_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        _REFRESH_COOKIE_NAME,
        token,
        httponly=True,
        secure=settings.environment != "development",
        max_age=_REFRESH_COOKIE_MAX_AGE,
        samesite="lax",
    )


_TRUSTED_PROXIES: set[str] = set()


def _extract_client_ip(request: Request) -> str:
    if _TRUSTED_PROXIES:
        forwarded = request.headers.get("x-forwarded-for", "").split(",")[0].strip()
        if forwarded:
            return forwarded
    if request.client:
        return request.client.host
    return "unknown"


@router.post("/register", status_code=201)
async def register(body: RegisterRequest, response: Response, request: Request, db=Depends(get_db_session)):
    ip = _extract_client_ip(request)
    if register_limiter.is_limited(ip):
        raise HTTPException(status_code=429, detail="请求过于频繁，请稍后再试")
    register_limiter.record(ip)

    result = await db.execute(select(User).where(User.username == body.username))
    if result.scalar_one_or_none() is not None:
        raise HTTPException(status_code=400, detail="注册失败")

    user = User(
        username=body.username,
        hashed_password=hash_password(body.password),
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    access_token = create_access_token(user.id)
    refresh_token, jti = create_refresh_token(user.id)
    expires_at = datetime.datetime.now(datetime.UTC) + datetime.timedelta(
        days=settings.refresh_token_expire_days,
    )
    await store_refresh_token(db, user.id, jti, expires_at)
    _set_refresh_cookie(response, refresh_token)

    return {
        "id": user.id,
        "username": user.username,
        "access_token": access_token,
    }


@router.post("/login")
async def login(body: LoginRequest, response: Response, db=Depends(get_db_session)):
    wait = login_throttle.check(body.username)
    if wait > 0:
        raise HTTPException(
            status_code=429,
            detail=f"登录尝试过于频繁，请 {wait} 秒后再试",
            headers={"Retry-After": str(wait)},
        )

    result = await db.execute(select(User).where(User.username == body.username))
    user = result.scalar_one_or_none()

    if user is None or not verify_password(body.password, user.hashed_password):
        login_throttle.record_failure(body.username)
        raise HTTPException(status_code=401, detail="用户名或密码错误")

    if not user.is_active:
        raise HTTPException(status_code=403, detail="账号已被停用")

    login_throttle.reset(body.username)

    access_token = create_access_token(user.id)
    refresh_token, jti = create_refresh_token(user.id)
    expires_at = datetime.datetime.now(datetime.UTC) + datetime.timedelta(
        days=settings.refresh_token_expire_days,
    )
    await store_refresh_token(db, user.id, jti, expires_at)
    _set_refresh_cookie(response, refresh_token)

    return {
        "id": user.id,
        "username": user.username,
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

    access_token = create_access_token(int(payload["sub"]))
    return {"access_token": access_token}


@router.get("/me")
async def me(user: dict = Depends(get_current_user), db=Depends(get_db_session)):
    from sqlalchemy import select as sa_select

    result = await db.execute(sa_select(User).where(User.id == int(user["user_id"])))
    db_user = result.scalar_one_or_none()
    if db_user is None:
        raise HTTPException(status_code=401, detail="User not found")

    return {
        "id": db_user.id,
        "username": db_user.username,
        "is_active": db_user.is_active,
    }
