"""文件存储抽象层（本地 / 阿里云 OSS 双模式自动切换）。

storage_path 始终使用后端无关的相对路径（如 "traditional/房建/招标文件/v1/file.pdf"），
数据库只存相对路径。实际落位由后端决定：
- OSS 模式（oss_bucket_name + oss_endpoint 已配置）：相对路径前加 oss_prefix 作为 OSS key。
- 本地模式（默认）：相对路径拼接到 STORAGE_ROOT 之下。
"""
from __future__ import annotations

import re
from pathlib import Path

STORAGE_ROOT = "data/knowledge"


def is_oss_enabled() -> bool:
    """检测 OSS 是否配置完整（配置完整则启用 OSS，否则回退本地）。"""
    from app.core.config import settings

    return bool(settings.oss_bucket_name and settings.oss_endpoint)


def safe_path_segment(value: str, fallback: str = "untitled", max_length: int = 100) -> str:
    normalized = re.sub(r"[^\w.\-]", "_", value).strip("._-")
    normalized = normalized.replace("..", "_")
    result = normalized or fallback
    return result[:max_length]


def _validate_storage_path(storage_path: str) -> None:
    """校验相对存储路径，阻止路径遍历（禁止 .. 段）。"""
    if not storage_path:
        raise ValueError("存储路径为空")
    parts = storage_path.replace("\\", "/").split("/")
    if any(p == ".." for p in parts):
        raise ValueError("非法存储路径")


def _local_path(storage_path: str) -> Path:
    """本地模式：相对 storage_path → 绝对路径。"""
    return Path(STORAGE_ROOT) / storage_path


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

        get_bucket().put_object(get_oss_key(storage_path), content)
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

        return get_bucket().get_object(get_oss_key(storage_path)).read()
    return _local_path(storage_path).read_bytes()


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

        return get_bucket().object_exists(get_oss_key(storage_path))
    return _local_path(storage_path).exists()
