from __future__ import annotations

import asyncio
import io
import ipaddress
import json
import logging
import multiprocessing
import socket
import ssl
import time
import uuid
import zipfile
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import httpx
import httpcore

from app.core.config import settings
from app.lib.private_temp import (
    FileIdentity,
    create_private_temp_file,
    secure_unlink,
    snapshot_file_identity,
    validate_file_identity,
)

logger = logging.getLogger(__name__)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

BATCH_UPLOAD_URL = "https://mineru.net/api/v4/file-urls/batch"
BATCH_RESULT_URL = "https://mineru.net/api/v4/extract-results/batch/{batch_id}"
FILE_CHUNK_SIZE = 64 * 1024
PROCESS_POLL_INTERVAL_SECONDS = 0.01
PROCESS_TERMINATE_GRACE_SECONDS = 0.2
PROCESS_KILL_GRACE_SECONDS = 0.2

Resolver = Callable[[str, int], Awaitable[list[tuple]]]
TaskCreatedCallback = Callable[[str, str], Awaitable[None]]


class _PinnedNetworkBackend(httpcore.AsyncNetworkBackend):
    """Resolve only through validated mappings while preserving the HTTP origin."""

    def __init__(self, backend: httpcore.AsyncNetworkBackend | None = None) -> None:
        if backend is None:
            from httpcore._backends.auto import AutoBackend

            backend = AutoBackend()
        self._backend = backend
        self._pinned: dict[str, str] = {}

    def pin(self, hostname: str, address: str) -> None:
        parsed = ipaddress.ip_address(address)
        if not parsed.is_global:
            raise ValueError("address must be public")
        self._pinned[hostname.rstrip(".").lower()] = str(parsed)

    async def connect_tcp(
        self,
        host: str,
        port: int,
        timeout: float | None = None,
        local_address: str | None = None,
        socket_options: Any = None,
    ) -> Any:
        address = self._pinned.get(host.rstrip(".").lower())
        if address is None:
            raise httpcore.ConnectError("network destination was not pinned")
        return await self._backend.connect_tcp(
            address,
            port,
            timeout=timeout,
            local_address=local_address,
            socket_options=socket_options,
        )

    async def connect_unix_socket(self, *args: Any, **kwargs: Any) -> Any:
        raise httpcore.ConnectError("unix sockets are disabled")

    async def sleep(self, seconds: float) -> None:
        await self._backend.sleep(seconds)


class _PinnedAsyncTransport(httpx.AsyncHTTPTransport):
    """HTTPX/httpcore transport whose TCP destination is an already validated IP."""

    def __init__(self, *, network_backend: httpcore.AsyncNetworkBackend | None = None) -> None:
        self._network_backend = _PinnedNetworkBackend(network_backend)
        self._pool = httpcore.AsyncConnectionPool(
            ssl_context=ssl.create_default_context(),
            network_backend=self._network_backend,
            retries=0,
        )

    def pin(self, hostname: str, address: str) -> None:
        self._network_backend.pin(hostname, address)


class MinerUError(Exception):
    """带稳定错误码且不包含上游敏感内容的 MinerU 异常。"""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)


@dataclass(frozen=True)
class MinerUResult:
    task_id: str
    batch_id: str
    markdown: str


@dataclass(frozen=True)
class _BufferedResponse:
    status_code: int
    body: bytes


def _extract_markdown_bytes(
    archive_bytes: bytes,
    max_zip_members: int,
    max_compression_ratio: float,
    max_markdown_bytes: int,
) -> bytes:
    try:
        with zipfile.ZipFile(io.BytesIO(archive_bytes)) as archive:
            members = archive.infolist()
            if len(members) > max_zip_members:
                raise MinerUError("invalid_archive", "MinerU archive exceeds safety limits")
            for member in members:
                compressed_size = max(member.compress_size, 1)
                if member.file_size / compressed_size > max_compression_ratio:
                    raise MinerUError("invalid_archive", "MinerU archive exceeds safety limits")
            markdown_members = [
                member
                for member in members
                if member.filename.endswith("full.md") or member.filename.endswith(".md")
            ]
            if not markdown_members:
                raise MinerUError("invalid_archive", "MinerU archive contains no Markdown")
            markdown_member = markdown_members[0]
            if markdown_member.file_size > max_markdown_bytes:
                raise MinerUError("invalid_archive", "MinerU Markdown exceeds safety limits")
            with archive.open(markdown_member) as markdown_file:
                markdown = markdown_file.read(max_markdown_bytes + 1)
            if len(markdown) > max_markdown_bytes:
                raise MinerUError("invalid_archive", "MinerU Markdown exceeds safety limits")
            markdown.decode("utf-8")
            return markdown
    except MinerUError:
        raise
    except (OSError, RuntimeError, UnicodeDecodeError, zipfile.BadZipFile, zipfile.LargeZipFile):
        raise MinerUError("invalid_archive", "MinerU archive is invalid") from None


def _extract_markdown_path(
    archive_path: str,
    max_zip_members: int,
    max_compression_ratio: float,
    max_markdown_bytes: int,
) -> bytes:
    try:
        with zipfile.ZipFile(archive_path) as archive:
            members = archive.infolist()
            if len(members) > max_zip_members:
                raise MinerUError("invalid_archive", "MinerU archive exceeds safety limits")
            for member in members:
                compressed_size = max(member.compress_size, 1)
                if member.file_size / compressed_size > max_compression_ratio:
                    raise MinerUError("invalid_archive", "MinerU archive exceeds safety limits")
            markdown_members = [
                member for member in members if member.filename.endswith("full.md") or member.filename.endswith(".md")
            ]
            if not markdown_members:
                raise MinerUError("invalid_archive", "MinerU archive contains no Markdown")
            markdown_member = markdown_members[0]
            if markdown_member.file_size > max_markdown_bytes:
                raise MinerUError("invalid_archive", "MinerU Markdown exceeds safety limits")
            with archive.open(markdown_member) as markdown_file:
                markdown = markdown_file.read(max_markdown_bytes + 1)
            if len(markdown) > max_markdown_bytes:
                raise MinerUError("invalid_archive", "MinerU Markdown exceeds safety limits")
            markdown.decode("utf-8")
            return markdown
    except MinerUError:
        raise
    except (OSError, RuntimeError, UnicodeDecodeError, zipfile.BadZipFile, zipfile.LargeZipFile, NotImplementedError):
        raise MinerUError("invalid_archive", "MinerU archive is invalid") from None


def _archive_worker(
    sender: Any,
    archive_path: str,
    max_zip_members: int,
    max_compression_ratio: float,
    max_markdown_bytes: int,
    output_path: str,
) -> None:
    try:
        markdown = _extract_markdown_path(
            archive_path,
            max_zip_members,
            max_compression_ratio,
            max_markdown_bytes,
        )
        with open(output_path, "wb") as output:
            output.write(markdown)
        sender.send(("ok", ""))
    except MinerUError as error:
        sender.send(("error", error.code))
    except Exception:
        sender.send(("error", "invalid_archive"))
    finally:
        _safe_close(sender)


async def _wait_for_process_exit(process: Any, timeout_seconds: float) -> None:
    end = asyncio.get_running_loop().time() + timeout_seconds
    while asyncio.get_running_loop().time() < end:
        if not _safe_is_alive(process, default=True):
            return
        await asyncio.sleep(PROCESS_POLL_INTERVAL_SECONDS)


def _safe_is_alive(process: Any, *, default: bool) -> bool:
    try:
        return bool(process.is_alive())
    except Exception:
        logger.warning("MinerU archive worker state check failed")
        return default


def _safe_process_call(process: Any, method: str, **kwargs: Any) -> None:
    try:
        getattr(process, method)(**kwargs)
    except Exception:
        logger.warning("MinerU archive worker control failed operation=%s", method)


def _safe_close(resource: Any) -> None:
    try:
        resource.close()
    except Exception:
        logger.warning("MinerU IPC cleanup failed")


class MinerUClient:
    """原生异步 MinerU API v4 客户端。"""

    def __init__(
        self,
        api_token: str | None = None,
        model_version: str | None = None,
        enable_ocr: bool | None = None,
        language: str | None = None,
        request_timeout_seconds: float | None = None,
        poll_interval_seconds: float | None = None,
        total_timeout_seconds: float | None = None,
        max_zip_bytes: int | None = None,
        max_zip_members: int | None = None,
        max_compression_ratio: float | None = None,
        max_markdown_bytes: int | None = None,
        max_json_bytes: int | None = None,
        trusted_hosts: str | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
        resolver: Resolver | None = None,
        clock: Callable[[], float] = time.monotonic,
        process_context: Any | None = None,
    ) -> None:
        token = api_token if api_token is not None else settings.mineru_api_token
        self.api_token = token.strip()
        self.model_version = model_version or settings.mineru_model_version
        self.enable_ocr = enable_ocr if enable_ocr is not None else settings.mineru_enable_ocr
        self.language = language or settings.mineru_language
        self.request_timeout_seconds = self._setting(
            request_timeout_seconds, settings.mineru_request_timeout_seconds
        )
        self.poll_interval_seconds = self._setting(
            poll_interval_seconds, settings.mineru_poll_interval_seconds
        )
        self.total_timeout_seconds = self._setting(
            total_timeout_seconds, settings.mineru_total_timeout_seconds
        )
        self.max_zip_bytes = self._setting(max_zip_bytes, settings.mineru_max_zip_bytes)
        self.max_zip_members = self._setting(max_zip_members, settings.mineru_max_zip_members)
        self.max_compression_ratio = self._setting(
            max_compression_ratio, settings.mineru_max_compression_ratio
        )
        self.max_markdown_bytes = self._setting(
            max_markdown_bytes, settings.mineru_max_markdown_bytes
        )
        self.max_json_bytes = self._setting(max_json_bytes, settings.mineru_max_json_bytes)
        trusted_value = trusted_hosts if trusted_hosts is not None else settings.mineru_trusted_hosts
        self.trusted_hosts = tuple(item.strip().lower() for item in trusted_value.split(",") if item.strip())
        self._transport = transport
        self._resolver = resolver or self._resolve_host
        self._clock = clock
        self._process_context = process_context or multiprocessing.get_context("spawn")
        if not self.api_token:
            raise MinerUError("apply", "MinerU token is not configured")

    @staticmethod
    def _setting(override: Any, default: Any) -> Any:
        return default if override is None else override

    @property
    def _headers(self) -> dict[str, str]:
        return {
            "Accept-Encoding": "identity",
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_token}",
        }

    async def parse_pdf_async(
        self,
        file_path: str,
        *,
        existing_task_id: str | None = None,
        on_task_created: TaskCreatedCallback | None = None,
    ) -> MinerUResult:
        deadline = self._clock() + self.total_timeout_seconds
        self._validate_readable_file(file_path)
        transport = self._transport
        pinned_transport: _PinnedAsyncTransport | None = None
        if transport is None:
            pinned_transport = _PinnedAsyncTransport()
            transport = pinned_transport
            await self._pin_fixed_api_host(pinned_transport, deadline)
        async with httpx.AsyncClient(
            transport=transport,
            follow_redirects=False,
            trust_env=False,
        ) as client:
            if existing_task_id is None:
                batch_id, upload_url = await self._apply_upload(client, file_path, deadline)
                if on_task_created is not None:
                    await on_task_created(batch_id, "pending")
                await self._validate_external_url(upload_url, "apply", deadline, pinned_transport)
                logger.info("MinerU upload started")
                await self._put_file(client, file_path, upload_url, deadline)
                if on_task_created is not None:
                    await on_task_created(batch_id, "uploaded")
            else:
                batch_id = existing_task_id
            zip_url = await self._poll_batch(client, batch_id, deadline)
            await self._validate_external_url(zip_url, "download", deadline, pinned_transport)
            markdown = await self._download_markdown(client, zip_url, deadline)
        return MinerUResult(task_id=batch_id, batch_id=batch_id, markdown=markdown)

    async def _apply_upload(
        self,
        client: httpx.AsyncClient,
        file_path: str,
        deadline: float,
    ) -> tuple[str, str]:
        payload = {
            "files": [
                {
                    "name": Path(file_path).name,
                    "data_id": f"doc_{uuid.uuid4().hex[:16]}",
                    "is_ocr": self.enable_ocr,
                }
            ],
            "model_version": self.model_version,
            "enable_formula": True,
            "enable_table": True,
            "language": self.language,
        }
        response = await self._request_limited(
            client,
            "POST",
            BATCH_UPLOAD_URL,
            deadline,
            "apply",
            self.max_json_bytes,
            headers=self._headers,
            json=payload,
        )
        body = self._decode_json(response.body, "apply")
        if response.status_code != 200 or body.get("code") != 0:
            raise MinerUError("apply", "MinerU upload application failed")
        data = body.get("data")
        if not isinstance(data, dict):
            raise MinerUError("apply", "MinerU upload application returned invalid data")
        batch_id = data.get("batch_id")
        urls = data.get("file_urls")
        if not isinstance(batch_id, str) or not isinstance(urls, list) or not urls or not isinstance(urls[0], str):
            raise MinerUError("apply", "MinerU upload application returned invalid data")
        return batch_id, urls[0]

    async def _put_file(
        self,
        client: httpx.AsyncClient,
        file_path: str,
        upload_url: str,
        deadline: float,
    ) -> None:
        response = await self._request_limited(
            client,
            "PUT",
            upload_url,
            deadline,
            "upload",
            self.max_json_bytes,
            headers={"Accept-Encoding": "identity"},
            content=self._file_chunks(file_path),
        )
        if response.status_code not in (200, 201):
            raise MinerUError("upload", "MinerU file upload failed")

    async def _poll_batch(
        self,
        client: httpx.AsyncClient,
        batch_id: str,
        deadline: float,
    ) -> str:
        url = BATCH_RESULT_URL.format(batch_id=batch_id)
        while True:
            response = await self._request_limited(
                client,
                "GET",
                url,
                deadline,
                "poll",
                self.max_json_bytes,
                headers=self._headers,
            )
            body = self._decode_json(response.body, "poll")
            if response.status_code != 200 or body.get("code") != 0:
                raise MinerUError("poll", "MinerU polling failed")
            data = body.get("data")
            results = data.get("extract_result", []) if isinstance(data, dict) else []
            if results:
                result = results[0]
                if not isinstance(result, dict):
                    raise MinerUError("poll", "MinerU polling returned invalid data")
                state = result.get("state")
                if state == "failed":
                    raise MinerUError("upstream_failed", "MinerU extraction failed")
                if state == "done":
                    zip_url = result.get("full_zip_url")
                    if not isinstance(zip_url, str) or not zip_url:
                        raise MinerUError("download", "MinerU result has no download archive")
                    return zip_url
                self._log_progress(result)
            remaining = self._remaining(deadline)
            await asyncio.sleep(min(self.poll_interval_seconds, remaining))

    async def _download_markdown(
        self,
        client: httpx.AsyncClient,
        zip_url: str,
        deadline: float,
    ) -> str:
        archive_path = create_private_temp_file(prefix="mineru-archive-", suffix=".zip")
        archive_identity = snapshot_file_identity(archive_path)
        downloaded = 0
        timeout = self._request_timeout(deadline)
        try:
            with open(archive_path, "wb") as archive:
                async with client.stream(
                    "GET",
                    zip_url,
                    timeout=timeout,
                    headers={"Accept-Encoding": "identity"},
                ) as response:
                    self._ensure_identity_encoding(response.headers, "download")
                    self._ensure_deadline(deadline)
                    if response.status_code != 200:
                        raise MinerUError("download", "MinerU archive download failed")
                    async for chunk in response.aiter_raw():
                        downloaded += len(chunk)
                        if downloaded > self.max_zip_bytes:
                            raise MinerUError("invalid_archive", "MinerU archive exceeds safety limits")
                        archive.write(chunk)
                        self._ensure_deadline(deadline)
            if not validate_file_identity(archive_path, archive_identity):
                raise MinerUError("invalid_archive", "MinerU archive is invalid")
            return await self._extract_markdown_isolated(archive_path, deadline)
        except MinerUError:
            raise
        except httpx.TimeoutException:
            raise MinerUError("timeout", "MinerU processing timed out") from None
        except httpx.HTTPError:
            raise MinerUError("download", "MinerU archive download failed") from None
        except OSError:
            raise MinerUError("download", "MinerU archive download failed") from None
        finally:
            secure_unlink(archive_path, identity=archive_identity)

    async def _extract_markdown_isolated(self, archive: Path | bytes, deadline: float) -> str:
        receiver: Any | None = None
        sender: Any | None = None
        output_path: Path | None = None
        output_identity: FileIdentity | None = None
        owned_archive_path: Path | None = None
        archive_path: Path
        process: Any | None = None
        process_started = False
        try:
            receiver, sender = self._process_context.Pipe(duplex=False)
            if isinstance(archive, bytes):
                owned_archive_path = create_private_temp_file(prefix="mineru-archive-", suffix=".zip")
                owned_archive_path.write_bytes(archive)
                archive_path = owned_archive_path
            else:
                archive_path = archive
            output_path = create_private_temp_file(prefix="mineru-", suffix=".md")
            output_identity = snapshot_file_identity(output_path)
            process = self._process_context.Process(
                target=_archive_worker,
                args=(
                    sender,
                    str(archive_path),
                    self.max_zip_members,
                    self.max_compression_ratio,
                    self.max_markdown_bytes,
                    str(output_path),
                ),
                daemon=True,
            )
            process.start()
            process_started = True
            _safe_close(sender)
            while True:
                if receiver.poll():
                    status, code = receiver.recv()
                    if status != "ok":
                        raise MinerUError(code or "invalid_archive", "MinerU archive is invalid")
                    if not validate_file_identity(output_path, output_identity):
                        raise MinerUError("invalid_archive", "MinerU archive output is invalid")
                    return await self._read_markdown_output(str(output_path), deadline)
                if not _safe_is_alive(process, default=True):
                    raise MinerUError("invalid_archive", "MinerU archive worker failed")
                remaining = self._remaining(deadline)
                await asyncio.sleep(min(PROCESS_POLL_INTERVAL_SECONDS, remaining))
        except MinerUError:
            raise
        except (EOFError, OSError, ValueError):
            raise MinerUError("invalid_archive", "MinerU archive worker failed") from None
        finally:
            try:
                if process_started and process is not None:
                    await self._stop_process(process)
            finally:
                if receiver is not None:
                    _safe_close(receiver)
                if sender is not None:
                    _safe_close(sender)
                if output_path is not None:
                    secure_unlink(output_path, identity=output_identity)
                if owned_archive_path is not None:
                    secure_unlink(owned_archive_path)

    async def _read_markdown_output(self, output_path: str, deadline: float) -> str:
        content = bytearray()
        try:
            with open(output_path, "rb") as output:
                while chunk := output.read(FILE_CHUNK_SIZE):
                    content.extend(chunk)
                    if len(content) > self.max_markdown_bytes:
                        raise MinerUError("invalid_archive", "MinerU Markdown exceeds safety limits")
                    self._ensure_deadline(deadline)
                    await asyncio.sleep(0)
            return bytes(content).decode("utf-8")
        except MinerUError:
            raise
        except (OSError, UnicodeDecodeError):
            raise MinerUError("invalid_archive", "MinerU archive output is invalid") from None

    @staticmethod
    async def _stop_process(process: Any) -> None:
        cancellation: asyncio.CancelledError | None = None
        if _safe_is_alive(process, default=True):
            _safe_process_call(process, "terminate")
        try:
            await _wait_for_process_exit(process, PROCESS_TERMINATE_GRACE_SECONDS)
        except asyncio.CancelledError as error:
            cancellation = error
        if _safe_is_alive(process, default=True):
            _safe_process_call(process, "kill")
        try:
            await _wait_for_process_exit(process, PROCESS_KILL_GRACE_SECONDS)
        except asyncio.CancelledError as error:
            cancellation = error
        _safe_process_call(process, "join", timeout=0.1)
        if _safe_is_alive(process, default=False):
            logger.error("MinerU archive worker could not be stopped")
        if cancellation is not None:
            raise cancellation

    def _extract_markdown(self, archive_bytes: bytes) -> str:
        return _extract_markdown_bytes(
            archive_bytes,
            self.max_zip_members,
            self.max_compression_ratio,
            self.max_markdown_bytes,
        ).decode("utf-8")

    async def _request_limited(
        self,
        client: httpx.AsyncClient,
        method: str,
        url: str,
        deadline: float,
        error_code: str,
        max_body_bytes: int,
        **kwargs: Any,
    ) -> _BufferedResponse:
        timeout = self._request_timeout(deadline)
        body = bytearray()
        try:
            async with client.stream(method, url, timeout=timeout, **kwargs) as response:
                self._ensure_identity_encoding(response.headers, error_code)
                async for chunk in response.aiter_raw():
                    body.extend(chunk)
                    if len(body) > max_body_bytes:
                        raise MinerUError(error_code, "MinerU response exceeds safety limits")
                    self._ensure_deadline(deadline)
                return _BufferedResponse(response.status_code, bytes(body))
        except MinerUError:
            raise
        except httpx.TimeoutException:
            raise MinerUError("timeout", "MinerU processing timed out") from None
        except httpx.HTTPError:
            raise MinerUError(error_code, f"MinerU {error_code} request failed") from None

    async def _validate_external_url(
        self,
        url: str,
        error_code: str,
        deadline: float,
        pinned_transport: _PinnedAsyncTransport | None = None,
    ) -> None:
        try:
            parsed = urlsplit(url)
            host = parsed.hostname.lower() if parsed.hostname else ""
            if (
                parsed.scheme != "https"
                or not host
                or (parsed.port is not None and parsed.port != 443)
                or parsed.username is not None
                or parsed.password is not None
                or not self._is_trusted_host(host)
            ):
                raise ValueError
            first_addresses = await self._resolve_public_addresses(host, parsed.port or 443, deadline)
            await asyncio.sleep(0)
            second_addresses = await self._resolve_public_addresses(host, parsed.port or 443, deadline)
            if first_addresses != second_addresses:
                raise ValueError
            if pinned_transport is not None:
                pinned_transport.pin(host, sorted(first_addresses)[0])
            self._ensure_deadline(deadline)
        except MinerUError:
            raise
        except TimeoutError:
            raise MinerUError("timeout", "MinerU processing timed out") from None
        except (OSError, ValueError, IndexError, TypeError):
            raise MinerUError(error_code, "MinerU returned an unsafe URL") from None

    async def _pin_fixed_api_host(self, transport: _PinnedAsyncTransport, deadline: float) -> None:
        host = urlsplit(BATCH_UPLOAD_URL).hostname
        if not host:
            raise MinerUError("apply", "MinerU API URL is invalid")
        try:
            addresses = await self._resolve_public_addresses(host, 443, deadline)
            transport.pin(host, sorted(addresses)[0])
        except (OSError, ValueError, TimeoutError):
            raise MinerUError("apply", "MinerU API host is unsafe") from None

    async def _resolve_public_addresses(self, host: str, port: int, deadline: float) -> frozenset[str]:
        try:
            literal = ipaddress.ip_address(host)
            addresses = [literal]
        except ValueError:
            remaining = self._remaining(deadline)
            async with asyncio.timeout(remaining):
                resolved = await self._resolver(host, port)
            addresses = [ipaddress.ip_address(item[4][0]) for item in resolved]
        if not addresses or any(not address.is_global for address in addresses):
            raise ValueError
        return frozenset(str(address) for address in addresses)

    def _is_trusted_host(self, host: str) -> bool:
        for trusted in self.trusted_hosts:
            if trusted.startswith("."):
                if host.endswith(trusted) and host != trusted[1:]:
                    return True
            elif host == trusted:
                return True
        return False

    async def _resolve_host(self, host: str, port: int) -> list[tuple]:
        loop = asyncio.get_running_loop()
        return await loop.getaddrinfo(host, port, type=socket.SOCK_STREAM)

    async def _file_chunks(self, file_path: str) -> AsyncIterator[bytes]:
        try:
            with open(file_path, "rb") as file:
                while chunk := file.read(FILE_CHUNK_SIZE):
                    yield chunk
                    await asyncio.sleep(0)
        except OSError:
            raise MinerUError("file_read", "Unable to read input file") from None

    @staticmethod
    def _decode_json(body: bytes, error_code: str) -> dict[str, Any]:
        try:
            decoded = json.loads(body)
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise MinerUError(error_code, "MinerU returned invalid data") from None
        if not isinstance(decoded, dict):
            raise MinerUError(error_code, "MinerU returned invalid data")
        return decoded

    @staticmethod
    def _ensure_identity_encoding(headers: httpx.Headers, error_code: str) -> None:
        content_encoding = headers.get("Content-Encoding", "identity").strip().lower()
        if content_encoding != "identity":
            raise MinerUError(error_code, "MinerU returned unsupported content encoding")

    @staticmethod
    def _validate_readable_file(file_path: str) -> None:
        try:
            with open(file_path, "rb"):
                pass
        except OSError:
            raise MinerUError("file_read", "Unable to read input file") from None

    def _request_timeout(self, deadline: float) -> float:
        return min(self.request_timeout_seconds, self._remaining(deadline))

    def _remaining(self, deadline: float) -> float:
        remaining = deadline - self._clock()
        if remaining <= 0:
            raise MinerUError("timeout", "MinerU processing timed out")
        return remaining

    def _ensure_deadline(self, deadline: float) -> None:
        self._remaining(deadline)

    @staticmethod
    def _log_progress(result: dict[str, Any]) -> None:
        progress = result.get("extract_progress")
        if not isinstance(progress, dict):
            progress = {}
        extracted_pages = progress.get("extracted_pages")
        total_pages = progress.get("total_pages")
        logger.info(
            "MinerU extraction in progress pages=%s/%s",
            extracted_pages if isinstance(extracted_pages, int) else "?",
            total_pages if isinstance(total_pages, int) else "?",
        )


async def parse_pdf_to_markdown(file_path: str) -> str:
    result = await MinerUClient().parse_pdf_async(file_path)
    return result.markdown
