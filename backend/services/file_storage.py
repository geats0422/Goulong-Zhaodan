from __future__ import annotations

from pathlib import Path

STORAGE_ROOT = "data/knowledge"


def build_storage_path(
    category_key: str,
    subcategory_name: str,
    doc_title: str,
    version_number: int,
) -> Path:
    return Path(STORAGE_ROOT) / category_key / subcategory_name / doc_title / f"v{version_number}"


def ensure_storage_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def save_upload_file(file_path: Path, content: bytes) -> Path:
    ensure_storage_dir(file_path.parent)
    file_path.write_bytes(content)
    return file_path
