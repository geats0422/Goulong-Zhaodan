from __future__ import annotations

from typing import Any

from arq import func
from arq.cron import cron

from app.core.redis import get_redis_settings
from app.workers.dispatcher import document_job_dispatcher_task
from app.workers.tasks import (
    close_expired_orders_task,
    document_processing_task,
    inspect_document_task,
    knowledge_upload_task,
    parse_document_task,
    reset_monthly_free_quota_task,
)

document_processing_registration = func(document_processing_task, timeout=1800)
# Preserve the callable-style introspection used by existing worker smoke tests.
document_processing_registration.__name__ = document_processing_registration.name


class WorkerSettings:
    redis_settings = get_redis_settings()
    functions = [
        inspect_document_task,
        parse_document_task,
        knowledge_upload_task,
        document_processing_registration,
        close_expired_orders_task,
        document_job_dispatcher_task,
    ]
    job_timeout = 600
    max_jobs = 2
    max_tries = 3
    keep_result = 3600
    cron_jobs: list[Any] = [
        cron(close_expired_orders_task, minute={0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55}),
        cron(document_job_dispatcher_task, minute=set(range(60))),
        cron(reset_monthly_free_quota_task, day=1, hour=0, minute=5),
    ]

    @staticmethod
    async def on_startup(ctx):
        await document_job_dispatcher_task(ctx)

    @staticmethod
    async def on_shutdown(ctx):
        pass
