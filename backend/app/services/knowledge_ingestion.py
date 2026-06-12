from __future__ import annotations

import logging
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.knowledge import (
    DocumentVersion,
    IndexNode,
    KnowledgeDocument,
)
from app.services.markdown_converter import convert_to_markdown, ConversionError
from app.services.page_indexer import build_index_nodes, IndexingError

logger = logging.getLogger(__name__)


async def ingest_document_content(
    db: AsyncSession,
    document: KnowledgeDocument,
    version: DocumentVersion,
    original_path: str,
    safe_stem: str,
) -> tuple[int, str | None]:
    node_count = 0
    error_msg = None

    try:
        markdown_text = convert_to_markdown(str(original_path))
        md_path = Path(original_path).parent / f"{safe_stem}.md"
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
            elif node_data.parent_index is not None:
                logger.warning("parent_index %d 越界 (已创建 %d 个节点), 节点变为根节点",
                               node_data.parent_index, len(created_nodes))
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

    if version.status in ("completed", "convert_failed", "index_failed"):
        document.current_version_id = version.id

    return node_count, error_msg
