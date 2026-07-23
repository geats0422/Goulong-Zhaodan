"""文件存储抽象层（本地 / 阿里云 OSS 双模式自动切换）。

storage_path 始终使用后端无关的相对路径（如 "traditional/房建/招标文件/v1/file.pdf"），
数据库只存相对路径。实际落位由后端决定：
- OSS 模式（oss_bucket_name + oss_endpoint 已配置）：相对路径前加 oss_prefix 作为 OSS key。
- 本地模式（默认）：相对路径拼接到 STORAGE_ROOT 之下。
"""

from __future__ import annotations

import asyncio
import codecs
import hashlib
import inspect
import os
import re
import stat
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath, PureWindowsPath

from app.lib.private_temp import FileIdentity, create_private_temp_file, secure_unlink, snapshot_file_identity

STORAGE_ROOT = "data/knowledge"
_DEFAULT_STORAGE_ROOT = STORAGE_ROOT
_OLE_SIGNATURE = bytes.fromhex("D0CF11E0A1B11AE1")
_OOXML_ROOTS = {"docx": "word/", "pptx": "ppt/", "xlsx": "xl/"}


async def _await_stream_close(result):
    await result


class StoredFileValidationError(ValueError):
    """Stable validation failure for a stored source document."""


class FileStorageError(RuntimeError):
    """Stable storage failure that is safe to expose through application APIs."""


@dataclass(frozen=True, slots=True)
class PrivateStoredFile:
    path: Path
    content_hash: str
    size: int
    identity: FileIdentity


def is_oss_enabled() -> bool:
    """Only use OSS when it was explicitly selected and fully configured."""
    from app.core.config import settings

    return bool(
        settings.storage_backend == "oss"
        and settings.oss_access_key_id
        and settings.oss_access_key_secret
        and settings.oss_bucket_name
        and settings.oss_endpoint
    )


def safe_path_segment(value: str, fallback: str = "untitled", max_length: int = 100) -> str:
    normalized = re.sub(r"[^\w.\-]", "_", value).strip("._-")
    normalized = normalized.replace("..", "_")
    result = normalized or fallback
    return result[:max_length]


def _validate_storage_path(storage_path: str) -> None:
    """Require a normalized POSIX identifier, never an OS path."""
    if not storage_path or "\\" in storage_path or "\x00" in storage_path:
        raise ValueError("存储路径为空")
    posix = PurePosixPath(storage_path)
    windows = PureWindowsPath(storage_path)
    if (
        posix.is_absolute()
        or windows.is_absolute()
        or windows.drive
        or storage_path.startswith("//")
        or any(part in {"", ".", ".."} for part in posix.parts)
    ):
        raise ValueError("非法存储路径")


def _local_path(storage_path: str) -> Path:
    """本地模式：相对 storage_path → 绝对路径。"""
    from app.core.config import settings

    root = Path(STORAGE_ROOT if STORAGE_ROOT != _DEFAULT_STORAGE_ROOT else settings.upload_dir)
    if not root.is_absolute():
        root = Path(__file__).resolve().parents[3] / root
    return root / storage_path


def build_storage_path(
    category_key: str,
    subcategory_name: str,
    doc_title: str,
    version_number: int,
) -> str:
    """构建后端无关的相对存储目录（不含根前缀）。"""
    return f"{category_key}/{subcategory_name}/{doc_title}/v{version_number}"


def ensure_storage_dir(path: str | Path) -> str | Path:
    """兼容旧代码：本地模式创建目录；OSS 模式空操作。"""
    if is_oss_enabled():
        return path
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return path


def save_file(storage_path: str, content: bytes) -> str:
    """存储文件（OSS/本地双模式）。返回 storage_path。"""
    _validate_storage_path(storage_path)
    if is_oss_enabled():
        from app.core.oss_client import get_bucket, get_oss_key

        try:
            get_bucket().put_object(get_oss_key(storage_path), content)
        except Exception as exc:
            raise FileStorageError("文件存储服务暂时不可用") from exc
    else:
        local = _local_path(storage_path)
        local.parent.mkdir(parents=True, exist_ok=True)
        local.write_bytes(content)
    return storage_path


def read_file(storage_path: str) -> bytes:
    """读取文件内容（OSS/本地双模式）。"""
    _validate_storage_path(storage_path)
    if is_oss_enabled():
        from app.core.oss_client import get_bucket, get_oss_key

        try:
            return get_bucket().get_object(get_oss_key(storage_path)).read()
        except Exception as exc:
            raise FileStorageError("文件存储服务暂时不可用") from exc
    return _local_path(storage_path).read_bytes()


def iter_file_chunks(storage_path: str, chunk_size: int = 64 * 1024):
    """以有界块读取受控存储对象，供哈希与解析边界校验使用。"""
    _validate_storage_path(storage_path)
    if chunk_size <= 0:
        raise ValueError("chunk_size 必须大于 0")
    if is_oss_enabled():
        from app.core.oss_client import get_bucket, get_oss_key

        stream = get_bucket().get_object(get_oss_key(storage_path))
        try:
            while chunk := stream.read(chunk_size):
                yield chunk
        finally:
            close = getattr(stream, "close", None)
            if callable(close):
                close()
            else:
                aclose = getattr(stream, "aclose", None)
                if callable(aclose):
                    result = aclose()
                    if inspect.isawaitable(result):
                        asyncio.run(_await_stream_close(result))
        return
    with _local_path(storage_path).open("rb") as source:
        while chunk := source.read(chunk_size):
            yield chunk


def _is_reparse(info: os.stat_result) -> bool:
    return bool(getattr(info, "st_file_attributes", 0) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400))


def _validated_local_source(storage_path: str) -> Path:
    target = _local_path(storage_path)
    root = _local_path("")
    try:
        root_info = root.lstat()
        if stat.S_ISLNK(root_info.st_mode) or _is_reparse(root_info):
            raise StoredFileValidationError("unsafe storage root")
        resolved_root = root.resolve(strict=True)
        current = root
        for part in PurePosixPath(storage_path).parts:
            current = current / part
            info = current.lstat()
            if stat.S_ISLNK(info.st_mode) or _is_reparse(info):
                raise StoredFileValidationError("unsafe storage path")
        resolved_target = target.resolve(strict=True)
        resolved_target.relative_to(resolved_root)
        if not resolved_target.is_file():
            raise StoredFileValidationError("unsafe storage path")
        return resolved_target
    except StoredFileValidationError:
        raise
    except (FileNotFoundError, OSError, ValueError):
        raise StoredFileValidationError("unsafe storage path") from None


def copy_storage_to_private_temp(
    storage_path: str,
    *,
    suffix: str,
    max_bytes: int,
    expected_hash: str | None = None,
    chunk_size: int = 64 * 1024,
) -> PrivateStoredFile:
    """Stream a bounded stored object into the hardened private temp root."""
    _validate_storage_path(storage_path)
    if max_bytes <= 0 or chunk_size <= 0:
        raise StoredFileValidationError("invalid size limit")
    output = create_private_temp_file(prefix="stored-document-", suffix=suffix)
    identity = snapshot_file_identity(output)
    digest = hashlib.sha256()
    total = 0
    try:
        if is_oss_enabled():
            chunks = iter_file_chunks(storage_path, chunk_size)
        else:
            source = _validated_local_source(storage_path)

            def local_chunks():
                with source.open("rb") as stream:
                    while chunk := stream.read(chunk_size):
                        yield chunk

            chunks = local_chunks()
        with output.open("wb") as destination:
            for chunk in chunks:
                total += len(chunk)
                if total > max_bytes:
                    raise StoredFileValidationError("stored file exceeds size limit")
                digest.update(chunk)
                destination.write(chunk)
        actual_hash = digest.hexdigest()
        if expected_hash is not None and actual_hash != expected_hash:
            raise StoredFileValidationError("stored file hash mismatch")
        return PrivateStoredFile(output, actual_hash, total, identity)
    except Exception:
        secure_unlink(output, identity=identity)
        raise


def validate_document_snapshot(
    path: Path,
    file_type: str,
    *,
    max_members: int = 1000,
    max_member_bytes: int = 100 * 1024 * 1024,
    max_total_uncompressed_bytes: int = 500 * 1024 * 1024,
    max_compression_ratio: float = 100,
) -> None:
    """Revalidate basic signatures and bounded OOXML structure before parsing."""
    normalized = file_type.lower().lstrip(".")
    try:
        with path.open("rb") as source:
            signature = source.read(8)
        if normalized == "pdf":
            if not signature.startswith(b"%PDF-"):
                raise StoredFileValidationError("invalid PDF signature")
            return
        if normalized == "doc":
            if signature != _OLE_SIGNATURE:
                raise StoredFileValidationError("invalid OLE signature")
            return
        if normalized in {"txt", "md"}:
            decoder = codecs.getincrementaldecoder("utf-8")()
            with path.open("rb") as source:
                while chunk := source.read(64 * 1024):
                    decoder.decode(chunk)
                decoder.decode(b"", final=True)
            return
        if normalized not in _OOXML_ROOTS or not signature.startswith(b"PK"):
            raise StoredFileValidationError("invalid document signature")
        with zipfile.ZipFile(path) as archive:
            members = archive.infolist()
            if len(members) > max_members:
                raise StoredFileValidationError("OOXML member count exceeds limit")
            names = {member.filename for member in members}
            if "[Content_Types].xml" not in names or not any(
                name.startswith(_OOXML_ROOTS[normalized]) for name in names
            ):
                raise StoredFileValidationError("invalid OOXML signature")
            total = 0
            for member in members:
                total += member.file_size
                if member.file_size > max_member_bytes or total > max_total_uncompressed_bytes:
                    raise StoredFileValidationError("OOXML expanded size exceeds limit")
                if member.file_size / max(member.compress_size, 1) > max_compression_ratio:
                    raise StoredFileValidationError("OOXML compression ratio exceeds limit")
    except StoredFileValidationError:
        raise
    except (OSError, UnicodeDecodeError, zipfile.BadZipFile, zipfile.LargeZipFile):
        raise StoredFileValidationError("invalid document signature") from None


def delete_file(storage_path: str) -> bool:
    """删除文件（OSS/本地双模式）。失败返回 False。"""
    try:
        if not storage_path:
            return False
        _validate_storage_path(storage_path)
        if is_oss_enabled():
            from app.core.oss_client import get_bucket, get_oss_key

            get_bucket().delete_object(get_oss_key(storage_path))
        else:
            p = _local_path(storage_path)
            if p.exists():
                p.unlink()
        return True
    except Exception:
        return False


def file_exists(storage_path: str) -> bool:
    """检查文件是否存在（OSS/本地双模式）。"""
    if not storage_path:
        return False
    _validate_storage_path(storage_path)
    if is_oss_enabled():
        from app.core.oss_client import get_bucket, get_oss_key

        try:
            return get_bucket().object_exists(get_oss_key(storage_path))
        except Exception as exc:
            raise FileStorageError("文件存储服务暂时不可用") from exc
    return _local_path(storage_path).exists()
