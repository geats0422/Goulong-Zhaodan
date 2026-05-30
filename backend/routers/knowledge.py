from __future__ import annotations

import re

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from core.auth import get_current_user
from core.constants import validate_category, validate_file_type, ENGINEERING_CATEGORIES
from core.database import get_db_session
from models.knowledge import (
    EngineeringSubcategory,
    KnowledgeDocument,
    DocumentVersion,
    IndexNode,
)
from services.file_storage import build_storage_path, save_upload_file
from services.markdown_converter import convert_to_markdown, ConversionError
from services.page_indexer import build_index_nodes, IndexingError

MAX_FILE_SIZE = 50 * 1024 * 1024

router = APIRouter(prefix="/knowledge", tags=["知识库"])


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
    node_count: int
    error: str | None


class OverviewDocument(BaseModel):
    id: int
    title: str
    current_version: VersionInfo | None
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
    db: AsyncSession = Depends(get_db_session),
    user: dict = Depends(get_current_user),
):
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
    db: AsyncSession = Depends(get_db_session),
    user: dict = Depends(get_current_user),
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
    subcategory_id: int | None = Form(None),
    subcategory_name: str | None = Form(None),
    db: AsyncSession = Depends(get_db_session),
    user: dict = Depends(get_current_user),
):
    filename = file.filename or "unknown"
    try:
        ext = validate_file_type(filename)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    safe_name = re.sub(r"[^\w.\-]", "_", filename)

    try:
        category_label = validate_category(category)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    sub = await _get_or_create_subcategory(db, category, subcategory_id, subcategory_name)

    stem = filename[: filename.rfind(".")] if "." in filename else filename
    stem = stem.strip() or "untitled"

    result = await db.execute(
        select(KnowledgeDocument).where(
            KnowledgeDocument.title == stem,
            KnowledgeDocument.subcategory_id == sub.id,
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
        document = KnowledgeDocument(title=stem, subcategory_id=sub.id)
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

    storage_dir = build_storage_path(category, sub.name, stem, version_number)
    original_path = storage_dir / safe_name

    version = DocumentVersion(
        document_id=document.id,
        version_number=version_number,
        display_name=display_name,
        original_file_path=str(original_path),
        status="pending",
        file_size_bytes=file_size,
        file_type=ext,
    )
    db.add(version)
    await db.flush()
    await db.refresh(version)

    save_upload_file(original_path, content)

    node_count = 0
    error_msg = None

    try:
        markdown_text = convert_to_markdown(str(original_path))
        md_path = original_path.parent / f"{stem}.md"
        md_path.parent.mkdir(parents=True, exist_ok=True)
        md_path.write_text(markdown_text, encoding="utf-8")
        version.markdown_path = str(md_path)
        version.status = "converting"
        await db.flush()

        index_nodes = await build_index_nodes(markdown_text, md_path=str(md_path))
        created_nodes: list[IndexNode] = []
        for node_data in index_nodes:
            parent_id = None
            if node_data.parent_index is not None and node_data.parent_index < len(created_nodes):
                parent_id = created_nodes[node_data.parent_index].id
            node = IndexNode(
                version_id=version.id,
                parent_id=parent_id,
                node_type=node_data.node_type,
                path_label=node_data.path_label,
                content=node_data.content,
                position=node_data.position,
            )
            created_nodes.append(node)
        db.add_all(created_nodes)
        await db.flush()

        node_count = len(created_nodes)
        version.status = "completed"
    except (ConversionError, IndexingError) as exc:
        if isinstance(exc, ConversionError):
            version.status = "convert_failed"
        else:
            version.status = "index_failed"
        error_msg = str(exc)
        version.error_message = error_msg

    if version.status in ("completed", "convert_failed", "index_failed"):
        document.current_version_id = version.id
    await db.commit()
    await db.refresh(version)

    return UploadResponse(
        document_id=document.id,
        version_id=version.id,
        version_number=version.version_number,
        display_name=version.display_name,
        status=version.status,
        category=category_label,
        subcategory=sub.name,
        node_count=node_count,
        error=error_msg,
    )


@router.get("/documents", response_model=DocumentListResponse)
async def list_documents(
    subcategory_id: int,
    db: AsyncSession = Depends(get_db_session),
    user: dict = Depends(get_current_user),
):
    result = await db.execute(
        select(KnowledgeDocument).where(KnowledgeDocument.subcategory_id == subcategory_id)
    )
    docs = result.scalars().all()

    items: list[DocumentItem] = []
    for doc in docs:
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
    db: AsyncSession = Depends(get_db_session),
    user: dict = Depends(get_current_user),
):
    result = await db.execute(
        select(KnowledgeDocument).where(KnowledgeDocument.id == document_id)
    )
    document = result.scalar_one_or_none()
    if document is None:
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
