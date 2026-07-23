"""Alembic 迁移环境配置。

对齐 database-design.md §8 + system-architecture §3：
- 迁移走同步 URL（database_sync_url, psycopg2），运行时用 async URL。
- target_metadata = Base.metadata，为未来 autogenerate 预留。
- 当前阶段 2 手写迁移（op.create_table），不依赖 autogenerate。
"""

from __future__ import annotations

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

# 导入 app 配置与 Base（prepend_sys_path=. 已将 backend/ 加入 sys.path）
from app.core.config import get_settings
from app.core.database import Base

# Alembic Config 对象
config = context.config

# 配置 Python logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# 从应用配置注入同步数据库 URL（覆盖 alembic.ini 的占位值）
settings = get_settings()
config.set_main_option("sqlalchemy.url", settings.database_sync_url)

# target_metadata 用于 autogenerate；当前手写迁移，但仍指向 Base.metadata
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """离线模式：仅用 URL 生成 SQL 脚本，不需要 DBAPI 连接。"""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """在线模式：创建同步 Engine 并关联连接执行迁移。"""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
