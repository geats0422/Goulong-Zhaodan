from __future__ import annotations

import datetime
import uuid

import jwt
from fastapi import HTTPException, Request
from sqlalchemy import select, update
import bcrypt as _bcrypt

from app.core.config import settings


def hash_password(password: str) -> str:
    return _bcrypt.hashpw(password.encode("utf-8"), _bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    return _bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))


def create_access_token(user_id: uuid.UUID) -> str:
    expire = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(
        minutes=settings.access_token_expire_minutes,
    )
    payload = {"sub": str(user_id), "type": "access", "exp": expire}
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def create_refresh_token(user_id: uuid.UUID) -> tuple[str, str]:
    jti = uuid.uuid4().hex
    expire = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(
        days=settings.refresh_token_expire_days,
    )
    payload = {
        "sub": str(user_id),
        "type": "refresh",
        "jti": jti,
        "exp": expire,
    }
    token = jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
    return token, jti


def decode_token(token: str, token_type: str) -> dict:
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

    if payload.get("type") != token_type:
        raise HTTPException(status_code=401, detail="Invalid token type")

    return payload


async def store_refresh_token(db, user_id: uuid.UUID, jti: str, expires_at: datetime.datetime) -> None:
    from app.models.knowledge import RefreshToken

    db.add(RefreshToken(user_id=user_id, token_jti=jti, expires_at=expires_at, revoked=False))
    await db.commit()


async def is_refresh_token_revoked(db, jti: str) -> bool:
    from app.models.knowledge import RefreshToken

    result = await db.execute(select(RefreshToken).where(RefreshToken.token_jti == jti))
    token_record = result.scalar_one_or_none()
    if token_record is None:
        return True
    return token_record.revoked


async def revoke_all_refresh_tokens(db, user_id: uuid.UUID) -> None:
    from app.models.knowledge import RefreshToken

    await db.execute(
        update(RefreshToken).where(RefreshToken.user_id == user_id, ~RefreshToken.revoked).values(revoked=True)
    )
    await db.commit()


async def get_current_user(request: Request) -> dict:
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")

    token = auth_header[7:]
    payload = decode_token(token, "access")

    return {
        "user_id": payload["sub"],
        "is_active": payload.get("is_active", True),
    }
