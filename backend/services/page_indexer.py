from __future__ import annotations

import os
import re
import sys
import tempfile
from pathlib import Path
from typing import Any

from pydantic import BaseModel

_DEPTH_NODE_TYPES = ("chapter", "section", "paragraph", "sentence")


class IndexNodeCreate(BaseModel):
    node_type: str
    path_label: str
    content: str
    position: int
    parent_index: int | None = None


class IndexingError(Exception):
    pass


_SENTENCE_END = re.compile(r"(?<=[。！？；])")


async def build_index_nodes(
    markdown_text: str, md_path: str | None = None
) -> list[IndexNodeCreate]:
    if not markdown_text or not markdown_text.strip():
        return []
    try:
        return await _parse_with_pageindex(markdown_text, md_path)
    except Exception:
        return _fallback_parse(markdown_text)


async def _parse_with_pageindex(
    markdown_text: str, md_path: str | None = None
) -> list[IndexNodeCreate]:
    if md_path is None:
        raise IndexingError("no md_path provided for pageindex")

    target_path = md_path
    tmp_file: tempfile._TemporaryFileWrapper | None = None

    if not Path(md_path).exists():
        tmp_file = tempfile.NamedTemporaryFile(
            mode="w", suffix=".md", delete=False, encoding="utf-8"
        )
        tmp_file.write(markdown_text)
        tmp_file.close()
        target_path = tmp_file.name

    try:
        return await _run_pageindex_md_to_tree(target_path)
    finally:
        if tmp_file is not None:
            os.unlink(tmp_file.name)


async def _run_pageindex_md_to_tree(md_path: str) -> list[IndexNodeCreate]:
    from core.config import settings

    vendor_path = Path(__file__).resolve().parents[1] / settings.pageindex_vendor_path
    if not vendor_path.exists():
        raise IndexingError("pageindex vendor not found")

    vendor_str = str(vendor_path)
    if vendor_str not in sys.path:
        sys.path.insert(0, vendor_str)

    try:
        from pageindex.page_index_md import md_to_tree  # type: ignore[import-untyped]
    except Exception as exc:
        raise IndexingError(f"pageindex import failed: {exc}") from exc

    os.environ.setdefault("OPENAI_API_KEY", settings.model_api_key)
    if settings.model_base_url:
        os.environ.setdefault("OPENAI_API_BASE", settings.model_base_url)

    tree = await md_to_tree(
        md_path=md_path,
        if_thinning=False,
        if_add_node_summary=False,
        if_add_node_text=True,
        if_add_node_id=True,
        if_add_doc_description=False,
        model=settings.model_name,
        summary_token_threshold=200,
    )

    if isinstance(tree, str):
        import json

        tree = json.loads(tree)

    structure = tree.get("structure", tree) if isinstance(tree, dict) else tree

    return _convert_tree_list_to_nodes(structure)


def _convert_tree_list_to_nodes(structure: list[dict[str, Any]]) -> list[IndexNodeCreate]:
    nodes: list[IndexNodeCreate] = []
    for root in structure:
        _walk_tree(root, nodes, depth=0, parent_index=None, path_prefix="")
    return nodes


def _convert_tree_to_nodes(tree: dict[str, Any]) -> list[IndexNodeCreate]:
    nodes: list[IndexNodeCreate] = []
    _walk_tree(tree, nodes, depth=0, parent_index=None, path_prefix="")
    return nodes


def _walk_tree(
    node: dict[str, Any],
    nodes: list[IndexNodeCreate],
    depth: int,
    parent_index: int | None,
    path_prefix: str,
) -> None:
    title = node.get("title", "")
    text = node.get("text", "")
    node_id = node.get("node_id", "")
    children = node.get("nodes", [])

    node_type = _DEPTH_NODE_TYPES[min(depth, len(_DEPTH_NODE_TYPES) - 1)]
    label = f"{path_prefix} > {title}" if path_prefix else title

    content = text.strip() if text else ""
    if not content and title:
        content = title

    current_index = len(nodes)
    nodes.append(
        IndexNodeCreate(
            node_type=node_type,
            path_label=label or node_id,
            content=content,
            position=current_index,
            parent_index=parent_index,
        )
    )

    for child in children:
        _walk_tree(child, nodes, depth + 1, current_index, label)


def _fallback_parse(markdown_text: str) -> list[IndexNodeCreate]:
    nodes: list[IndexNodeCreate] = []
    lines = markdown_text.split("\n")
    sections: list[dict[str, Any]] = []
    current_content_lines: list[str] = []
    current_level = 0
    current_heading = ""

    for line in lines:
        heading_match = re.match(r"^(#{1,6})\s+(.+)$", line)
        if heading_match:
            if current_content_lines or current_heading:
                _flush_section(
                    sections, current_level, current_heading, current_content_lines
                )
                current_content_lines = []
            current_level = len(heading_match.group(1))
            current_heading = heading_match.group(2).strip()
        else:
            current_content_lines.append(line)

    if current_heading:
        _flush_section(sections, current_level, current_heading, current_content_lines)

    if not sections:
        paragraphs = _split_paragraphs(markdown_text)
        for p_pos, para in enumerate(paragraphs):
            sentences = _split_sentences(para)
            if not sentences:
                continue
            for s_pos, sentence in enumerate(sentences):
                nodes.append(
                    IndexNodeCreate(
                        node_type="sentence",
                        path_label=f"段落{p_pos + 1} > 句子{s_pos + 1}",
                        content=sentence,
                        position=s_pos,
                    )
                )
        return nodes

    chapter_idx = 0
    section_idx = 0
    para_global = 0

    for sec in sections:
        level = sec["level"]
        heading = sec["heading"]
        content = sec["content"]

        if level == 1:
            chapter_idx += 1
            section_idx = 0
            nodes.append(
                IndexNodeCreate(
                    node_type="chapter",
                    path_label=heading,
                    content=content.strip(),
                    position=chapter_idx,
                    parent_index=None,
                )
            )
        elif level == 2:
            section_idx += 1
            parent_idx = None
            for i, n in enumerate(nodes):
                if n.node_type == "chapter":
                    parent_idx = i
            nodes.append(
                IndexNodeCreate(
                    node_type="section",
                    path_label=heading,
                    content=content.strip(),
                    position=section_idx,
                    parent_index=parent_idx,
                )
            )

        paragraphs = _split_paragraphs(content)
        for p_pos, para in enumerate(paragraphs):
            para_global += 1
            parent_idx = len(nodes) - 1 if nodes else None
            nodes.append(
                IndexNodeCreate(
                    node_type="paragraph",
                    path_label=f"{heading} > 第{p_pos + 1}段",
                    content=para,
                    position=p_pos,
                    parent_index=parent_idx,
                )
            )
            sentences = _split_sentences(para)
            for s_pos, sentence in enumerate(sentences):
                nodes.append(
                    IndexNodeCreate(
                        node_type="sentence",
                        path_label=f"{heading} > 第{p_pos + 1}段 > 句子{s_pos + 1}",
                        content=sentence,
                        position=s_pos,
                        parent_index=len(nodes) - 1,
                    )
                )

    return nodes


def _flush_section(
    sections: list[dict[str, Any]],
    level: int,
    heading: str,
    content_lines: list[str],
) -> None:
    content = "\n".join(content_lines).strip()
    if heading or content:
        sections.append(
            {"level": level, "heading": heading, "content": content}
        )


def _split_paragraphs(text: str) -> list[str]:
    parts = re.split(r"\n\s*\n", text)
    return [p.strip() for p in parts if p.strip()]


def _split_sentences(text: str) -> list[str]:
    parts = _SENTENCE_END.split(text)
    return [s.strip() for s in parts if s.strip()]
