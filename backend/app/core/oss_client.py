"""阿里云 OSS 对象存储客户端。

替代本地磁盘存储，文件统一上传到 OSS Bucket。
AccessKey 优先用专用 oss_access_key_id/secret，缺省时复用 aliyun_access_key_id/secret。
"""
from __future__ import annotations

import logging

from app.core.config import settings

logger = logging.getLogger(__name__)

_bucket = None


def get_bucket():
    """获取 OSS Bucket 单例（懒加载）。"""
    global _bucket
    if _bucket is not None:
        return _bucket

    import oss2

    access_key = settings.oss_access_key_id or settings.aliyun_access_key_id
    access_secret = settings.oss_access_key_secret or settings.aliyun_access_key_secret

    if not access_key or not access_secret:
        raise RuntimeError("OSS 未配置 AccessKey（oss_access_key_id/secret 或 aliyun_access_key_id/secret）")
    if not settings.oss_bucket_name or not settings.oss_endpoint:
        raise RuntimeError("OSS 未配置 oss_bucket_name/oss_endpoint")

    auth = oss2.Auth(access_key, access_secret)
    _bucket = oss2.Bucket(auth, settings.oss_endpoint, settings.oss_bucket_name)
    logger.info(
        "OSS 客户端已初始化: bucket=%s endpoint=%s",
        settings.oss_bucket_name,
        settings.oss_endpoint,
    )
    return _bucket


def get_oss_key(storage_path: str) -> str:
    """把相对 storage_path 转为 OSS key（加 prefix）。"""
    prefix = settings.oss_prefix.rstrip("/") if settings.oss_prefix else ""
    if prefix:
        return f"{prefix}/{storage_path}"
    return storage_path
