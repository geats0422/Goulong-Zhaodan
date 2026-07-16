from __future__ import annotations

import hashlib
import io
import os
import zipfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from app.lib import private_temp
from app.services import file_storage


@pytest.fixture
def isolated_storage(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    storage_root = tmp_path / "storage"
    private_root = tmp_path / "private"
    storage_root.mkdir()
    monkeypatch.setattr(file_storage, "STORAGE_ROOT", str(storage_root))
    monkeypatch.setattr(private_temp, "PRIVATE_TEMP_DIR", private_root)
    monkeypatch.setattr(private_temp, "_root_identity", None)
    monkeypatch.setattr(private_temp, "_last_cleanup", 0.0)
    monkeypatch.setattr(file_storage, "is_oss_enabled", lambda: False)
    return storage_root, private_root


def test_stream_copy_hashes_and_removes_real_private_temp(isolated_storage) -> None:
    storage_root, private_root = isolated_storage
    content = b"%PDF-1.7\n" + b"document" * 100
    source = storage_root / "users" / "u" / "source.pdf"
    source.parent.mkdir(parents=True)
    source.write_bytes(content)

    artifact = file_storage.copy_storage_to_private_temp(
        "users/u/source.pdf",
        suffix=".pdf",
        max_bytes=len(content),
        expected_hash=hashlib.sha256(content).hexdigest(),
    )

    assert artifact.path.parent == private_root
    assert artifact.size == len(content)
    assert artifact.content_hash == hashlib.sha256(content).hexdigest()
    assert artifact.path.read_bytes() == content
    assert private_temp.secure_unlink(artifact.path, identity=artifact.identity)
    assert not artifact.path.exists()


def test_stream_copy_stops_at_limit_and_cleans_partial_file(isolated_storage) -> None:
    storage_root, private_root = isolated_storage
    source = storage_root / "users" / "u" / "large.pdf"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"x" * 1025)

    with pytest.raises(file_storage.StoredFileValidationError, match="size"):
        file_storage.copy_storage_to_private_temp("users/u/large.pdf", suffix=".pdf", max_bytes=1024)

    assert list(private_root.iterdir()) == []


@pytest.mark.skipif(not hasattr(os, "symlink"), reason="symlink unsupported")
def test_local_storage_rejects_symlink_escape(isolated_storage, tmp_path: Path) -> None:
    storage_root, _ = isolated_storage
    outside = tmp_path / "outside.pdf"
    outside.write_bytes(b"%PDF-1.7")
    link = storage_root / "users" / "u" / "source.pdf"
    link.parent.mkdir(parents=True)
    try:
        link.symlink_to(outside)
    except OSError:
        pytest.skip("symlink creation requires additional privileges")

    with pytest.raises(file_storage.StoredFileValidationError, match="unsafe"):
        file_storage.copy_storage_to_private_temp("users/u/source.pdf", suffix=".pdf", max_bytes=1024)


@pytest.mark.parametrize("path", ["/etc/passwd", "C:/secret.pdf", "//server/share/a.pdf", "users\\u\\a.pdf"])
def test_storage_identifier_rejects_absolute_unc_drive_and_backslash(path: str) -> None:
    with pytest.raises(ValueError):
        file_storage._validate_storage_path(path)


def test_oss_chunk_iterator_closes_stream_when_consumer_stops(monkeypatch: pytest.MonkeyPatch) -> None:
    stream = Mock()
    stream.read.side_effect = [b"chunk", b""]
    bucket = Mock()
    bucket.get_object.return_value = stream
    monkeypatch.setattr(file_storage, "is_oss_enabled", lambda: True)
    monkeypatch.setattr("app.core.oss_client.get_bucket", lambda: bucket)
    monkeypatch.setattr("app.core.oss_client.get_oss_key", lambda path: path)

    chunks = file_storage.iter_file_chunks("users/u/file.pdf")
    assert next(chunks) == b"chunk"
    chunks.close()

    stream.close.assert_called_once_with()


def test_oss_chunk_iterator_supports_async_close(monkeypatch: pytest.MonkeyPatch) -> None:
    stream = SimpleNamespace(read=Mock(side_effect=[b"chunk", b""]), aclose=AsyncMock())
    bucket = Mock()
    bucket.get_object.return_value = stream
    monkeypatch.setattr(file_storage, "is_oss_enabled", lambda: True)
    monkeypatch.setattr("app.core.oss_client.get_bucket", lambda: bucket)
    monkeypatch.setattr("app.core.oss_client.get_oss_key", lambda path: path)

    assert list(file_storage.iter_file_chunks("users/u/file.pdf")) == [b"chunk"]
    stream.aclose.assert_awaited_once_with()


def _ooxml_bytes(*, members: list[tuple[str, bytes]]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, content in members:
            archive.writestr(name, content)
    return buffer.getvalue()


def test_document_signature_and_ooxml_limits_are_revalidated(isolated_storage) -> None:
    storage_root, _ = isolated_storage
    source = storage_root / "users" / "u" / "source.docx"
    source.parent.mkdir(parents=True)
    source.write_bytes(
        _ooxml_bytes(
            members=[
                ("[Content_Types].xml", b"types"),
                ("word/document.xml", b"document"),
            ]
        )
    )
    artifact = file_storage.copy_storage_to_private_temp(
        "users/u/source.docx", suffix=".docx", max_bytes=4096
    )
    try:
        file_storage.validate_document_snapshot(
            artifact.path,
            "docx",
            max_members=5,
            max_member_bytes=100,
            max_total_uncompressed_bytes=200,
            max_compression_ratio=20,
        )
        with pytest.raises(file_storage.StoredFileValidationError):
            file_storage.validate_document_snapshot(
                artifact.path,
                "docx",
                max_members=1,
                max_member_bytes=100,
                max_total_uncompressed_bytes=200,
                max_compression_ratio=20,
            )
    finally:
        private_temp.secure_unlink(artifact.path, identity=artifact.identity)


def test_ooxml_zip_bomb_and_wrong_magic_are_rejected(isolated_storage) -> None:
    storage_root, _ = isolated_storage
    bomb = storage_root / "users" / "u" / "bomb.docx"
    bomb.parent.mkdir(parents=True)
    bomb.write_bytes(
        _ooxml_bytes(
            members=[
                ("[Content_Types].xml", b"types"),
                ("word/document.xml", b"0" * 20_000),
            ]
        )
    )
    artifact = file_storage.copy_storage_to_private_temp(
        "users/u/bomb.docx", suffix=".docx", max_bytes=4096
    )
    try:
        with pytest.raises(file_storage.StoredFileValidationError):
            file_storage.validate_document_snapshot(
                artifact.path,
                "docx",
                max_members=5,
                max_member_bytes=30_000,
                max_total_uncompressed_bytes=30_000,
                max_compression_ratio=2,
            )
    finally:
        private_temp.secure_unlink(artifact.path, identity=artifact.identity)

    wrong = storage_root / "users" / "u" / "wrong.pdf"
    wrong.write_bytes(b"not a pdf")
    artifact = file_storage.copy_storage_to_private_temp(
        "users/u/wrong.pdf", suffix=".pdf", max_bytes=100
    )
    try:
        with pytest.raises(file_storage.StoredFileValidationError, match="signature"):
            file_storage.validate_document_snapshot(artifact.path, "pdf")
    finally:
        private_temp.secure_unlink(artifact.path, identity=artifact.identity)
