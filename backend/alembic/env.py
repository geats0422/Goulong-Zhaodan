from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from logging.config import fileConfig
import os

from alembic import context
from sqlalchemy import create_engine, pool

from app.models import Base

config = context.config

db_url = os.environ.get("ALEMBIC_DATABASE_URL") or config.get_main_option("sqlalchemy.url")
# alembic 走同步引擎，去掉异步驱动后缀
db_url = db_url.replace("+asyncpg", "")

if config.config_file_name is not None:
    # disable_existing_loggers=False 避免禁用测试框架（pytest caplog）和应用
    # 已实例化的 logger；同进程内调用 command.upgrade 时尤其重要，否则后续测试
    # 的 caplog 会因为 logger 被 fileConfig 静默禁用而捕获不到日志。
    fileConfig(config.config_file_name, disable_existing_loggers=False)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=db_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_schemas=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = create_engine(db_url, poolclass=pool.NullPool)
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata, include_schemas=True)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
