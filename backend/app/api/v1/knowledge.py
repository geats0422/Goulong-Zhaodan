from __future__ import annotations

import hashlib
import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy import and_, select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.auth import CurrentUserContext, get_current_user
from app.core.constants import (
    validate_category,
    validate_file_type,
    ENGINEERING_CATEGORIES,
)
from app.core.database import get_db_session
from app.core.file_magic import validate_file_magic
from app.core.quota import require_quota
from app.models.knowledge import (
    EngineeringSubcategory,
    KnowledgeDocument,
    DocumentVersion,
    IndexNode,
)
from app.services.document_job_service import SourceArtifact, create_document_job
from app.services.file_storage import build_storage_path, save_file, safe_path_segment

MAX_FILE_SIZE = 50 * 1024 * 1024

router = APIRouter(prefix="/knowledge", tags=["知识库"])


def _current_user_id(user: CurrentUserContext) -> uuid.UUID:
    try:
        return user.user_id
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(status_code=401, detail="Invalid user") from exc


def _is_document_visible(doc: KnowledgeDocument, user_id: uuid.UUID) -> bool:
    return (
        doc.is_active
        and doc.application_scenario == "contract"
        and (doc.owner_type == "system" or doc.owner_user_id == user_id)
    )


def _visible_document_filter(user_id: uuid.UUID):
    return or_(
        and_(
            KnowledgeDocument.is_active.is_(True),
            KnowledgeDocument.application_scenario == "contract",
            KnowledgeDocument.owner_type == "system",
        ),
        and_(
            KnowledgeDocument.is_active.is_(True),
            KnowledgeDocument.application_scenario == "contract",
            KnowledgeDocument.owner_type == "user",
            KnowledgeDocument.owner_user_id == user_id,
        ),
    )


def _validate_contract_application_scenario(application_scenario: str) -> None:
    if application_scenario == "bidding":
        raise HTTPException(
            status_code=400,
            detail={"code": "deprecated_application_scenario", "message": "新知识库仅支持合同场景"},
        )
    if application_scenario != "contract":
        raise HTTPException(
            status_code=400,
            detail={"code": "invalid_application_scenario", "message": "非法应用场景"},
        )


def _safe_path_segment(value: str, fallback: str = "untitled") -> str:
    return safe_path_segment(value, fallback)


class SubcategoryItem(BaseModel):
    id: int
    name: str


class SubcategoryListResponse(BaseModel):
    category: str
    category_label: str
    subcategories: list[SubcategoryItem]


class VersionInfo(BaseModel):
    version_number: int
    display_name: str
    status: str


class DocumentItem(BaseModel):
    id: int
    title: str
    current_version: VersionInfo | None
    subcategory: str
    created_at: str


class DocumentListResponse(BaseModel):
    documents: list[DocumentItem]


class NodeItem(BaseModel):
    id: int
    node_type: str
    path_label: str
    content: str | None
    position: int
    children: list[NodeItem]


class NodeTreeResponse(BaseModel):
    document_id: int
    version_number: int
    nodes: list[NodeItem]


class UploadResponse(BaseModel):
    document_id: int
    version_id: int
    version_number: int
    display_name: str
    status: str
    category: str
    subcategory: str
    application_scenario: str
    node_count: int
    error: str | None
    job_id: str


class OverviewDocument(BaseModel):
    id: int
    title: str
    current_version: VersionInfo | None
    owner_type: str
    application_scenario: str
    created_at: str


class OverviewSubcategory(BaseModel):
    id: int
    name: str
    documents: list[OverviewDocument]


class OverviewCategory(BaseModel):
    key: str
    label: str
    subcategories: list[OverviewSubcategory]


class OverviewResponse(BaseModel):
    categories: list[OverviewCategory]


@router.get("/overview", response_model=OverviewResponse)
async def get_knowledge_overview(
    db=Depends(get_db_session),
    user: CurrentUserContext = Depends(get_current_user),
):
    user_id = _current_user_id(user)
    categories: list[OverviewCategory] = []
    for key, label in ENGINEERING_CATEGORIES.items():
        result = await db.execute(
            select(EngineeringSubcategory)
            .where(EngineeringSubcategory.category_key == key)
            .options(
                selectinload(EngineeringSubcategory.documents).selectinload(
                    KnowledgeDocument.current_version
                )
            )
        )
        subs = result.scalars().all()

        sub_items: list[OverviewSubcategory] = []
        for sub in subs:
            doc_items: list[OverviewDocument] = []
            for doc in sub.documents:
                if not _is_document_visible(doc, user_id):
                    continue
                ver_info = None
                if doc.current_version is not None:
                    ver_info = VersionInfo(
                        version_number=doc.current_version.version_number,
                        display_name=doc.current_version.display_name,
                        status=doc.current_version.status,
                    )
                doc_items.append(
                    OverviewDocument(
                        id=doc.id,
                        title=doc.title,
                        current_version=ver_info,
                        owner_type=doc.owner_type,
                        application_scenario=doc.application_scenario,
                        created_at=doc.created_at.isoformat() if doc.created_at else "",
                    )
                )
            sub_items.append(
                OverviewSubcategory(id=sub.id, name=sub.name, documents=doc_items)
            )
        categories.append(OverviewCategory(key=key, label=label, subcategories=sub_items))
    return OverviewResponse(categories=categories)


async def _get_or_create_subcategory(
    db: AsyncSession,
    category_key: str,
    subcategory_id: int | None,
    subcategory_name: str | None,
) -> EngineeringSubcategory:
    if subcategory_id is not None:
        result = await db.execute(
            select(EngineeringSubcategory).where(EngineeringSubcategory.id == subcategory_id)
        )
        sub = result.scalar_one_or_none()
        if sub is None:
            raise HTTPException(status_code=400, detail=f"Subcategory id={subcategory_id} not found")
        if sub.category_key != category_key:
            raise HTTPException(
                status_code=400,
                detail=f"Subcategory does not belong to category '{category_key}'",
            )
        return sub

    if subcategory_name is not None:
        result = await db.execute(
            select(EngineeringSubcategory).where(
                EngineeringSubcategory.category_key == category_key,
                EngineeringSubcategory.name == subcategory_name,
            )
        )
        sub = result.scalar_one_or_none()
        if sub is not None:
            return sub
        sub = EngineeringSubcategory(category_key=category_key, name=subcategory_name)
        db.add(sub)
        await db.flush()
        await db.refresh(sub)
        return sub

    raise HTTPException(status_code=400, detail="Must provide subcategory_id or subcategory_name")


def _build_display_name(stem: str, ext: str, version_number: int) -> str:
    if version_number == 1:
        return f"{stem}{ext}"
    return f"{stem}({version_number - 1}){ext}"


def _build_node_tree(nodes: list[IndexNode]) -> list[NodeItem]:
    by_id: dict[int | None, list[IndexNode]] = {}
    for node in nodes:
        by_id.setdefault(node.parent_id, []).append(node)

    def _to_item(node: IndexNode) -> NodeItem:
        children = by_id.get(node.id, [])
        return NodeItem(
            id=node.id,
            node_type=node.node_type,
            path_label=node.path_label,
            content=node.content,
            position=node.position,
            children=[_to_item(c) for c in children],
        )

    roots = by_id.get(None, [])
    return [_to_item(n) for n in roots]


@router.get("/subcategories", response_model=SubcategoryListResponse)
async def list_subcategories(
    category: str,
    db=Depends(get_db_session),
    user: CurrentUserContext = Depends(get_current_user),
):
    try:
        category_label = validate_category(category)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    result = await db.execute(
        select(EngineeringSubcategory).where(EngineeringSubcategory.category_key == category)
    )
    subs = result.scalars().all()

    return SubcategoryListResponse(
        category=category,
        category_label=category_label,
        subcategories=[SubcategoryItem(id=s.id, name=s.name) for s in subs],
    )


@router.post("/upload", response_model=UploadResponse)
async def upload_and_ingest(
    file: UploadFile = File(...),
    category: str = Form(...),
    application_scenario: str = Form("contract"),
    subcategory_id: int | None = Form(None),
    subcategory_name: str | None = Form(None),
    db=Depends(get_db_session),
    user: CurrentUserContext = Depends(get_current_user),
):
    filename = file.filename or "unknown"
    _validate_contract_application_scenario(application_scenario)
    await require_quota(db, _current_user_id(user))
    try:
        ext = validate_file_type(filename)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    safe_name = safe_path_segment(filename, fallback=filename)

    try:
        category_label = validate_category(category)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    sub = await _get_or_create_subcategory(db, category, subcategory_id, subcategory_name)
    owner_user_id = _current_user_id(user)

    stem = filename[: filename.rfind(".")] if "." in filename else filename
    stem = stem.strip() or "untitled"
    safe_stem = _safe_path_segment(stem)

    result = await db.execute(
        select(KnowledgeDocument).where(
            KnowledgeDocument.title == stem,
            KnowledgeDocument.subcategory_id == sub.id,
            KnowledgeDocument.owner_type == "user",
            KnowledgeDocument.owner_user_id == owner_user_id,
            KnowledgeDocument.application_scenario == application_scenario,
        )
    )
    existing_doc = result.scalar_one_or_none()

    if existing_doc is not None:
        max_ver_result = await db.execute(
            select(func.max(DocumentVersion.version_number)).where(
                DocumentVersion.document_id == existing_doc.id
            )
        )
        max_ver = max_ver_result.scalar() or 0
        version_number = max_ver + 1
        document = existing_doc
    else:
        version_number = 1
        document = KnowledgeDocument(
            title=stem,
            subcategory_id=sub.id,
            owner_type="user",
            owner_user_id=owner_user_id,
            application_scenario=application_scenario,
        )
        db.add(document)
        await db.flush()
        await db.refresh(document)

    display_name = _build_display_name(stem, ext, version_number)
    content = await file.read()
    file_size = len(content)
    if file_size == 0:
        raise HTTPException(status_code=400, detail="文件内容为空")
    if file_size > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="文件大小超过 50MB 限制")

    try:
        validate_file_magic(filename, content)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    storage_dir = build_storage_path(category, _safe_path_segment(sub.name, "subcategory"), safe_stem, version_number)
    original_storage_path = f"{storage_dir}/{safe_name}"

    version = DocumentVersion(
        document_id=document.id,
        version_number=version_number,
        display_name=display_name,
        original_file_path=original_storage_path,
        status="pending",
        file_size_bytes=file_size,
        file_type=ext,
    )
    db.add(version)
    await db.flush()
    await db.refresh(version)

    save_file(original_storage_path, content)

    content_hash = hashlib.sha256(content).hexdigest()
    source = SourceArtifact(
        user_id=owner_user_id,
        source_path=original_storage_path,
        content_hash=content_hash,
    )
    job = await create_document_job(
        db,
        source=source,
        job_type="knowledge",
        file_type=ext,
        knowledge_version_id=version.id,
    )
    await db.commit()
    await db.refresh(version)

    return UploadResponse(
        document_id=document.id,
        version_id=version.id,
        version_number=version.version_number,
        display_name=version.display_name,
        status="pending",
        category=category_label,
        subcategory=sub.name,
        application_scenario=application_scenario,
        node_count=0,
        error=None,
        job_id=job.job_id,
    )


@router.get("/documents", response_model=DocumentListResponse)
async def list_documents(
    subcategory_id: int,
    application_scenario: str = "contract",
    db=Depends(get_db_session),
    user: CurrentUserContext = Depends(get_current_user),
):
    user_id = _current_user_id(user)
    _validate_contract_application_scenario(application_scenario)
    result = await db.execute(
        select(KnowledgeDocument)
        .where(
            KnowledgeDocument.subcategory_id == subcategory_id,
            KnowledgeDocument.application_scenario == application_scenario,
            KnowledgeDocument.is_active.is_(True),
            _visible_document_filter(user_id),
        )
        .options(
            selectinload(KnowledgeDocument.current_version),
            selectinload(KnowledgeDocument.subcategory),
        )
    )
    docs = result.scalars().all()

    items: list[DocumentItem] = []
    for doc in docs:
        if not _is_document_visible(doc, user_id):
            continue
        ver_info = None
        if doc.current_version is not None:
            ver_info = VersionInfo(
                version_number=doc.current_version.version_number,
                display_name=doc.current_version.display_name,
                status=doc.current_version.status,
            )
        items.append(
            DocumentItem(
                id=doc.id,
                title=doc.title,
                current_version=ver_info,
                subcategory=doc.subcategory.name if doc.subcategory else "",
                created_at=doc.created_at.isoformat() if doc.created_at else "",
            )
        )

    return DocumentListResponse(documents=items)


@router.get("/documents/{document_id}/nodes", response_model=NodeTreeResponse)
async def get_document_nodes(
    document_id: int,
    version_number: int | None = None,
    application_scenario: str = "contract",
    db=Depends(get_db_session),
    user: CurrentUserContext = Depends(get_current_user),
):
    user_id = _current_user_id(user)
    _validate_contract_application_scenario(application_scenario)
    result = await db.execute(
        select(KnowledgeDocument).where(
            KnowledgeDocument.id == document_id,
            KnowledgeDocument.application_scenario == application_scenario,
            _visible_document_filter(user_id),
        )
    )
    document = result.scalar_one_or_none()
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")
    if not _is_document_visible(document, user_id):
        if document.application_scenario == "bidding":
            raise HTTPException(
                status_code=400,
                detail={"code": "deprecated_application_scenario", "message": "招投标知识库已归档"},
            )
        raise HTTPException(status_code=404, detail="Document not found")

    if version_number is not None:
        ver_result = await db.execute(
            select(DocumentVersion).where(
                DocumentVersion.document_id == document_id,
                DocumentVersion.version_number == version_number,
            )
        )
        version = ver_result.scalar_one_or_none()
        if version is None:
            raise HTTPException(status_code=404, detail="Version not found")
    else:
        if document.current_version_id is None:
            return NodeTreeResponse(
                document_id=document_id,
                version_number=0,
                nodes=[],
            )
        ver_result = await db.execute(
            select(DocumentVersion).where(DocumentVersion.id == document.current_version_id)
        )
        version = ver_result.scalar_one_or_none()
        if version is None:
            return NodeTreeResponse(
                document_id=document_id,
                version_number=0,
                nodes=[],
            )

    nodes_result = await db.execute(
        select(IndexNode).where(IndexNode.version_id == version.id).order_by(IndexNode.position)
    )
    all_nodes = nodes_result.scalars().all()

    tree = _build_node_tree(list(all_nodes))

    return NodeTreeResponse(
        document_id=document_id,
        version_number=version.version_number,
        nodes=tree,
    )
