from __future__ import annotations

from core.redis import get_redis_settings
from workers.tasks import inspect_document_task, parse_document_task, knowledge_upload_task


class WorkerSettings:
    redis_settings = get_redis_settings()
    functions = [inspect_document_task, parse_document_task, knowledge_upload_task]
    job_timeout = 600
    max_tries = 3
    keep_result = 3600

    @staticmethod
    async def on_startup(ctx):
        pass

    @staticmethod
    async def on_shutdown(ctx):
        pass
