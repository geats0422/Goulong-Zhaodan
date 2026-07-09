from __future__ import annotations

from typing import Any

from arq.cron import cron

from app.core.redis import get_redis_settings
from app.workers.tasks import (
    close_expired_orders_task,
    inspect_document_task,
    knowledge_upload_task,
    parse_document_task,
)


class WorkerSettings:
    redis_settings = get_redis_settings()
    functions = [
        inspect_document_task,
        parse_document_task,
        knowledge_upload_task,
        close_expired_orders_task,
    ]
    job_timeout = 600
    max_tries = 3
    keep_result = 3600
    cron_jobs: list[Any] = [
        # 每 5 分钟关闭超时未支付的 pending 订单
        cron(close_expired_orders_task, minute={0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55}),
    ]

    @staticmethod
    async def on_startup(ctx):
        pass

    @staticmethod
    async def on_shutdown(ctx):
        pass
