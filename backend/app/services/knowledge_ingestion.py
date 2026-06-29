from __future__ import annotations

import logging
import os
import tempfile

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.knowledge import (
    DocumentVersion,
    IndexNode,
    KnowledgeDocument,
)
from app.services.file_storage import read_file, save_file
from app.services.markdown_converter import convert_to_markdown, ConversionError
from app.services.page_indexer import build_index_nodes, IndexingError

logger = logging.getLogger(__name__)


def _md_storage_path(original_storage_path: str, safe_stem: str) -> str:
    """原始文件 storage_path → 同目录的 md storage_path。"""
    if "/" in original_storage_path:
        parent = original_storage_path.rsplit("/", 1)[0]
        return f"{parent}/{safe_stem}.md"
    return f"{safe_stem}.md"


async def ingest_document_content(
    db: AsyncSession,
    document: KnowledgeDocument,
    version: DocumentVersion,
    original_storage_path: str,
    safe_stem: str,
    original_content: bytes | None = None,
) -> tuple[int, str | None]:
    """解析上传文档：读原始文件 → markitdown 转 md → pageindex 建索引。

    存储后端无关：原始文件与 md 产物都走 file_storage 抽象层（OSS/本地）。
    解析工具（markitdown、pageindex）依赖本地文件，故用临时文件中转。
    """
    node_count = 0
    error_msg = None

    tmp_original = None
    tmp_md = None
    try:
        content = original_content if original_content is not None else read_file(original_storage_path)
        ext = original_storage_path.rsplit(".", 1)[-1].lower() if "." in original_storage_path else "tmp"

        # 原始文件 → 临时文件 → markitdown 解析
        with tempfile.NamedTemporaryFile(suffix=f".{ext}", delete=False) as tmp:
            tmp.write(content)
            tmp_original = tmp.name
        markdown_text = convert_to_markdown(tmp_original)

        # md 产物存存储抽象层（OSS/本地）
        md_storage_path = _md_storage_path(original_storage_path, safe_stem)
        save_file(md_storage_path, markdown_text.encode("utf-8"))
        version.markdown_path = md_storage_path
        version.status = "converting"
        await db.flush()

        # md 临时文件 → pageindex 索引
        with tempfile.NamedTemporaryFile(
            suffix=".md", mode="w", encoding="utf-8", delete=False
        ) as tmp:
            tmp.write(markdown_text)
            tmp_md = tmp.name
        index_nodes = await build_index_nodes(markdown_text, md_path=tmp_md)

        created_nodes: list[IndexNode] = []
        for node_data in index_nodes:
            parent_id = None
            if node_data.parent_index is not None and node_data.parent_index < len(created_nodes):
                parent_id = created_nodes[node_data.parent_index].id
            elif node_data.parent_index is not None:
                logger.warning(
                    "parent_index %d 越界 (已创建 %d 个节点), 节点变为根节点",
                    node_data.parent_index,
                    len(created_nodes),
                )
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
    except Exception as exc:
        version.status = "convert_failed"
        error_msg = str(exc)
        version.error_message = error_msg
    finally:
        # 清理临时文件
        if tmp_original and os.path.exists(tmp_original):
            os.unlink(tmp_original)
        if tmp_md and os.path.exists(tmp_md):
            os.unlink(tmp_md)

    if version.status in ("completed", "convert_failed", "index_failed"):
        document.current_version_id = version.id

    return node_count, error_msg
