from __future__ import annotations

import pytest

from app.core import config
from app.core.config import Settings
from app.services import file_storage


@pytest.fixture
def storage_settings(monkeypatch, tmp_path):
    original = config.settings
    monkeypatch.setattr(file_storage, "STORAGE_ROOT", str(tmp_path))
    yield
    config.settings = original


def test_local_is_default_even_with_oss_values(storage_settings):
    config.settings = Settings(
        _env_file=None,
        oss_access_key_id="key-id",
        oss_access_key_secret="key-secret",
        oss_bucket_name="bucket",
        oss_endpoint="endpoint",
    )

    assert file_storage.is_oss_enabled() is False
    file_storage.save_file("users/test/document.txt", b"local")
    assert file_storage.read_file("users/test/document.txt") == b"local"


def test_explicit_oss_requires_complete_configuration(storage_settings):
    config.settings = Settings(_env_file=None, storage_backend="oss", oss_bucket_name="bucket")

    assert file_storage.is_oss_enabled() is False


def test_explicit_oss_wraps_sdk_failures(storage_settings, monkeypatch):
    class BrokenBucket:
        def put_object(self, *_args):
            raise RuntimeError("OSS 502 request-id=secret")

    config.settings = Settings(
        _env_file=None,
        storage_backend="oss",
        oss_access_key_id="key-id",
        oss_access_key_secret="key-secret",
        oss_bucket_name="bucket",
        oss_endpoint="endpoint",
    )
    monkeypatch.setattr("app.core.oss_client.get_bucket", lambda: BrokenBucket())
    monkeypatch.setattr("app.core.oss_client.get_oss_key", lambda path: path)

    with pytest.raises(file_storage.FileStorageError, match="文件存储服务暂时不可用"):
        file_storage.save_file("users/test/document.txt", b"payload")
