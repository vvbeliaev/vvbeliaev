"""Миграции идут на asyncpg, как и приложение. Адрес — из `Settings().database_url`.

Тесты кладут свой адрес в `config.attributes["url"]`: окружение и `.env` разработчика остаются нетронутыми.
`command.upgrade` зовёт `asyncio.run`, поэтому изнутри идущего цикла событий его не вызвать.
"""

import asyncio

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import create_async_engine

from almanac.config import Settings
from almanac.models import Base, UtcDateTime

config = context.config


def render_item(kind: str, obj, autogen_context):
    """Автогенерация пишет `UtcDateTime` как есть, а миграция не должна зависеть от кода приложения."""
    if kind == "type" and isinstance(obj, UtcDateTime):
        return "sa.DateTime(timezone=True)"
    return False


def _migrate(connection: Connection) -> None:
    context.configure(
        connection=connection, target_metadata=Base.metadata, compare_type=True, render_item=render_item
    )
    with context.begin_transaction():
        context.run_migrations()


async def run() -> None:
    engine = create_async_engine(config.attributes.get("url") or Settings().database_url, poolclass=pool.NullPool)
    try:
        async with engine.connect() as connection:
            await connection.run_sync(_migrate)
    finally:
        await engine.dispose()


asyncio.run(run())
