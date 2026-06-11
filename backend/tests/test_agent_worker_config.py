from __future__ import annotations

from core.config import Settings
from workers.config import WorkerSettings


TASK_FUNCTION_NAMES = [
    "inspect_document_task",
    "parse_document_task",
    "knowledge_upload_task",
]


def test_redis_settings_from_config():
    s = Settings()
    assert hasattr(s, "redis_url")
    assert s.redis_url == "redis://localhost:6379"


def test_worker_settings_job_timeout():
    assert WorkerSettings.job_timeout == 600


def test_worker_settings_max_tries():
    assert WorkerSettings.max_tries == 3


def test_worker_settings_keep_result():
    assert WorkerSettings.keep_result == 3600


def test_worker_settings_functions():
    functions = WorkerSettings.functions
    fn_names = [fn.__name__ for fn in functions]
    for name in TASK_FUNCTION_NAMES:
        assert name in fn_names


def test_worker_settings_has_redis_settings():
    has_redis_attr = hasattr(WorkerSettings, "redis_settings")
    has_startup = hasattr(WorkerSettings, "on_startup")
    has_shutdown = hasattr(WorkerSettings, "on_shutdown")
    assert has_redis_attr or (has_startup and has_shutdown)
