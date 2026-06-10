from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from core.auth import get_current_user, hash_password, revoke_all_refresh_tokens, verify_password
from core.constants import ENGINEERING_CATEGORIES
from core.database import get_db_session
from core.password_rules import validate_password
from models.knowledge import (
    EngineeringSubcategory,
    KnowledgeDocument,
    KnowledgeDocumentSetting,
    TabooWord,
    User,
    UserProfile,
)

router = APIRouter(prefix="/settings", tags=["设置"])


class ProfileResponse(BaseModel):
    username: str
    display_name: str
    subscription_plan: str
    monthly_quota: int
    quota_used: int
    wechat_bound: bool
    alipay_bound: bool
    burn_after_read: bool


class SettingsDocument(BaseModel):
    id: int
    title: str
    enabled: bool
    owner_type: str
    application_scenario: str


class SettingsSubcategory(BaseModel):
    id: int
    name: str
    documents: list[SettingsDocument]


class SettingsKnowledgeCategory(BaseModel):
    category_key: str
    category_label: str
    subcategories: list[SettingsSubcategory]


class TabooWordResponse(BaseModel):
    id: int
    word: str
    replacement: str | None
    note: str | None


class SettingsOverviewResponse(BaseModel):
    profile: ProfileResponse
    knowledge: list[SettingsKnowledgeCategory]
    taboo_words: list[TabooWordResponse]


class ProfileUpdateRequest(BaseModel):
    display_name: str | None = None
    wechat_bound: bool | None = None
    alipay_bound: bool | None = None
    burn_after_read: bool | None = None

    @field_validator("display_name")
    @classmethod
    def validate_display_name(cls, value: str | None) -> str | None:
        if value is None:
            return value
        value = value.strip()
        if not value or len(value) > 100:
            raise ValueError("显示名称长度须为 1-100 字符")
        return value


class PasswordUpdateRequest(BaseModel):
    old_password: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def validate_new_password(cls, value: str) -> str:
        errors = validate_password(value)
        if errors:
            raise ValueError("; ".join(errors))
        return value


class KnowledgeDocumentToggleRequest(BaseModel):
    enabled: bool


class TabooWordCreateRequest(BaseModel):
    word: str
    replacement: str | None = None
    note: str | None = None

    @field_validator("word")
    @classmethod
    def validate_word(cls, value: str) -> str:
        value = value.strip()
        if not value or len(value) > 100:
            raise ValueError("违禁词长度须为 1-100 字符")
        return value

    @field_validator("replacement")
    @classmethod
    def normalize_replacement(cls, value: str | None) -> str | None:
        if value is None:
            return value
        value = value.strip()
        return value or None

    @field_validator("note")
    @classmethod
    def normalize_note(cls, value: str | None) -> str | None:
        if value is None:
            return value
        value = value.strip()
        return value or None


class TabooWordUpdateRequest(TabooWordCreateRequest):
    pass


def _current_user_id(user: dict) -> int:
    try:
        return int(user["user_id"])
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(status_code=401, detail="Invalid user") from exc


async def _get_user(db: AsyncSession, user_id: int) -> User:
    result = await db.execute(select(User).where(User.id == user_id))
    db_user = result.scalar_one_or_none()
    if db_user is None:
        raise HTTPException(status_code=401, detail="User not found")
    return db_user


async def _get_or_create_profile(db: AsyncSession, db_user: User) -> UserProfile:
    result = await db.execute(select(UserProfile).where(UserProfile.user_id == db_user.id))
    profile = result.scalar_one_or_none()
    if profile is not None:
        return profile

    profile = UserProfile(
        user_id=db_user.id,
        display_name=db_user.username,
        subscription_plan="personal",
        monthly_quota=500,
        quota_used=0,
        wechat_bound=False,
        alipay_bound=False,
        burn_after_read=True,
    )
    db.add(profile)
    await db.commit()
    await db.refresh(profile)
    return profile


def _profile_response(db_user: User, profile: UserProfile) -> ProfileResponse:
    return ProfileResponse(
        username=db_user.username,
        display_name=profile.display_name,
        subscription_plan=profile.subscription_plan,
        monthly_quota=profile.monthly_quota,
        quota_used=profile.quota_used,
        wechat_bound=profile.wechat_bound,
        alipay_bound=profile.alipay_bound,
        burn_after_read=profile.burn_after_read,
    )


def _taboo_response(item: TabooWord) -> TabooWordResponse:
    return TabooWordResponse(
        id=item.id,
        word=item.word,
        replacement=item.replacement,
        note=item.note,
    )


async def _build_knowledge(db: AsyncSession, user_id: int) -> list[SettingsKnowledgeCategory]:
    setting_result = await db.execute(
        select(KnowledgeDocumentSetting).where(KnowledgeDocumentSetting.user_id == user_id)
    )
    settings_by_doc = {item.document_id: item.enabled for item in setting_result.scalars().all()}

    categories: list[SettingsKnowledgeCategory] = []
    for key, label in ENGINEERING_CATEGORIES.items():
        result = await db.execute(
            select(EngineeringSubcategory)
            .where(EngineeringSubcategory.category_key == key)
            .options(selectinload(EngineeringSubcategory.documents))
        )
        subcategories = []
        for sub in result.scalars().all():
            documents = [
                SettingsDocument(
                    id=doc.id,
                    title=doc.title,
                    enabled=settings_by_doc.get(doc.id, True),
                    owner_type=doc.owner_type,
                    application_scenario=doc.application_scenario,
                )
                for doc in sub.documents
            ]
            subcategories.append(SettingsSubcategory(id=sub.id, name=sub.name, documents=documents))
        categories.append(
            SettingsKnowledgeCategory(
                category_key=key,
                category_label=label,
                subcategories=subcategories,
            )
        )
    return categories


@router.get("/overview", response_model=SettingsOverviewResponse)
async def get_settings_overview(
    db: AsyncSession = Depends(get_db_session),
    user: dict = Depends(get_current_user),
) -> SettingsOverviewResponse:
    user_id = _current_user_id(user)
    db_user = await _get_user(db, user_id)
    profile = await _get_or_create_profile(db, db_user)

    taboo_result = await db.execute(select(TabooWord).where(TabooWord.user_id == user_id).order_by(TabooWord.id))
    taboo_words = [_taboo_response(item) for item in taboo_result.scalars().all()]

    return SettingsOverviewResponse(
        profile=_profile_response(db_user, profile),
        knowledge=await _build_knowledge(db, user_id),
        taboo_words=taboo_words,
    )


@router.patch("/profile", response_model=ProfileResponse)
async def update_profile(
    body: ProfileUpdateRequest,
    db: AsyncSession = Depends(get_db_session),
    user: dict = Depends(get_current_user),
) -> ProfileResponse:
    user_id = _current_user_id(user)
    db_user = await _get_user(db, user_id)
    profile = await _get_or_create_profile(db, db_user)

    for field in ("display_name", "wechat_bound", "alipay_bound", "burn_after_read"):
        value = getattr(body, field)
        if value is not None:
            setattr(profile, field, value)

    await db.commit()
    await db.refresh(profile)
    return _profile_response(db_user, profile)


@router.post("/password")
async def update_password(
    body: PasswordUpdateRequest,
    db: AsyncSession = Depends(get_db_session),
    user: dict = Depends(get_current_user),
) -> dict[str, bool]:
    user_id = _current_user_id(user)
    db_user = await _get_user(db, user_id)
    if not verify_password(body.old_password, db_user.hashed_password):
        raise HTTPException(status_code=400, detail="旧密码错误")

    db_user.hashed_password = hash_password(body.new_password)
    await revoke_all_refresh_tokens(db, user_id)
    await db.commit()
    return {"success": True}


@router.patch("/knowledge/documents/{document_id}", response_model=SettingsDocument)
async def update_knowledge_document_setting(
    document_id: int,
    body: KnowledgeDocumentToggleRequest,
    db: AsyncSession = Depends(get_db_session),
    user: dict = Depends(get_current_user),
) -> SettingsDocument:
    user_id = _current_user_id(user)
    doc_result = await db.execute(select(KnowledgeDocument).where(KnowledgeDocument.id == document_id))
    document = doc_result.scalar_one_or_none()
    if document is None:
        raise HTTPException(status_code=404, detail="文档不存在")

    setting_result = await db.execute(
        select(KnowledgeDocumentSetting).where(
            KnowledgeDocumentSetting.user_id == user_id,
            KnowledgeDocumentSetting.document_id == document_id,
        )
    )
    setting = setting_result.scalar_one_or_none()
    if setting is None:
        setting = KnowledgeDocumentSetting(user_id=user_id, document_id=document_id, enabled=body.enabled)
        db.add(setting)
    else:
        setting.enabled = body.enabled

    await db.commit()
    return SettingsDocument(id=document.id, title=document.title, enabled=body.enabled)


@router.post("/taboo-words", response_model=TabooWordResponse, status_code=201)
async def create_taboo_word(
    body: TabooWordCreateRequest,
    db: AsyncSession = Depends(get_db_session),
    user: dict = Depends(get_current_user),
) -> TabooWordResponse:
    user_id = _current_user_id(user)
    result = await db.execute(select(TabooWord).where(TabooWord.user_id == user_id, TabooWord.word == body.word))
    if result.scalar_one_or_none() is not None:
        raise HTTPException(status_code=409, detail="违禁词已存在")

    item = TabooWord(user_id=user_id, word=body.word, replacement=body.replacement, note=body.note)
    db.add(item)
    await db.commit()
    await db.refresh(item)
    return _taboo_response(item)


@router.patch("/taboo-words/{word_id}", response_model=TabooWordResponse)
async def update_taboo_word(
    word_id: int,
    body: TabooWordUpdateRequest,
    db: AsyncSession = Depends(get_db_session),
    user: dict = Depends(get_current_user),
) -> TabooWordResponse:
    user_id = _current_user_id(user)
    result = await db.execute(select(TabooWord).where(TabooWord.id == word_id, TabooWord.user_id == user_id))
    item = result.scalar_one_or_none()
    if item is None:
        raise HTTPException(status_code=404, detail="违禁词不存在")

    duplicate = await db.execute(
        select(TabooWord).where(
            TabooWord.user_id == user_id,
            TabooWord.word == body.word,
            TabooWord.id != word_id,
        )
    )
    if duplicate.scalar_one_or_none() is not None:
        raise HTTPException(status_code=409, detail="违禁词已存在")

    item.word = body.word
    item.replacement = body.replacement
    item.note = body.note
    await db.commit()
    await db.refresh(item)
    return _taboo_response(item)


@router.delete("/taboo-words/{word_id}", status_code=204)
async def delete_taboo_word(
    word_id: int,
    db: AsyncSession = Depends(get_db_session),
    user: dict = Depends(get_current_user),
) -> None:
    user_id = _current_user_id(user)
    result = await db.execute(select(TabooWord).where(TabooWord.id == word_id, TabooWord.user_id == user_id))
    item = result.scalar_one_or_none()
    if item is None:
        raise HTTPException(status_code=404, detail="违禁词不存在")
    await db.delete(item)
    await db.commit()
    return None
