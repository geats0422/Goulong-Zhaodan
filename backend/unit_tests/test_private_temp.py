from __future__ import annotations

import logging
import os
from pathlib import Path

import pytest

from app.lib.private_temp import (
    cleanup_private_temp_dir,
    create_private_temp_file,
    secure_unlink,
    snapshot_file_identity,
    validate_file_identity,
)


def test_windows_private_temp_directory_fails_closed_when_acl_hardening_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.lib import private_temp

    root = tmp_path / "private-root"
    monkeypatch.setattr(private_temp, "PRIVATE_TEMP_DIR", root)
    monkeypatch.setattr(private_temp, "_root_identity", None)
    monkeypatch.setattr(private_temp, "_windows_acl_checked", False)
    monkeypatch.setattr(private_temp.sys, "platform", "win32")
    monkeypatch.setattr(private_temp, "_harden_windows_acl", lambda _path: False)

    with pytest.raises(RuntimeError, match="private temporary directory is unavailable"):
        create_private_temp_file(prefix="sensitive-", suffix=".tmp")


def test_unlink_failure_retries_and_logs_only_redacted_metadata(
    tmp_path: Path,
    monkeypatch,
    caplog,
) -> None:
    secret_path = tmp_path / "customer-secret-contract.pdf"
    secret_path.write_bytes(b"secret")
    attempts = 0

    def fail_unlink(self: Path, *, missing_ok: bool = False) -> None:
        nonlocal attempts
        attempts += 1
        raise PermissionError("sensitive path detail")

    monkeypatch.setattr(Path, "unlink", fail_unlink)
    caplog.set_level(logging.WARNING)

    assert secure_unlink(secret_path, attempts=3, retry_delay_seconds=0) is False
    assert attempts == 3
    assert "customer-secret-contract" not in caplog.text
    assert "sensitive path detail" not in caplog.text
    assert "temporary file cleanup failed" in caplog.text


def test_cleanup_failure_never_overrides_original_exception(tmp_path: Path, monkeypatch) -> None:
    path = tmp_path / "secret.tmp"
    path.write_bytes(b"secret")
    monkeypatch.setattr(Path, "unlink", lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("cleanup")))

    with pytest.raises(RuntimeError, match="original"):
        try:
            raise RuntimeError("original")
        finally:
            secure_unlink(path, attempts=1, retry_delay_seconds=0)


def test_private_temp_rejects_symlink_replacement_and_identity_change(tmp_path: Path) -> None:
    path = create_private_temp_file(prefix="snapshot-", suffix=".txt")
    identity = snapshot_file_identity(path)
    replacement = tmp_path / "replacement.txt"
    replacement.write_text("replacement", encoding="utf-8")
    secure_unlink(path)

    try:
        os.symlink(replacement, path)
    except OSError:
        path.write_text("different file", encoding="utf-8")

    assert validate_file_identity(path, identity) is False
    secure_unlink(path)


def test_private_temp_cleanup_removes_stale_private_files() -> None:
    path = create_private_temp_file(prefix="stale-", suffix=".tmp")
    assert path.exists()

    removed = cleanup_private_temp_dir(max_age_seconds=0)

    assert removed >= 1
    assert not path.exists()
