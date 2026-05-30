from __future__ import annotations

import sys
import types
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

for mod_name in ["pageindex", "pydantic_ai", "pydantic_ai.agent", "pydantic_ai.models"]:
    if mod_name not in sys.modules:
        sys.modules[mod_name] = types.ModuleType(mod_name)

if "markitdown" not in sys.modules:
    _fake_md = types.ModuleType("markitdown")
    _fake_md.MarkItDown = MagicMock()
    sys.modules["markitdown"] = _fake_md

from services.markdown_converter import ConversionError, convert_to_markdown  # noqa: E402
from services.page_indexer import IndexNodeCreate, build_index_nodes  # noqa: E402


class TestConvertToMarkdown:
    def test_returns_text_for_simple_file(self, tmp_path: Path) -> None:
        test_file = tmp_path / "test.txt"
        test_file.write_text("hello world", encoding="utf-8")

        mock_result = MagicMock()
        mock_result.text_content = "hello world"

        fake_md = sys.modules["markitdown"]
        fake_md.MarkItDown = MagicMock(return_value=MagicMock(convert=MagicMock(return_value=mock_result)))

        with patch("services.markdown_converter.MarkItDown", return_value=fake_md.MarkItDown.return_value):
            result = convert_to_markdown(test_file)
        assert result == "hello world"

    def test_raises_conversion_error_for_missing_file(self) -> None:
        with pytest.raises(ConversionError, match="File not found"):
            convert_to_markdown("/nonexistent/path/file.txt")

    def test_raises_conversion_error_for_empty_content(self, tmp_path: Path) -> None:
        test_file = tmp_path / "empty.txt"
        test_file.write_text("", encoding="utf-8")

        mock_result = MagicMock()
        mock_result.text_content = ""

        with patch("services.markdown_converter.MarkItDown") as MockMD:
            MockMD.return_value.convert.return_value = mock_result
            with pytest.raises(ConversionError, match="empty content"):
                convert_to_markdown(test_file)

    def test_raises_conversion_error_on_markitdown_failure(self, tmp_path: Path) -> None:
        test_file = tmp_path / "bad.docx"
        test_file.write_bytes(b"garbage")

        with patch("services.markdown_converter.MarkItDown") as MockMD:
            MockMD.return_value.convert.side_effect = RuntimeError("conversion failed")
            with pytest.raises(ConversionError, match="conversion failed"):
                convert_to_markdown(test_file)

    def test_raises_conversion_error_for_whitespace_only(self, tmp_path: Path) -> None:
        test_file = tmp_path / "whitespace.txt"
        test_file.write_text("   \n  \t  ", encoding="utf-8")

        mock_result = MagicMock()
        mock_result.text_content = "   \n  \t  "

        with patch("services.markdown_converter.MarkItDown") as MockMD:
            MockMD.return_value.convert.return_value = mock_result
            with pytest.raises(ConversionError, match="empty content"):
                convert_to_markdown(test_file)


class TestBuildIndexNodes:
    @pytest.mark.asyncio
    async def test_returns_empty_for_empty_text(self) -> None:
        assert await build_index_nodes("") == []
        assert await build_index_nodes("   \n  ") == []

    @pytest.mark.asyncio
    async def test_returns_nodes_for_markdown_with_headings(self) -> None:
        md = "# 第一章 概述\n\n这是概述内容。包含两个句子。第二句在这里。\n\n## 1.1 子节\n\n子节内容。"
        nodes = await build_index_nodes(md)
        assert len(nodes) > 0
        types_found = {n.node_type for n in nodes}
        assert "chapter" in types_found

    @pytest.mark.asyncio
    async def test_node_hierarchy_chapter_section_paragraph(self) -> None:
        md = "# 第一章\n\n第一章正文。\n\n## 1.1 小节\n\n小节正文。"
        nodes = await build_index_nodes(md)
        chapter_nodes = [n for n in nodes if n.node_type == "chapter"]
        section_nodes = [n for n in nodes if n.node_type == "section"]
        paragraph_nodes = [n for n in nodes if n.node_type == "paragraph"]
        assert len(chapter_nodes) >= 1
        assert len(section_nodes) >= 1
        assert len(paragraph_nodes) >= 1

    @pytest.mark.asyncio
    async def test_parent_index_links_correctly(self) -> None:
        md = "# 第一章\n\n正文段落。"
        nodes = await build_index_nodes(md)
        chapter_nodes = [n for n in nodes if n.node_type == "chapter"]
        assert len(chapter_nodes) >= 1
        chapter_idx = nodes.index(chapter_nodes[0])
        for n in nodes:
            if n.node_type == "paragraph" and n.parent_index is not None:
                assert n.parent_index == chapter_idx

    @pytest.mark.asyncio
    async def test_flat_text_without_headings(self) -> None:
        md = "这是一段文字。有多个句子。第三句来了。"
        nodes = await build_index_nodes(md)
        assert len(nodes) > 0
        assert all(n.node_type == "sentence" for n in nodes)

    def test_index_node_create_model(self) -> None:
        node = IndexNodeCreate(
            node_type="chapter",
            path_label="第1章",
            content="内容",
            position=0,
            parent_index=None,
        )
        assert node.node_type == "chapter"
        assert node.parent_index is None

    @pytest.mark.asyncio
    async def test_multiple_chapters(self) -> None:
        md = "# 第一章\n\n内容一。\n\n# 第二章\n\n内容二。"
        nodes = await build_index_nodes(md)
        chapters = [n for n in nodes if n.node_type == "chapter"]
        assert len(chapters) == 2
        assert chapters[0].position == 1
        assert chapters[1].position == 2

    @pytest.mark.asyncio
    async def test_fallback_when_md_path_none(self) -> None:
        md = "# 第一章\n\n内容一。"
        nodes = await build_index_nodes(md, md_path=None)
        assert len(nodes) > 0
        assert nodes[0].node_type == "chapter"

    @pytest.mark.asyncio
    async def test_fallback_when_md_path_nonexistent(self) -> None:
        md = "# 第一章\n\n内容一。"
        nodes = await build_index_nodes(md, md_path="/nonexistent/path.md")
        assert len(nodes) > 0
        assert nodes[0].node_type == "chapter"


class TestConvertTreeToNodes:
    def test_single_node_tree(self) -> None:
        from services.page_indexer import _convert_tree_to_nodes

        tree = {"title": "根节点", "node_id": "1", "text": "根节点正文", "nodes": []}
        nodes = _convert_tree_to_nodes(tree)
        assert len(nodes) == 1
        assert nodes[0].node_type == "chapter"
        assert nodes[0].path_label == "根节点"
        assert nodes[0].content == "根节点正文"
        assert nodes[0].parent_index is None

    def test_nested_tree_depth_mapping(self) -> None:
        from services.page_indexer import _convert_tree_to_nodes

        tree = {
            "title": "章",
            "node_id": "1",
            "text": "",
            "nodes": [
                {
                    "title": "节",
                    "node_id": "2",
                    "text": "节内容",
                    "nodes": [
                        {"title": "段", "node_id": "3", "text": "段内容", "nodes": []}
                    ],
                }
            ],
        }
        nodes = _convert_tree_to_nodes(tree)
        assert len(nodes) == 3
        assert nodes[0].node_type == "chapter"
        assert nodes[1].node_type == "section"
        assert nodes[2].node_type == "paragraph"
        assert nodes[1].parent_index == 0
        assert nodes[2].parent_index == 1

    def test_deep_nesting_caps_at_sentence(self) -> None:
        from services.page_indexer import _convert_tree_to_nodes

        tree = {
            "title": "A",
            "node_id": "1",
            "text": "",
            "nodes": [
                {
                    "title": "B",
                    "node_id": "2",
                    "text": "",
                    "nodes": [
                        {
                            "title": "C",
                            "node_id": "3",
                            "text": "",
                            "nodes": [
                                {
                                    "title": "D",
                                    "node_id": "4",
                                    "text": "最深",
                                    "nodes": [
                                        {
                                            "title": "E",
                                            "node_id": "5",
                                            "text": "更深",
                                            "nodes": [],
                                        }
                                    ],
                                }
                            ],
                        }
                    ],
                }
            ],
        }
        nodes = _convert_tree_to_nodes(tree)
        types = [n.node_type for n in nodes]
        assert types == ["chapter", "section", "paragraph", "sentence", "sentence"]

    def test_path_label_builds_hierarchy(self) -> None:
        from services.page_indexer import _convert_tree_to_nodes

        tree = {
            "title": "第一章",
            "node_id": "1",
            "text": "",
            "nodes": [
                {"title": "1.1", "node_id": "2", "text": "", "nodes": []}
            ],
        }
        nodes = _convert_tree_to_nodes(tree)
        assert nodes[0].path_label == "第一章"
        assert nodes[1].path_label == "第一章 > 1.1"
