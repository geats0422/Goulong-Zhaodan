from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from app.services import page_indexer


@pytest.mark.asyncio
async def test_worker_mode_propagates_pageindex_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        page_indexer,
        "_parse_with_pageindex",
        AsyncMock(side_effect=RuntimeError("provider secret")),
    )
    with pytest.raises(page_indexer.IndexingError, match="PageIndex failed") as caught:
        await page_indexer.build_index_nodes("# title\nbody", strict=True)
    assert "secret" not in str(caught.value)


@pytest.mark.asyncio
async def test_default_mode_keeps_legacy_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        page_indexer,
        "_parse_with_pageindex",
        AsyncMock(side_effect=RuntimeError("unavailable")),
    )
    nodes = await page_indexer.build_index_nodes("# title\nbody")
    assert nodes


@pytest.mark.asyncio
async def test_strict_mode_rejects_empty_pageindex_nodes(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(page_indexer, "_parse_with_pageindex", AsyncMock(return_value=[]))
    with pytest.raises(page_indexer.IndexingError):
        await page_indexer.build_index_nodes("# title\nbody", md_path="document.md", strict=True)


@pytest.mark.asyncio
async def test_non_strict_mode_keeps_empty_nodes_for_legacy_consumers(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(page_indexer, "_parse_with_pageindex", AsyncMock(return_value=[]))
    assert await page_indexer.build_index_nodes("# title\nbody", md_path="document.md") == []


@pytest.mark.asyncio
async def test_strict_mode_rejects_empty_markdown_as_empty_index() -> None:
    with pytest.raises(page_indexer.IndexingError):
        await page_indexer.build_index_nodes("   ", strict=True)
