from __future__ import annotations

import asyncio
import io
import json
import logging
import multiprocessing
import socket
import ssl
import sys
import time
import zipfile
from collections.abc import Awaitable, Callable
from pathlib import Path
from unittest.mock import patch

import httpx
import pytest
from pydantic import ValidationError

from app.core.config import Settings, assert_production_security
from app.lib.mineru.client import (
    MinerUClient,
    MinerUError,
    MinerUResult,
    _PinnedAsyncTransport,
)

TOKEN = "unit-test-token"
UPLOAD_URL = "https://objects.example/upload?signature=upload-secret"
ZIP_URL = "https://objects.example/result?signature=download-secret"
PUBLIC_IP = "93.184.216.34"
DOCUMENT_TEXT = "不得出现在错误或日志中的原文"

Resolver = Callable[[str, int], Awaitable[list[tuple]]]


async def _public_resolver(host: str, port: int) -> list[tuple]:
    return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (PUBLIC_IP, port))]


def _markdown_zip(markdown: str | bytes, *, compression: int = zipfile.ZIP_STORED) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=compression) as archive:
        archive.writestr("result/full.md", markdown)
    return buffer.getvalue()


class _RawStream(httpx.AsyncByteStream):
    def __init__(self, content: bytes) -> None:
        self.content = content

    async def __aiter__(self):
        yield self.content


def _raw_response(
    status_code: int,
    content: bytes = b"",
    headers: dict[str, str] | None = None,
) -> httpx.Response:
    return httpx.Response(status_code, headers=headers, stream=_RawStream(content))


def _json_response(data: dict, status_code: int = 200) -> httpx.Response:
    return _raw_response(status_code, json.dumps(data, ensure_ascii=False).encode())


def _client(
    handler: Callable[[httpx.Request], Awaitable[httpx.Response]],
    *,
    resolver: Resolver = _public_resolver,
    **overrides: object,
) -> MinerUClient:
    options: dict[str, object] = {
        "api_token": TOKEN,
        "model_version": "pipeline",
        "enable_ocr": True,
        "language": "ch",
        "request_timeout_seconds": 5,
        "poll_interval_seconds": 0,
        "total_timeout_seconds": 30,
        "max_zip_bytes": 1024 * 1024,
        "max_zip_members": 20,
        "max_compression_ratio": 100,
        "max_markdown_bytes": 1024 * 1024,
        "max_json_bytes": 1024,
        "trusted_hosts": "objects.example",
        "transport": httpx.MockTransport(handler),
        "resolver": resolver,
    }
    options.update(overrides)
    return MinerUClient(**options)


def _run(coro):
    return asyncio.run(coro)


def test_result_never_contains_presigned_url(tmp_path: Path) -> None:
    document = tmp_path / "sample.pdf"
    document.write_bytes(b"pdf")
    poll_count = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal poll_count
        if request.url.path.endswith("/file-urls/batch"):
            return _json_response({"code": 0, "data": {"batch_id": "batch-1", "file_urls": [UPLOAD_URL]}})
        if request.method == "PUT":
            return _raw_response(200)
        if request.url.path.endswith("/extract-results/batch/batch-1"):
            poll_count += 1
            if poll_count == 1:
                return _json_response({"code": 0, "data": {"extract_result": []}})
            return _json_response(
                {"code": 0, "data": {"extract_result": [{"state": "done", "full_zip_url": ZIP_URL}]}}
            )
        return _raw_response(200, _markdown_zip("# 解析结果"))

    result = _run(_client(handler).parse_pdf_async(str(document)))

    assert result == MinerUResult(task_id="batch-1", batch_id="batch-1", markdown="# 解析结果")
    assert "url" not in {name.lower() for name in result.__dataclass_fields__}
    assert "signature=" not in repr(result)


@pytest.mark.parametrize(
    ("failure_stage", "expected_code"),
    [
        ("apply", "apply"),
        ("upload", "upload"),
        ("poll", "poll"),
        ("upstream_failed", "upstream_failed"),
        ("download", "download"),
    ],
)
def test_http_and_upstream_failures_have_stable_sanitized_codes(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
    failure_stage: str,
    expected_code: str,
) -> None:
    document = tmp_path / "sample.pdf"
    document.write_text(DOCUMENT_TEXT, encoding="utf-8")

    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/file-urls/batch"):
            if failure_stage == "apply":
                return _raw_response(500, f"{TOKEN} {UPLOAD_URL} {DOCUMENT_TEXT}".encode())
            return _json_response({"code": 0, "data": {"batch_id": "batch-1", "file_urls": [UPLOAD_URL]}})
        if request.method == "PUT":
            if failure_stage == "upload":
                return _raw_response(500, f"{TOKEN} {UPLOAD_URL} {DOCUMENT_TEXT}".encode())
            return _raw_response(200)
        if request.url.path.endswith("/extract-results/batch/batch-1"):
            if failure_stage == "poll":
                return _raw_response(500, f"{TOKEN} {ZIP_URL} {DOCUMENT_TEXT}".encode())
            state = "failed" if failure_stage == "upstream_failed" else "done"
            return _json_response(
                {
                    "code": 0,
                    "data": {
                        "extract_result": [
                            {"state": state, "full_zip_url": ZIP_URL, "err_msg": f"{TOKEN} {DOCUMENT_TEXT}"}
                        ]
                    },
                }
            )
        if failure_stage == "download":
            return _raw_response(500, f"{TOKEN} {ZIP_URL} {DOCUMENT_TEXT}".encode())
        return _raw_response(200, _markdown_zip("markdown"))

    caplog.set_level(logging.INFO)
    with pytest.raises(MinerUError) as caught:
        _run(_client(handler).parse_pdf_async(str(document)))

    assert caught.value.code == expected_code
    exposed = f"{caught.value}\n{caplog.text}"
    assert TOKEN not in exposed
    assert UPLOAD_URL not in exposed
    assert ZIP_URL not in exposed
    assert DOCUMENT_TEXT not in exposed


def test_request_timeout_is_shared_by_every_http_stage(tmp_path: Path) -> None:
    document = tmp_path / "sample.pdf"
    document.write_bytes(b"pdf")
    observed_timeouts: list[float] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        observed_timeouts.append(request.extensions["timeout"]["read"])
        if request.url.path.endswith("/file-urls/batch"):
            return _json_response({"code": 0, "data": {"batch_id": "batch-1", "file_urls": [UPLOAD_URL]}})
        if request.method == "PUT":
            return _raw_response(200)
        if request.url.path.endswith("/extract-results/batch/batch-1"):
            return _json_response(
                {"code": 0, "data": {"extract_result": [{"state": "done", "full_zip_url": ZIP_URL}]}}
            )
        return _raw_response(200, _markdown_zip("markdown"))

    _run(_client(handler, request_timeout_seconds=2).parse_pdf_async(str(document)))

    assert observed_timeouts == [2, 2, 2, 2]


def test_every_request_uses_identity_content_encoding(tmp_path: Path) -> None:
    document = tmp_path / "sample.pdf"
    document.write_bytes(b"pdf")
    observed_encodings: list[str] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        observed_encodings.append(request.headers["Accept-Encoding"])
        if request.url.path.endswith("/file-urls/batch"):
            return _json_response({"code": 0, "data": {"batch_id": "batch-1", "file_urls": [UPLOAD_URL]}})
        if request.method == "PUT":
            return _raw_response(200, headers={"Content-Encoding": "identity"})
        if request.url.path.endswith("/extract-results/batch/batch-1"):
            return _json_response(
                {"code": 0, "data": {"extract_result": [{"state": "done", "full_zip_url": ZIP_URL}]}}
            )
        return _raw_response(
            200,
            _markdown_zip("markdown"),
            headers={"Content-Encoding": "identity"},
        )

    _run(_client(handler).parse_pdf_async(str(document)))

    assert observed_encodings == ["identity", "identity", "identity", "identity"]


@pytest.mark.parametrize("failure_stage", ["apply", "download"])
def test_rejects_non_identity_content_encoding(tmp_path: Path, failure_stage: str) -> None:
    document = tmp_path / "sample.pdf"
    document.write_bytes(b"pdf")

    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/file-urls/batch"):
            if failure_stage == "apply":
                return _raw_response(200, b"compressed", headers={"Content-Encoding": "gzip"})
            return _json_response({"code": 0, "data": {"batch_id": "batch-1", "file_urls": [UPLOAD_URL]}})
        if request.method == "PUT":
            return _raw_response(200)
        if request.url.path.endswith("/extract-results/batch/batch-1"):
            return _json_response(
                {"code": 0, "data": {"extract_result": [{"state": "done", "full_zip_url": ZIP_URL}]}}
            )
        return _raw_response(200, b"compressed", headers={"Content-Encoding": "br"})

    with pytest.raises(MinerUError) as caught:
        _run(_client(handler).parse_pdf_async(str(document)))

    assert caught.value.code == failure_stage


@pytest.mark.parametrize("failure_stage", ["apply", "poll"])
def test_apply_and_poll_json_bodies_have_streaming_size_limit(tmp_path: Path, failure_stage: str) -> None:
    document = tmp_path / "sample.pdf"
    document.write_bytes(b"pdf")

    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/file-urls/batch"):
            if failure_stage == "apply":
                return _raw_response(200, b"{" + b"x" * 500 + b"}")
            return _json_response({"code": 0, "data": {"batch_id": "batch-1", "file_urls": [UPLOAD_URL]}})
        if request.method == "PUT":
            return _raw_response(200)
        return _raw_response(200, b"{" + b"x" * 500 + b"}")

    with pytest.raises(MinerUError) as caught:
        _run(_client(handler, max_json_bytes=300).parse_pdf_async(str(document)))

    assert caught.value.code == failure_stage


def test_end_to_end_deadline_includes_apply_upload_poll_and_download(tmp_path: Path) -> None:
    document = tmp_path / "sample.pdf"
    document.write_bytes(b"pdf")

    class Clock:
        value = 0.0

        def __call__(self) -> float:
            return self.value

    clock = Clock()
    observed_timeouts: list[float] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        observed_timeouts.append(request.extensions["timeout"]["read"])
        clock.value += 2
        if request.url.path.endswith("/file-urls/batch"):
            return _json_response({"code": 0, "data": {"batch_id": "batch-1", "file_urls": [UPLOAD_URL]}})
        if request.method == "PUT":
            return _raw_response(200)
        if request.url.path.endswith("/extract-results/batch/batch-1"):
            return _json_response(
                {"code": 0, "data": {"extract_result": [{"state": "done", "full_zip_url": ZIP_URL}]}}
            )
        clock.value += 3
        return _raw_response(200, _markdown_zip("markdown"))

    with pytest.raises(MinerUError) as caught:
        _run(
            _client(
                handler,
                request_timeout_seconds=20,
                total_timeout_seconds=10,
                clock=clock,
            ).parse_pdf_async(str(document))
        )

    assert caught.value.code == "timeout"
    assert observed_timeouts == [10, 8, 6, 4]


def test_async_request_is_cancellable_without_background_thread(tmp_path: Path) -> None:
    document = tmp_path / "sample.pdf"
    document.write_bytes(b"pdf")
    started = asyncio.Event()

    async def scenario() -> None:
        async def handler(_request: httpx.Request) -> httpx.Response:
            started.set()
            await asyncio.Event().wait()
            raise AssertionError("unreachable")

        task = asyncio.create_task(_client(handler).parse_pdf_async(str(document)))
        await started.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    _run(scenario())


@pytest.mark.parametrize(
    "unsafe_url",
    [
        "http://objects.example/upload",
        "https://localhost/upload",
        "https://127.0.0.1/upload",
        "https://10.0.0.1/upload",
        "https://169.254.169.254/latest/meta-data",
        "https://[::1]/upload",
    ],
)
def test_rejects_unsafe_upload_urls_before_put(tmp_path: Path, unsafe_url: str) -> None:
    document = tmp_path / "sample.pdf"
    document.write_bytes(b"pdf")
    requests: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return _json_response({"code": 0, "data": {"batch_id": "batch-1", "file_urls": [unsafe_url]}})

    with pytest.raises(MinerUError) as caught:
        _run(_client(handler).parse_pdf_async(str(document)))

    assert caught.value.code == "apply"
    assert len(requests) == 1


def test_rejects_hostname_that_resolves_to_private_address(tmp_path: Path) -> None:
    document = tmp_path / "sample.pdf"
    document.write_bytes(b"pdf")

    async def private_resolver(_host: str, port: int) -> list[tuple]:
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("192.168.1.10", port))]

    async def handler(_request: httpx.Request) -> httpx.Response:
        return _json_response(
            {"code": 0, "data": {"batch_id": "batch-1", "file_urls": ["https://storage.example/upload"]}}
        )

    with pytest.raises(MinerUError) as caught:
        _run(_client(handler, resolver=private_resolver).parse_pdf_async(str(document)))

    assert caught.value.code == "apply"


def test_rejects_public_hostname_outside_trusted_allowlist(tmp_path: Path) -> None:
    document = tmp_path / "sample.pdf"
    document.write_bytes(b"pdf")
    requests: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return _json_response(
            {"code": 0, "data": {"batch_id": "batch-1", "file_urls": ["https://attacker.example/upload"]}}
        )

    with pytest.raises(MinerUError) as caught:
        _run(_client(handler, trusted_hosts="objects.example,.trusted-storage.example").parse_pdf_async(str(document)))

    assert caught.value.code == "apply"
    assert len(requests) == 1


def test_rejects_dns_resolution_that_changes_before_request(tmp_path: Path) -> None:
    document = tmp_path / "sample.pdf"
    document.write_bytes(b"pdf")
    resolutions = iter([PUBLIC_IP, "192.168.1.10"])
    requests: list[httpx.Request] = []

    async def rebinding_resolver(_host: str, port: int) -> list[tuple]:
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (next(resolutions), port))]

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return _json_response({"code": 0, "data": {"batch_id": "batch-1", "file_urls": [UPLOAD_URL]}})

    with pytest.raises(MinerUError) as caught:
        _run(_client(handler, resolver=rebinding_resolver).parse_pdf_async(str(document)))

    assert caught.value.code == "apply"
    assert len(requests) == 1


def test_rejects_unsafe_download_url_before_get(tmp_path: Path) -> None:
    document = tmp_path / "sample.pdf"
    document.write_bytes(b"pdf")
    requests: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path.endswith("/file-urls/batch"):
            return _json_response({"code": 0, "data": {"batch_id": "batch-1", "file_urls": [UPLOAD_URL]}})
        if request.method == "PUT":
            return _raw_response(200)
        return _json_response(
            {
                "code": 0,
                "data": {
                    "extract_result": [
                        {"state": "done", "full_zip_url": "https://169.254.169.254/result"}
                    ]
                },
            }
        )

    with pytest.raises(MinerUError) as caught:
        _run(_client(handler).parse_pdf_async(str(document)))

    assert caught.value.code == "download"
    assert len(requests) == 3


@pytest.mark.parametrize(
    ("archive_factory", "overrides"),
    [
        (lambda: b"x" * 100, {"max_zip_bytes": 50}),
        (
            lambda: _zip_with_members(3),
            {"max_zip_members": 2},
        ),
        (
            lambda: _markdown_zip("a" * 10000, compression=zipfile.ZIP_DEFLATED),
            {"max_compression_ratio": 2},
        ),
        (
            lambda: _markdown_zip("a" * 100),
            {"max_markdown_bytes": 50},
        ),
    ],
    ids=["zip-size", "member-count", "compression-ratio", "markdown-size"],
)
def test_rejects_oversized_or_dangerous_archives(
    tmp_path: Path,
    archive_factory: Callable[[], bytes],
    overrides: dict[str, object],
) -> None:
    document = tmp_path / "sample.pdf"
    document.write_bytes(b"pdf")
    archive = archive_factory()

    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/file-urls/batch"):
            return _json_response({"code": 0, "data": {"batch_id": "batch-1", "file_urls": [UPLOAD_URL]}})
        if request.method == "PUT":
            return _raw_response(200)
        if request.url.path.endswith("/extract-results/batch/batch-1"):
            return _json_response(
                {"code": 0, "data": {"extract_result": [{"state": "done", "full_zip_url": ZIP_URL}]}}
            )
        return _raw_response(200, archive)

    with pytest.raises(MinerUError) as caught:
        _run(_client(handler, **overrides).parse_pdf_async(str(document)))

    assert caught.value.code == "invalid_archive"


def _zip_with_members(count: int) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for index in range(count):
            archive.writestr(f"{index}.md", "markdown")
    return buffer.getvalue()


@pytest.mark.parametrize("archive", [b"not-a-zip", _markdown_zip(b"\xff")])
def test_invalid_archive_has_stable_error(tmp_path: Path, archive: bytes) -> None:
    document = tmp_path / "sample.pdf"
    document.write_bytes(b"pdf")

    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/file-urls/batch"):
            return _json_response({"code": 0, "data": {"batch_id": "batch-1", "file_urls": [UPLOAD_URL]}})
        if request.method == "PUT":
            return _raw_response(200)
        if request.url.path.endswith("/extract-results/batch/batch-1"):
            return _json_response(
                {"code": 0, "data": {"extract_result": [{"state": "done", "full_zip_url": ZIP_URL}]}}
            )
        return _raw_response(200, archive)

    with pytest.raises(MinerUError) as caught:
        _run(_client(handler).parse_pdf_async(str(document)))

    assert caught.value.code == "invalid_archive"


def test_unsupported_archive_error_is_mapped_to_stable_code() -> None:
    async def unused_handler(_request: httpx.Request) -> httpx.Response:
        raise AssertionError("HTTP is not used")

    client = _client(unused_handler)
    with patch("app.lib.mineru.client.zipfile.ZipFile", side_effect=NotImplementedError):
        with pytest.raises(MinerUError) as caught:
            client._extract_markdown(b"archive")

    assert caught.value.code == "invalid_archive"


def test_archive_timeout_terminates_and_joins_worker() -> None:
    class FakeReceiver:
        def poll(self) -> bool:
            return False

        def close(self) -> None:
            pass

    class FakeSender:
        def close(self) -> None:
            pass

    class FakeProcess:
        terminated = False
        joined = False

        def start(self) -> None:
            pass

        def is_alive(self) -> bool:
            return not self.terminated

        def terminate(self) -> None:
            self.terminated = True

        def kill(self) -> None:
            self.terminated = True

        def join(self, timeout: float | None = None) -> None:
            self.joined = True

    process = FakeProcess()

    class FakeContext:
        def Pipe(self, duplex: bool = False):
            return FakeReceiver(), FakeSender()

        def Process(self, **_kwargs):
            return process

    async def unused_handler(_request: httpx.Request) -> httpx.Response:
        raise AssertionError("HTTP is not used")

    client = _client(unused_handler, process_context=FakeContext())

    async def scenario() -> None:
        heartbeat_ran = False

        async def heartbeat() -> None:
            nonlocal heartbeat_ran
            await asyncio.sleep(0)
            heartbeat_ran = True

        heartbeat_task = asyncio.create_task(heartbeat())
        with pytest.raises(MinerUError) as caught:
            await client._extract_markdown_isolated(b"archive", time.monotonic() + 0.01)
        await heartbeat_task
        assert caught.value.code == "timeout"
        assert heartbeat_ran is True

    _run(scenario())
    assert process.terminated is True
    assert process.joined is True


def test_pinned_transport_connects_to_validated_ip_with_original_host_and_tls_sni() -> None:
    class RecordingStream:
        def __init__(self) -> None:
            self.writes = bytearray()
            self.read_once = False
            self.server_hostname: str | None = None
            self.ssl_context: ssl.SSLContext | None = None

        async def read(self, max_bytes: int, timeout: float | None = None) -> bytes:
            if self.read_once:
                return b""
            self.read_once = True
            return b"HTTP/1.1 200 OK\r\nContent-Length: 2\r\nConnection: close\r\n\r\nOK"

        async def write(self, buffer: bytes, timeout: float | None = None) -> None:
            self.writes.extend(buffer)

        async def aclose(self) -> None:
            pass

        async def start_tls(
            self,
            ssl_context: ssl.SSLContext,
            server_hostname: str | None = None,
            timeout: float | None = None,
        ):
            self.ssl_context = ssl_context
            self.server_hostname = server_hostname
            return self

        def get_extra_info(self, info: str):
            return None

    class RecordingBackend:
        def __init__(self) -> None:
            self.connected_host: str | None = None
            self.stream = RecordingStream()

        async def connect_tcp(self, host: str, port: int, **_kwargs):
            self.connected_host = host
            assert port == 443
            return self.stream

        async def connect_unix_socket(self, *_args, **_kwargs):
            raise AssertionError("unix sockets are not used")

        async def sleep(self, seconds: float) -> None:
            await asyncio.sleep(seconds)

    async def scenario() -> None:
        backend = RecordingBackend()
        transport = _PinnedAsyncTransport(network_backend=backend)
        transport.pin("objects.example", PUBLIC_IP)
        async with httpx.AsyncClient(transport=transport) as client:
            response = await client.get("https://objects.example/result")

        assert response.text == "OK"
        assert backend.connected_host == PUBLIC_IP
        assert backend.stream.server_hostname == "objects.example"
        assert backend.stream.ssl_context is not None
        assert backend.stream.ssl_context.check_hostname is True
        assert backend.stream.ssl_context.verify_mode == ssl.CERT_REQUIRED
        assert b"Host: objects.example" in backend.stream.writes

    _run(scenario())


def test_archive_worker_receives_zip_path_instead_of_archive_bytes(tmp_path: Path) -> None:
    archive = tmp_path / "result.zip"
    archive.write_bytes(_markdown_zip("markdown"))
    captured_args: tuple | None = None

    class InlineConnection:
        mailbox: list[tuple[str, str]] = []

        def send(self, value):
            self.mailbox.append(value)

        def poll(self):
            return bool(self.mailbox)

        def recv(self):
            return self.mailbox.pop(0)

        def close(self):
            pass

    class InlineProcess:
        def __init__(self, target, args) -> None:
            nonlocal captured_args
            self.target = target
            self.args = args
            captured_args = args

        def start(self):
            self.target(*self.args)

        def is_alive(self):
            return False

        def terminate(self):
            pass

        def kill(self):
            pass

        def join(self, timeout=None):
            pass

    class InlineContext:
        def Pipe(self, duplex=False):
            connection = InlineConnection()
            connection.mailbox = []
            return connection, connection

        def Process(self, *, target, args, daemon):
            return InlineProcess(target, args)

    async def unused_handler(_request: httpx.Request) -> httpx.Response:
        raise AssertionError("HTTP is not used")

    client = _client(unused_handler, process_context=InlineContext())
    result = _run(client._extract_markdown_isolated(archive, time.monotonic() + 1))

    assert result == "markdown"
    assert captured_args is not None
    assert captured_args[1] == str(archive)
    assert isinstance(captured_args[1], str)


def test_mineru_stop_process_control_method_failures_are_bounded() -> None:
    class BrokenProcess:
        def is_alive(self):
            raise OSError("sensitive")

        def terminate(self):
            raise OSError("sensitive")

        def kill(self):
            raise OSError("sensitive")

        def join(self, timeout=None):
            raise OSError("sensitive")

    started = time.monotonic()
    _run(MinerUClient._stop_process(BrokenProcess()))
    assert time.monotonic() - started < 1


def test_mineru_stop_process_finishes_kill_and_join_before_propagating_cancellation() -> None:
    class StubbornProcess:
        killed = False
        joined = False

        def is_alive(self):
            return not self.killed

        def terminate(self):
            pass

        def kill(self):
            self.killed = True

        def join(self, timeout=None):
            self.joined = True

    async def scenario() -> None:
        process = StubbornProcess()
        task = asyncio.create_task(MinerUClient._stop_process(process))
        await asyncio.sleep(0)
        task.cancel()

        with pytest.raises(asyncio.CancelledError):
            await task

        assert process.killed is True
        assert process.joined is True

    _run(scenario())


def test_archive_worker_pipe_failure_is_sanitized_and_bounded(tmp_path: Path) -> None:
    archive = tmp_path / "result.zip"
    archive.write_bytes(_markdown_zip("markdown"))

    class PipeFailureContext:
        def Pipe(self, duplex=False):
            raise OSError("sensitive IPC detail")

    async def unused_handler(_request: httpx.Request) -> httpx.Response:
        raise AssertionError("HTTP is not used")

    client = _client(unused_handler, process_context=PipeFailureContext())
    with pytest.raises(MinerUError) as caught:
        _run(client._extract_markdown_isolated(archive, time.monotonic() + 1))

    assert caught.value.code == "invalid_archive"
    assert "sensitive" not in str(caught.value)


def _write_late_mineru_marker(path: str) -> None:
    time.sleep(0.4)
    Path(path).write_text("late", encoding="utf-8")


@pytest.mark.skipif(sys.platform != "win32", reason="Windows spawn process regression")
def test_mineru_real_windows_spawn_process_has_no_late_side_effect_or_orphan(tmp_path: Path) -> None:
    marker = tmp_path / "late-mineru.txt"
    process = multiprocessing.get_context("spawn").Process(
        target=_write_late_mineru_marker,
        args=(str(marker),),
    )
    process.start()

    _run(MinerUClient._stop_process(process))
    time.sleep(0.6)

    assert process.exitcode is not None
    assert process.is_alive() is False
    assert not marker.exists()


def test_archive_worker_start_failure_is_mapped_and_resources_closed() -> None:
    class FakeConnection:
        closed = False

        def close(self) -> None:
            self.closed = True

    receiver = FakeConnection()
    sender = FakeConnection()

    class FakeProcess:
        def start(self) -> None:
            raise OSError("sensitive process details")

        def is_alive(self) -> bool:
            raise AssertionError("must not inspect a process that did not start")

    class FakeContext:
        def Pipe(self, duplex: bool = False):
            return receiver, sender

        def Process(self, **_kwargs):
            return FakeProcess()

    async def unused_handler(_request: httpx.Request) -> httpx.Response:
        raise AssertionError("HTTP is not used")

    client = _client(unused_handler, process_context=FakeContext())
    with pytest.raises(MinerUError) as caught:
        _run(client._extract_markdown_isolated(b"archive", time.monotonic() + 1))

    assert caught.value.code == "invalid_archive"
    assert "sensitive" not in str(caught.value)
    assert receiver.closed is True
    assert sender.closed is True


def test_archive_process_construction_failure_cleans_all_resources_and_temp_file(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeConnection:
        closed = False

        def close(self) -> None:
            self.closed = True

    receiver = FakeConnection()
    sender = FakeConnection()
    created_path: Path | None = None

    class FakeContext:
        def Pipe(self, duplex: bool = False):
            return receiver, sender

        def Process(self, **_kwargs):
            raise OSError("sensitive process construction detail")

    real_mkstemp = __import__("tempfile").mkstemp

    def recording_mkstemp(*args, **kwargs):
        nonlocal created_path
        descriptor, path = real_mkstemp(*args, **kwargs)
        created_path = Path(path)
        return descriptor, path

    monkeypatch.setattr("app.lib.private_temp.tempfile.mkstemp", recording_mkstemp)

    async def unused_handler(_request: httpx.Request) -> httpx.Response:
        raise AssertionError("HTTP is not used")

    client = _client(unused_handler, process_context=FakeContext())
    with pytest.raises(MinerUError) as caught:
        _run(client._extract_markdown_isolated(b"archive", time.monotonic() + 1))

    assert caught.value.code == "invalid_archive"
    assert "sensitive" not in str(caught.value)
    assert receiver.closed is True
    assert sender.closed is True
    assert created_path is not None
    assert not created_path.exists()


def test_missing_file_has_stable_file_read_error(tmp_path: Path) -> None:
    missing = tmp_path / "missing.pdf"

    async def handler(_request: httpx.Request) -> httpx.Response:
        return _json_response({"code": 0, "data": {"batch_id": "batch-1", "file_urls": [UPLOAD_URL]}})

    with pytest.raises(MinerUError) as caught:
        _run(_client(handler).parse_pdf_async(str(missing)))

    assert caught.value.code == "file_read"
    assert str(missing) not in str(caught.value)


def test_configuration_defaults_and_constraints() -> None:
    from app.core.config import DEFAULT_MINERU_TRUSTED_HOSTS

    configured = Settings(_env_file=None)

    assert configured.mineru_request_timeout_seconds == 60
    assert configured.mineru_poll_interval_seconds == 3
    assert configured.mineru_total_timeout_seconds == 600
    assert configured.mineru_max_zip_bytes > 0
    assert configured.mineru_max_zip_members > 0
    assert configured.mineru_max_compression_ratio > 1
    assert configured.mineru_max_markdown_bytes > 0
    assert configured.mineru_max_json_bytes > 0
    assert configured.mineru_trusted_hosts == DEFAULT_MINERU_TRUSTED_HOSTS == ""
    with pytest.raises(ValidationError):
        Settings(_env_file=None, mineru_request_timeout_seconds=0)
    with pytest.raises(ValidationError):
        Settings(_env_file=None, mineru_total_timeout_seconds=-1)
    with pytest.raises(ValidationError):
        Settings(_env_file=None, mineru_max_zip_members=0)
    with pytest.raises(ValidationError):
        Settings(_env_file=None, mineru_max_json_bytes=0)
    with pytest.raises(ValidationError):
        Settings(_env_file=None, mineru_trusted_hosts="https://objects.example/path")


def test_production_configuration_rejects_whitespace_mineru_token() -> None:
    configured = Settings(
        _env_file=None,
        environment="production",
        jwt_secret_key="production-jwt-secret",
        api_key_encryption_secret="production-encryption-secret",
        data_encryption_key="production-data-key",
        model_api_key="production-model-key",
        model_base_url="https://api.deepseek.com/v1",
        model_name="deepseek-v4-pro",
        mineru_api_token="   ",
        database_url="postgresql+asyncpg://postgres:safe@localhost/goulong",
    )
    from app.core import config

    original = config.settings
    config.settings = configured
    try:
        with pytest.raises(RuntimeError, match="MINERU_API_TOKEN"):
            assert_production_security()
    finally:
        config.settings = original


def test_production_configuration_requires_trusted_hosts() -> None:
    configured = Settings(
        _env_file=None,
        environment="production",
        jwt_secret_key="production-jwt-secret",
        api_key_encryption_secret="production-encryption-secret",
        data_encryption_key="production-data-key",
        model_api_key="production-model-key",
        model_base_url="https://api.deepseek.com/v1",
        model_name="deepseek-v4-pro",
        mineru_api_token="production-mineru-token",
        mineru_trusted_hosts="  ",
        database_url="postgresql+asyncpg://postgres:safe@localhost/goulong",
    )
    from app.core import config

    original = config.settings
    config.settings = configured
    try:
        with pytest.raises(RuntimeError, match="MINERU_TRUSTED_HOSTS"):
            assert_production_security()
    finally:
        config.settings = original
