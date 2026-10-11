"""Миграции идут синхронным драйвером: адрес тот же, что у приложения, без `+aiosqlite`."""

from alembic import context
from sqlalchemy import create_engine

from almanac.config import Settings
from almanac.models import Base


def _url() -> str:
    return Settings().database_url.replace("+aiosqlite", "")


def run() -> None:
    engine = create_engine(_url())
    with engine.connect() as connection:
        # SQLite не умеет ALTER на большинство изменений: batch пересоздаёт таблицу.
        context.configure(connection=connection, target_metadata=Base.metadata, render_as_batch=True)
        with context.begin_transaction():
            context.run_migrations()


run()
