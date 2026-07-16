from __future__ import annotations

from pathlib import Path

import pytest

from app.lib.mineru import MinerUResult
from app.lib.private_temp import snapshot_file_identity
from app.services import document_parser
from app.services.document_quality import quality_thresholds_from_settings


@pytest.mark.asyncio
async def test_mineru_stage_and_task_callbacks_run_before_remote_processing(tmp_path: Path) -> None:
    source = tmp_path / "source.pdf"
    source.write_bytes(b"%PDF-1.7")
    snapshot = document_parser._Snapshot(
        source,
        "a" * 64,
        snapshot_file_identity(source),
    )
    events: list[tuple[str, str | None]] = []

    class Client:
        async def parse_pdf_async(self, file_path: str, **kwargs):
            events.append(("client", kwargs.get("existing_task_id")))
            await kwargs["on_task_created"]("remote-2")
            return MinerUResult(task_id="remote-2", batch_id="remote-2", markdown="# 标题\n\n" + "有效正文。" * 30)

    async def stage_callback(stage: str) -> None:
        events.append((stage, None))

    async def task_callback(task_id: str) -> None:
        events.append(("task", task_id))

    result = await document_parser._parse_with_mineru(
        snapshot,
        quality_thresholds_from_settings(document_parser.settings),
        Client(),
        stage_callback=stage_callback,
        existing_task_id="remote-1",
        task_created_callback=task_callback,
    )

    assert events == [
        ("parsing_mineru", None),
        ("client", "remote-1"),
        ("task", "remote-2"),
    ]
    assert result.mineru_task_id == "remote-2"
