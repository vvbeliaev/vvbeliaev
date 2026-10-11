"""Миграции идут синхронным драйвером: адрес тот же, что у приложения, без `+aiosqlite`."""

from alembic import context
from sqlalchemy import create_engine, event

from almanac.config import Settings
from almanac.models import Base


def _url() -> str:
    return Settings().database_url.replace("+aiosqlite", "")


def _engine():
    engine = create_engine(_url())
    if engine.dialect.name == "sqlite":
        # pysqlite сам начинает транзакцию только перед INSERT/UPDATE/DELETE, а DDL выполняет сразу.
        # Миграция, упавшая на полпути, оставила бы таблицы, а `alembic_version` — прежней, и следующий
        # старт упёрся бы в «table already exists». Рецепт из документации SQLAlchemy: драйвер не
        # трогает транзакции, а `BEGIN` отправляем сами.
        @event.listens_for(engine, "connect")
        def _no_driver_transactions(dbapi_connection, _record) -> None:
            dbapi_connection.isolation_level = None

        @event.listens_for(engine, "begin")
        def _begin(connection) -> None:
            connection.exec_driver_sql("BEGIN")

    return engine


def run() -> None:
    engine = _engine()
    with engine.connect() as connection:
        # SQLite не умеет ALTER на большинство изменений: batch пересоздаёт таблицу.
        context.configure(
            connection=connection,
            target_metadata=Base.metadata,
            render_as_batch=True,
            transactional_ddl=True,
        )
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()


run()
