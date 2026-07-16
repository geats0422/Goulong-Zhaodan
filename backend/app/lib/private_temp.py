"""Bounded, private temporary-file handling for sensitive document data."""

from __future__ import annotations

import logging
import os
import re
import stat
import subprocess
import sys
import tempfile
import threading
import time
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

PRIVATE_TEMP_DIR = Path(tempfile.gettempdir()) / "goulong-document-processing"
DEFAULT_STALE_AGE_SECONDS = 24 * 60 * 60
_CLEANUP_INTERVAL_SECONDS = 15 * 60
_last_cleanup = 0.0
_cleanup_lock = threading.Lock()
_root_identity: tuple[int, int] | None = None
_windows_acl_checked = False


@dataclass(frozen=True, slots=True)
class FileIdentity:
    device: int
    inode: int


def _is_reparse(stat_result: os.stat_result) -> bool:
    attributes = getattr(stat_result, "st_file_attributes", 0)
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    return bool(attributes & reparse_flag)


def _ensure_private_temp_dir() -> Path:
    global _root_identity, _windows_acl_checked
    try:
        PRIVATE_TEMP_DIR.mkdir(mode=0o700, parents=False, exist_ok=True)
        info = PRIVATE_TEMP_DIR.lstat()
        if not stat.S_ISDIR(info.st_mode) or stat.S_ISLNK(info.st_mode) or _is_reparse(info):
            raise RuntimeError("private temporary directory is unsafe")
        current_identity = (info.st_dev, info.st_ino)
        if _root_identity is not None and current_identity != _root_identity:
            raise RuntimeError("private temporary directory identity changed")
        _root_identity = current_identity
        PRIVATE_TEMP_DIR.chmod(0o700)
        if sys.platform == "win32" and not _windows_acl_checked:
            if not _harden_windows_acl(PRIVATE_TEMP_DIR):
                raise RuntimeError("private temporary directory ACL hardening failed")
            _windows_acl_checked = True
        return PRIVATE_TEMP_DIR
    except (OSError, RuntimeError):
        logger.error("private temporary directory is unavailable")
        raise RuntimeError("private temporary directory is unavailable") from None


def snapshot_file_identity(path: Path) -> FileIdentity:
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or stat.S_ISLNK(info.st_mode) or _is_reparse(info):
        raise OSError("unsafe temporary file")
    return FileIdentity(info.st_dev, info.st_ino)


def _harden_windows_acl(path: Path) -> bool:
    creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        identity = subprocess.run(
            ["whoami", "/user", "/fo", "csv", "/nh"],
            check=True,
            capture_output=True,
            text=True,
            timeout=2,
            creationflags=creation_flags,
        )
        match = re.search(r"S-\d-(?:\d+-)+\d+", identity.stdout)
        if match is None:
            return False
        sid = match.group(0)
        subprocess.run(
            [
                "icacls",
                str(path),
                "/inheritance:r",
                "/grant:r",
                f"*{sid}:(OI)(CI)F",
                "/remove:g",
                "*S-1-1-0",
                "*S-1-5-11",
                "*S-1-5-32-545",
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=3,
            creationflags=creation_flags,
        )
        return True
    except (OSError, subprocess.SubprocessError):
        return False


def validate_file_identity(path: Path, identity: FileIdentity) -> bool:
    try:
        return snapshot_file_identity(path) == identity
    except OSError:
        return False


def create_private_temp_file(*, prefix: str, suffix: str) -> Path:
    root = _ensure_private_temp_dir()
    _periodic_cleanup()
    descriptor = -1
    try:
        descriptor, raw_path = tempfile.mkstemp(prefix=prefix, suffix=suffix, dir=root)
        os.chmod(raw_path, 0o600)
        return Path(raw_path)
    finally:
        if descriptor >= 0:
            os.close(descriptor)


def secure_unlink(
    path: Path,
    *,
    identity: FileIdentity | None = None,
    attempts: int = 3,
    retry_delay_seconds: float = 0.02,
) -> bool:
    """Delete without exposing the sensitive path and never mask an active exception."""
    bounded_attempts = max(1, min(attempts, 10))
    for attempt in range(bounded_attempts):
        try:
            if identity is not None and not validate_file_identity(path, identity):
                logger.warning("temporary file cleanup refused identity mismatch")
                return False
            info = path.lstat()
            if not stat.S_ISLNK(info.st_mode) and not _is_reparse(info):
                path.chmod(0o600)
            path.unlink()
            return True
        except FileNotFoundError:
            return True
        except OSError:
            if attempt + 1 < bounded_attempts and retry_delay_seconds > 0:
                time.sleep(min(retry_delay_seconds, 0.1))
    logger.warning("temporary file cleanup failed attempts=%d", bounded_attempts)
    return False


def cleanup_private_temp_dir(*, max_age_seconds: float = DEFAULT_STALE_AGE_SECONDS) -> int:
    try:
        root = _ensure_private_temp_dir()
        cutoff = time.time() - max(0, max_age_seconds)
        entries = list(root.iterdir())
    except (OSError, RuntimeError):
        logger.warning("temporary directory cleanup scan failed")
        return 0

    removed = 0
    for path in entries:
        try:
            info = path.lstat()
            if info.st_mtime > cutoff:
                continue
            if stat.S_ISDIR(info.st_mode) and not stat.S_ISLNK(info.st_mode):
                logger.warning("temporary directory cleanup skipped unexpected directory")
                continue
            if secure_unlink(path):
                removed += 1
        except OSError:
            logger.warning("temporary directory cleanup entry failed")
    return removed


def _periodic_cleanup() -> None:
    global _last_cleanup
    now = time.monotonic()
    if now - _last_cleanup < _CLEANUP_INTERVAL_SECONDS:
        return
    with _cleanup_lock:
        if now - _last_cleanup < _CLEANUP_INTERVAL_SECONDS:
            return
        cleanup_private_temp_dir()
        _last_cleanup = now
