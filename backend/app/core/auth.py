from __future__ import annotations

import datetime
import uuid
from dataclasses import dataclass
from datetime import UTC, timedelta
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, Request
from sqlalchemy import select, update

from app.core.database import get_db_session
from app.core.password_rules import BCRYPT_MAX_PASSWORD_BYTES
from goulong_auth.config import auth_settings


def hash_password(password: str) -> str:
    if len(password.encode("utf-8")) > BCRYPT_MAX_PASSWORD_BYTES:
        raise ValueError(f"password cannot be longer than {BCRYPT_MAX_PASSWORD_BYTES} bytes")
    from goulong_auth.auth.password import hash_password as _hash
    return _hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    if len(plain.encode("utf-8")) > BCRYPT_MAX_PASSWORD_BYTES:
        return False
    from goulong_auth.auth.password import verify_password as _verify
    try:
        return _verify(plain, hashed)
    except (TypeError, ValueError):
        return False


def create_access_token(user_id: uuid.UUID) -> str:
    now = datetime.datetime.now(UTC)
    issued_at_ms = int(now.timestamp() * 1000)
    return jwt.encode(
        {
            "user_id": str(user_id),
            "product": "zhaodan",
            "typ": "access",
            "exp": now + timedelta(minutes=auth_settings.ACCESS_TOKEN_EXPIRE_MINUTES),
            "iat": issued_at_ms // 1000,
            "iat_ms": issued_at_ms,
        },
        auth_settings.JWT_SECRET_KEY,
        algorithm=auth_settings.JWT_ALGORITHM,
    )


def create_refresh_token(user_id: uuid.UUID) -> tuple[str, str]:
    now = datetime.datetime.now(UTC)
    jti = uuid.uuid4().hex
    token = jwt.encode(
        {
            "user_id": str(user_id),
            "product": "zhaodan",
            "typ": "refresh",
            "jti": jti,
            "exp": now + timedelta(days=auth_settings.REFRESH_TOKEN_EXPIRE_DAYS),
            "iat": now,
        },
        auth_settings.JWT_SECRET_KEY,
        algorithm=auth_settings.JWT_ALGORITHM,
    )
    return token, jti


def decode_token(token: str, token_type: str) -> dict:
    try:
        if token_type not in {"access", "refresh"}:
            raise ValueError("unsupported token type")
        payload = jwt.decode(
            token,
            auth_settings.JWT_SECRET_KEY,
            algorithms=[auth_settings.JWT_ALGORITHM],
            options={"require": ["exp", "iat", "user_id", "product"]},
        )
        user_id = uuid.UUID(str(payload["user_id"]))
        if payload.get("product") != "zhaodan":
            raise ValueError("wrong product")

        encoded_type = payload.get("typ")
        if encoded_type is None:
            encoded_type = "refresh" if payload.get("jti") else "access"
        if encoded_type != token_type:
            raise ValueError("wrong token type")
        if token_type == "refresh" and not payload.get("jti"):
            raise ValueError("missing refresh token id")
    except Exception as exc:
        raise HTTPException(status_code=401, detail="Invalid token") from exc
    return {
        "user_id": str(user_id),
        "product": payload["product"],
        "typ": encoded_type,
        "exp": payload["exp"],
        "iat": payload["iat"],
        "iat_ms": payload.get("iat_ms"),
        "jti": payload.get("jti"),
        "sub": str(user_id),
    }


async def store_refresh_token(db, user_id: uuid.UUID, jti: str, expires_at: datetime.datetime) -> None:
    from goulong_auth.models import RefreshToken

    db.add(RefreshToken(user_id=user_id, token_jti=jti, expires_at=expires_at, revoked=False))
    await db.commit()


async def is_refresh_token_revoked(db, jti: str) -> bool:
    from goulong_auth.models import RefreshToken

    result = await db.execute(select(RefreshToken).where(RefreshToken.token_jti == jti))
    token_record = result.scalar_one_or_none()
    if token_record is None:
        return True
    return token_record.revoked


async def revoke_all_refresh_tokens(db, user_id: uuid.UUID) -> None:
    """在当前事务中吊销用户的全部 refresh token，由调用方统一提交。"""
    from goulong_auth.models import RefreshToken

    await db.execute(
        update(RefreshToken).where(RefreshToken.user_id == user_id, ~RefreshToken.revoked).values(revoked=True)
    )


@dataclass
class CurrentUserContext:
    """当前登录用户上下文（从 JWT 解析，不含 DB 查询，保持高性能）。"""

    user_id: uuid.UUID
    is_active: bool = True


async def get_current_user(request: Request, db=Depends(get_db_session)) -> CurrentUserContext:
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")

    token = auth_header[7:]
    payload = decode_token(token, "access")

    from goulong_auth.models import User

    result = await db.execute(select(User).where(User.id == uuid.UUID(payload["user_id"])))
    user = result.scalar_one_or_none()
    if user is None or not user.is_active:
        raise HTTPException(status_code=401, detail="Not authenticated")

    password_changed_at = getattr(user, "password_changed_at", None)
    if password_changed_at is not None:
        if password_changed_at.tzinfo is None:
            password_changed_at = password_changed_at.replace(tzinfo=UTC)
        token_issued_at_ms = payload.get("iat_ms")
        if token_issued_at_ms is None:
            token_issued_at_ms = float(payload["iat"]) * 1000
        password_changed_at_ms = password_changed_at.timestamp() * 1000
        if token_issued_at_ms < password_changed_at_ms:
            raise HTTPException(status_code=401, detail="Not authenticated")

    return CurrentUserContext(
        user_id=user.id,
        is_active=user.is_active,
    )


CurrentUser = Annotated[CurrentUserContext, Depends(get_current_user)]
