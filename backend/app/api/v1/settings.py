from __future__ import annotations

import datetime
import re
import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.auth import get_current_user, hash_password, revoke_all_refresh_tokens, verify_password
from app.core.config import settings
from app.core.constants import ENGINEERING_CATEGORIES
from app.core.database import get_db_session
from app.core.password_rules import validate_password
from app.models.knowledge import (
    EngineeringSubcategory,
    KnowledgeDocument,
    KnowledgeDocumentSetting,
    TabooWord,
    User,
    UserProfile,
)

router = APIRouter(prefix="/settings", tags=["设置"])

PLAN_CATALOG = {
    "free":       {"label": "免费体验",   "period": "永久",  "price": "¥0",    "monthly_quota": 50,    "features": ["基础智能审查", "单文件上传", "Markdown 报告"]},
    "personal":   {"label": "个人版",     "period": "/月",   "price": "¥39",   "monthly_quota": 500,   "features": ["多文件材料包", "私域红线标准", "本地脱敏", "阅后即焚"]},
    "team":       {"label": "团队版",     "period": "/月",   "price": "¥299",  "monthly_quota": 3000,  "features": ["团队协作", "审计留痕", "自定义红线", "优先支持"]},
    "enterprise": {"label": "企业定制",   "period": "按合同", "price": "议价",  "monthly_quota": None,  "features": ["私有化部署", "SSO 单点登录", "SLA 保障", "专属客户成功"]},
}

MODEL_CATALOG = [
    {"model_name": "deepseek-ai/deepseek-v4-pro",   "label": "DeepSeek V4 Pro",   "tier": "高准确度 · 慢", "context": "128K"},
    {"model_name": "deepseek-ai/deepseek-v4-flash", "label": "DeepSeek V4 Flash", "tier": "快速响应",      "context": "64K"},
]

SCOPE_TEMPLATES = [
    {
        "key": "mcp_readonly",
        "label": "MCP 只读",
        "description": "只读查询，适用于 Agent 上下文获取",
        "scopes": ["profile:read", "inspection:read", "knowledge:read"],
    },
    {
        "key": "cli_review",
        "label": "CLI 审查",
        "description": "查询 + AI 生成，适用于 CLI 工具",
        "scopes": ["profile:read", "inspection:run", "inspection:read", "knowledge:read"],
    },
    {
        "key": "agent_automation",
        "label": "Agent 自动化",
        "description": "完整业务自动化，含读写和 AI 生成",
        "scopes": ["profile:read", "inspection:run", "inspection:read", "knowledge:read", "knowledge:write"],
    },
    {
        "key": "advanced_custom",
        "label": "高级自定义",
        "description": "手动选择具权限范围",
        "scopes": [],
    },
]


class ProfileResponse(BaseModel):
    nickname: str
    email: str | None
    phone: str | None
    avatar_url: str | None
    has_wechat: bool
    has_alipay: bool
    subscription_plan: str
    subscription_label: str
    subscription_period: str
    subscription_price: str
    monthly_quota: int
    quota_used: int
    burn_after_read: bool
    model_name: str
    model_base_url: str
    model_api_key_preview: str
    model_catalog: list[dict]
    scope_templates: list[dict]


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
    nickname: str | None = None
    avatar_url: str | None = None
    subscription_plan: str | None = None
    model_name: str | None = None
    burn_after_read: bool | None = None
    email: str | None = None
    phone: str | None = None

    @field_validator("nickname")
    @classmethod
    def validate_nickname(cls, value: str | None) -> str | None:
        if value is None:
            return value
        value = value.strip()
        if not value or len(value) > 100:
            raise ValueError("昵称长度须为 1-100 字符")
        return value

    @field_validator("subscription_plan")
    @classmethod
    def validate_subscription_plan(cls, value: str | None) -> str | None:
        if value is None:
            return value
        if value not in PLAN_CATALOG:
            raise ValueError("subscription_plan 必须在 PLAN_CATALOG 中")
        return value

    @field_validator("model_name")
    @classmethod
    def validate_model_name(cls, value: str | None) -> str | None:
        if value is None:
            return value
        allowed = {m["model_name"] for m in MODEL_CATALOG}
        if value not in allowed:
            raise ValueError("model_name 必须在 MODEL_CATALOG 中")
        return value

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, value: str | None) -> str | None:
        if value is None or value == "":
            return None
        value = value.strip()
        if not re.match(r"^\+?\d{6,20}$", value):
            raise ValueError("手机号格式不正确（6-20 位数字，可带 + 前缀）")
        return value

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str | None) -> str | None:
        if value is None or value == "":
            return None
        value = value.strip().lower()
        if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", value):
            raise ValueError("邮箱格式不正确")
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


def _current_user_id(user: dict) -> uuid.UUID:
    try:
        return uuid.UUID(user["user_id"])
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(status_code=401, detail="Invalid user") from exc


async def _get_user(db: AsyncSession, user_id: uuid.UUID) -> User:
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
        subscription_plan="free",
        monthly_quota=50,
        quota_used=0,
        burn_after_read=True,
    )
    db.add(profile)
    await db.commit()
    await db.refresh(profile)
    return profile


def _profile_response(db_user: User, profile: UserProfile) -> ProfileResponse:
    key = settings.model_api_key
    preview = f"****-****-{key[-4:]}" if len(key) >= 4 else "****"
    plan = PLAN_CATALOG.get(profile.subscription_plan, PLAN_CATALOG["free"])
    effective_model = profile.model_name or settings.model_name
    return ProfileResponse(
        nickname=db_user.nickname,
        email=db_user.email,
        phone=db_user.phone,
        avatar_url=db_user.avatar_url,
        has_wechat=db_user.wechat_openid is not None,
        has_alipay=db_user.alipay_user_id is not None,
        subscription_plan=profile.subscription_plan,
        subscription_label=plan["label"],
        subscription_period=plan["period"],
        subscription_price=plan["price"],
        monthly_quota=profile.monthly_quota or plan["monthly_quota"] or 0,
        quota_used=profile.quota_used,
        burn_after_read=profile.burn_after_read,
        model_name=effective_model,
        model_base_url=settings.model_base_url,
        model_api_key_preview=preview,
        model_catalog=MODEL_CATALOG,
        scope_templates=SCOPE_TEMPLATES,
    )


def _taboo_response(item: TabooWord) -> TabooWordResponse:
    return TabooWordResponse(
        id=item.id,
        word=item.word,
        replacement=item.replacement,
        note=item.note,
    )


async def _build_knowledge(db: AsyncSession, user_id: uuid.UUID) -> list[SettingsKnowledgeCategory]:
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

    if body.nickname is not None:
        db_user.nickname = body.nickname

    if body.avatar_url is not None:
        db_user.avatar_url = body.avatar_url

    if body.subscription_plan is not None and body.subscription_plan != profile.subscription_plan:
        plan_cfg = PLAN_CATALOG[body.subscription_plan]
        profile.subscription_plan = body.subscription_plan
        profile.monthly_quota = plan_cfg["monthly_quota"] or 0

    if body.model_name is not None:
        profile.model_name = body.model_name

    if body.phone is not None:
        if body.phone:
            dup = await db.execute(
                select(User).where(User.phone == body.phone, User.id != db_user.id)
            )
            if dup.scalar_one_or_none() is not None:
                raise HTTPException(status_code=409, detail="手机号已被使用")
        db_user.phone = body.phone

    if body.email is not None:
        if body.email:
            dup = await db.execute(
                select(User).where(User.email == body.email, User.id != db_user.id)
            )
            if dup.scalar_one_or_none() is not None:
                raise HTTPException(status_code=409, detail="邮箱已被使用")
        db_user.email = body.email

    if body.burn_after_read is not None:
        profile.burn_after_read = body.burn_after_read

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
    return SettingsDocument(id=document.id, title=document.title, enabled=body.enabled, owner_type=document.owner_type, application_scenario=document.application_scenario)


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


class CreateApiKeyRequest(BaseModel):
    name: str
    client_type: str
    scope_template: str
    scopes: list[str] | None = None
    expires_at: datetime.datetime | None = None


class ApiKeyResponse(BaseModel):
    id: uuid.UUID
    name: str
    client_type: str
    scope_template: str
    scopes: list[str]
    key_prefix: str
    status: str
    expires_at: datetime.datetime | None
    last_used_at: datetime.datetime | None
    last_viewed_at: datetime.datetime | None
    created_at: datetime.datetime
    updated_at: datetime.datetime


class CreateApiKeyResponse(ApiKeyResponse):
    full_key: str


class ApiKeySecretResponse(BaseModel):
    full_key: str


class UpdateApiKeyRequest(BaseModel):
    name: str | None = None
    scopes: list[str] | None = None
    expires_at: datetime.datetime | None = None


def _api_key_response(api_key) -> ApiKeyResponse:
    return ApiKeyResponse(
        id=api_key.id,
        name=api_key.name,
        client_type=api_key.client_type,
        scope_template=api_key.scope_template,
        scopes=api_key.scopes,
        key_prefix=api_key.key_prefix,
        status=api_key.status,
        expires_at=api_key.expires_at,
        last_used_at=api_key.last_used_at,
        last_viewed_at=api_key.last_viewed_at,
        created_at=api_key.created_at,
        updated_at=api_key.updated_at,
    )


@router.get("/api-keys", response_model=list[ApiKeyResponse])
async def list_api_keys_route(
    db: AsyncSession = Depends(get_db_session),
    user: dict = Depends(get_current_user),
) -> list[ApiKeyResponse]:
    from app.services.api_key_service import list_api_keys

    user_id = _current_user_id(user)
    keys = await list_api_keys(db, user_id)
    return [_api_key_response(k) for k in keys]


@router.post("/api-keys", response_model=CreateApiKeyResponse, status_code=201)
async def create_api_key_route(
    body: CreateApiKeyRequest,
    db: AsyncSession = Depends(get_db_session),
    user: dict = Depends(get_current_user),
) -> CreateApiKeyResponse:
    from app.services.api_key_service import create_api_key

    user_id = _current_user_id(user)
    result = await create_api_key(
        db=db,
        user_id=user_id,
        name=body.name,
        client_type=body.client_type,
        scope_template=body.scope_template,
        user_scopes=body.scopes,
        expires_at=body.expires_at,
    )
    api_key = result["api_key"]
    return CreateApiKeyResponse(
        id=api_key.id,
        name=api_key.name,
        client_type=api_key.client_type,
        scope_template=api_key.scope_template,
        scopes=api_key.scopes,
        key_prefix=api_key.key_prefix,
        status=api_key.status,
        expires_at=api_key.expires_at,
        last_used_at=api_key.last_used_at,
        last_viewed_at=api_key.last_viewed_at,
        created_at=api_key.created_at,
        updated_at=api_key.updated_at,
        full_key=result["full_key"],
    )


@router.get("/api-keys/{key_id}/secret", response_model=ApiKeySecretResponse)
async def get_api_key_secret_route(
    key_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
    user: dict = Depends(get_current_user),
) -> ApiKeySecretResponse:
    from app.services.api_key_service import get_api_key_secret

    user_id = _current_user_id(user)
    full_key = await get_api_key_secret(db, key_id, user_id)
    if full_key is None:
        raise HTTPException(status_code=404, detail="API Key 不存在")
    return ApiKeySecretResponse(full_key=full_key)


@router.patch("/api-keys/{key_id}", response_model=ApiKeyResponse)
async def update_api_key_route(
    key_id: uuid.UUID,
    body: UpdateApiKeyRequest,
    db: AsyncSession = Depends(get_db_session),
    user: dict = Depends(get_current_user),
) -> ApiKeyResponse:
    from app.services.api_key_service import update_api_key

    user_id = _current_user_id(user)
    kwargs = {}
    if body.name is not None:
        kwargs["name"] = body.name
    if body.scopes is not None:
        kwargs["scopes"] = body.scopes
    if body.expires_at is not None:
        kwargs["expires_at"] = body.expires_at

    api_key = await update_api_key(db, key_id, user_id, **kwargs)
    if api_key is None:
        raise HTTPException(status_code=404, detail="API Key 不存在")
    return _api_key_response(api_key)


@router.delete("/api-keys/{key_id}")
async def revoke_api_key_route(
    key_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
    user: dict = Depends(get_current_user),
) -> dict:
    from app.services.api_key_service import revoke_api_key

    user_id = _current_user_id(user)
    api_key = await revoke_api_key(db, key_id, user_id)
    if api_key is None:
        raise HTTPException(status_code=404, detail="API Key 不存在")
    return {"id": api_key.id, "status": api_key.status}
