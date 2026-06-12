from __future__ import annotations

import datetime
import uuid

from fastapi import HTTPException, Request
from sqlalchemy import select, update


def hash_password(password: str) -> str:
    from goulong_auth.auth.password import hash_password as _hash
    return _hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    from goulong_auth.auth.password import verify_password as _verify
    return _verify(plain, hashed)


def create_access_token(user_id: uuid.UUID) -> str:
    from goulong_auth.auth.jwt import create_access_token as _create
    return _create(user_id, product="zhaodan")


def create_refresh_token(user_id: uuid.UUID) -> tuple[str, str]:
    from goulong_auth.auth.jwt import create_refresh_token as _create
    import uuid as _uuid
    token = _create(user_id, product="zhaodan")
    jti = _uuid.uuid4().hex
    return token, jti


def decode_token(token: str, token_type: str) -> dict:
    from goulong_auth.auth.jwt import decode_token as _decode
    try:
        payload = _decode(token)
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")
    return {
        "user_id": str(payload.user_id),
        "product": payload.product,
        "exp": payload.exp,
        "iat": payload.iat,
        "sub": str(payload.user_id),
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
    from goulong_auth.models import RefreshToken

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
        "user_id": payload["user_id"],
        "is_active": payload.get("is_active", True),
    }
