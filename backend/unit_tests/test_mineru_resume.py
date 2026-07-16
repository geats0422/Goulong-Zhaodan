from __future__ import annotations

import io
import json
import socket
import zipfile
from pathlib import Path

import httpx
import pytest

from app.lib.mineru import MinerUClient, MinerUError


PUBLIC_IP = "93.184.216.34"


async def _resolver(host: str, port: int):
    return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (PUBLIC_IP, port))]


def _zip(markdown: str) -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        archive.writestr("full.md", markdown)
    return output.getvalue()


class _Stream(httpx.AsyncByteStream):
    def __init__(self, content: bytes) -> None:
        self.content = content

    async def __aiter__(self):
        yield self.content


def _raw(content: bytes = b"") -> httpx.Response:
    return httpx.Response(200, stream=_Stream(content))


def _response(data: dict) -> httpx.Response:
    return _raw(json.dumps(data).encode())


def _client(handler, *, trusted_hosts: str = "objects.example") -> MinerUClient:
    return MinerUClient(
        api_token="test-token",
        poll_interval_seconds=0,
        total_timeout_seconds=10,
        max_zip_bytes=1024 * 1024,
        max_zip_members=10,
        max_compression_ratio=100,
        max_markdown_bytes=1024 * 1024,
        max_json_bytes=4096,
        trusted_hosts=trusted_hosts,
        transport=httpx.MockTransport(handler),
        resolver=_resolver,
    )


@pytest.mark.asyncio
async def test_existing_task_id_resumes_polling_without_new_apply_or_upload(tmp_path: Path) -> None:
    source = tmp_path / "source.pdf"
    source.write_bytes(b"%PDF-1.7")
    methods: list[str] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        methods.append(request.method)
        if request.url.path.endswith("/extract-results/batch/existing-1"):
            return _response(
                {"code": 0, "data": {"extract_result": [{"state": "done", "full_zip_url": "https://objects.example/out.zip"}]}}
            )
        return _raw(_zip("# resumed"))

    result = await _client(handler).parse_pdf_async(str(source), existing_task_id="existing-1")

    assert result.task_id == "existing-1"
    assert methods == ["GET", "GET"]


@pytest.mark.asyncio
async def test_new_task_callbacks_persist_pending_before_upload_and_uploaded_after_put(tmp_path: Path) -> None:
    source = tmp_path / "source.pdf"
    source.write_bytes(b"%PDF-1.7")
    persisted: list[tuple[str, str]] = []

    async def on_task_created(task_id: str, upload_state: str) -> None:
        persisted.append((task_id, upload_state))

    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/file-urls/batch"):
            return _response(
                {"code": 0, "data": {"batch_id": "new-1", "file_urls": ["https://objects.example/upload"]}}
            )
        if request.method == "PUT":
            assert persisted == [("new-1", "pending")]
            return _raw()
        if request.url.path.endswith("/extract-results/batch/new-1"):
            assert persisted == [("new-1", "pending"), ("new-1", "uploaded")]
            return _response(
                {"code": 0, "data": {"extract_result": [{"state": "done", "full_zip_url": "https://objects.example/out.zip"}]}}
            )
        return _raw(_zip("# new"))

    await _client(handler).parse_pdf_async(str(source), on_task_created=on_task_created)
    assert persisted == [("new-1", "pending"), ("new-1", "uploaded")]


@pytest.mark.asyncio
async def test_upload_failure_never_marks_batch_uploaded(tmp_path: Path) -> None:
    source = tmp_path / "source.pdf"
    source.write_bytes(b"%PDF-1.7")
    persisted: list[tuple[str, str]] = []

    async def callback(task_id: str, upload_state: str) -> None:
        persisted.append((task_id, upload_state))

    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/file-urls/batch"):
            return _response(
                {"code": 0, "data": {"batch_id": "failed-1", "file_urls": ["https://objects.example/upload"]}}
            )
        return httpx.Response(500, stream=_Stream(b""))

    with pytest.raises(MinerUError):
        await _client(handler).parse_pdf_async(str(source), on_task_created=callback)
    assert persisted == [("failed-1", "pending")]


@pytest.mark.asyncio
async def test_external_download_url_rejects_non_443_port() -> None:
    client = _client(lambda request: httpx.Response(200))
    with pytest.raises(MinerUError, match="unsafe URL"):
        await client._validate_external_url(
            "https://objects.example:8443/out.zip",
            "download",
            client._clock() + 5,
        )


def test_explicit_trusted_suffix_does_not_trust_apex_or_sibling() -> None:
    client = _client(lambda request: httpx.Response(200), trusted_hosts=".objects.example")
    assert client._is_trusted_host("cdn.objects.example") is True
    assert client._is_trusted_host("objects.example") is False
    assert client._is_trusted_host("evilobjects.example") is False
