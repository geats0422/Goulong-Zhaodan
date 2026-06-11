from __future__ import annotations

import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.api_key_crypto import (
    decrypt_api_key,
    encrypt_api_key,
    generate_api_key,
    get_key_prefix,
    hash_api_key,
    verify_api_key_hash,
)
from core.api_key_scopes import resolve_scopes
from models.api_keys import ApiKey


async def create_api_key(
    db: AsyncSession,
    user_id: int,
    name: str,
    client_type: str,
    scope_template: str,
    user_scopes: list[str] | None = None,
    expires_at: datetime.datetime | None = None,
) -> dict:
    scopes = resolve_scopes(scope_template, user_scopes)
    full_key = generate_api_key()
    key_hash = hash_api_key(full_key)
    encrypted = encrypt_api_key(full_key)
    prefix = get_key_prefix(full_key)

    api_key = ApiKey(
        user_id=user_id,
        name=name,
        client_type=client_type,
        scope_template=scope_template,
        scopes=scopes,
        key_prefix=prefix,
        key_hash=key_hash,
        encrypted_key=encrypted,
        expires_at=expires_at,
    )
    db.add(api_key)
    await db.commit()
    await db.refresh(api_key)
    return {"api_key": api_key, "full_key": full_key}


async def list_api_keys(db: AsyncSession, user_id: int) -> list[ApiKey]:
    stmt = (
        select(ApiKey)
        .where(ApiKey.user_id == user_id)
        .order_by(ApiKey.created_at.desc())
    )
    result = await db.execute(stmt)
    keys = list(result.scalars().all())
    with db.no_autoflush:
        for key in keys:
            db.expunge(key)
            key.encrypted_key = None
            key.key_hash = None
    return keys


async def get_api_key_secret(
    db: AsyncSession, key_id: int, user_id: int
) -> str | None:
    stmt = select(ApiKey).where(ApiKey.id == key_id, ApiKey.user_id == user_id)
    result = await db.execute(stmt)
    api_key = result.scalar_one_or_none()
    if api_key is None:
        return None

    api_key.last_viewed_at = datetime.datetime.utcnow()
    await db.commit()
    return decrypt_api_key(api_key.encrypted_key)


async def update_api_key(
    db: AsyncSession, key_id: int, user_id: int, **kwargs
) -> ApiKey | None:
    stmt = select(ApiKey).where(ApiKey.id == key_id, ApiKey.user_id == user_id)
    result = await db.execute(stmt)
    api_key = result.scalar_one_or_none()
    if api_key is None:
        return None

    for field, value in kwargs.items():
        if hasattr(api_key, field):
            setattr(api_key, field, value)
    await db.commit()
    await db.refresh(api_key)
    return api_key


async def revoke_api_key(
    db: AsyncSession, key_id: int, user_id: int
) -> ApiKey | None:
    stmt = select(ApiKey).where(ApiKey.id == key_id, ApiKey.user_id == user_id)
    result = await db.execute(stmt)
    api_key = result.scalar_one_or_none()
    if api_key is None:
        return None

    api_key.status = "revoked"
    api_key.revoked_at = datetime.datetime.utcnow()
    await db.commit()
    await db.refresh(api_key)
    return api_key


async def lookup_api_key_by_token(
    db: AsyncSession, full_key: str
) -> ApiKey | None:
    prefix = get_key_prefix(full_key)
    stmt = select(ApiKey).where(ApiKey.key_prefix == prefix)
    result = await db.execute(stmt)
    candidates = list(result.scalars().all())

    for candidate in candidates:
        if verify_api_key_hash(full_key, candidate.key_hash):
            return candidate
    return None


async def authenticate_api_key(
    db: AsyncSession, full_key: str
) -> ApiKey | None:
    matched = await lookup_api_key_by_token(db, full_key)
    if matched is None:
        return None

    if matched.status == "revoked":
        return None

    if matched.expires_at is not None and matched.expires_at < datetime.datetime.utcnow():
        return None

    matched.last_used_at = datetime.datetime.utcnow()
    await db.commit()
    return matched
