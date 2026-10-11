"""Миграции на настоящем Postgres. Тесты синхронные: `alembic upgrade` зовёт `asyncio.run`."""

import asyncio

from alembic.autogenerate import compare_metadata
from alembic.runtime.migration import MigrationContext
from sqlalchemy import BigInteger, String, inspect, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import create_async_engine

from almanac.models import Base, UtcDateTime


def _on(url, work):
    """Результат `work(sync_connection)` на базе с этим адресом."""

    async def go():
        engine = create_async_engine(url)
        try:
            async with engine.connect() as connection:
                return await connection.run_sync(work)
        finally:
            await engine.dispose()

    return asyncio.run(go())


def test_upgrade_builds_the_tables_of_the_models(fresh_database, migrate):
    migrate(fresh_database)

    tables = _on(fresh_database, lambda connection: set(inspect(connection).get_table_names()))
    assert set(Base.metadata.tables) <= tables

    version = _on(fresh_database, lambda connection: connection.scalar(text("select version_num from alembic_version")))
    assert version == "0001"


def test_models_and_migrations_have_not_drifted_apart(fresh_database, migrate):
    migrate(fresh_database)

    def diff(connection):
        return compare_metadata(MigrationContext.configure(connection, opts={"compare_type": True}), Base.metadata)

    # Автогенерации нечего добавить: модель и миграция говорят одно и то же.
    assert _on(fresh_database, diff) == []


def test_column_types_match_what_the_models_chose_for_postgres(fresh_database, migrate):
    """Что `compare_metadata` не видит: пояс времени, JSONB, побайтовое сравнение строк, 64 бита."""
    migrate(fresh_database)
    query = text(
        "select table_name, column_name, data_type, collation_name from information_schema.columns "
        "where table_schema = 'public'"
    )
    found = {(row.table_name, row.column_name): row for row in _on(fresh_database, lambda c: c.execute(query).all())}

    checked = set()
    for table in Base.metadata.sorted_tables:
        for column in table.columns:
            row = found[(table.name, column.name)]
            if isinstance(column.type, UtcDateTime):
                assert row.data_type == "timestamp with time zone", (table.name, column.name)
                checked.add("timestamptz")
            elif isinstance(column.type, JSONB):
                assert row.data_type == "jsonb", (table.name, column.name)
                checked.add("jsonb")
            elif isinstance(column.type, BigInteger):
                assert row.data_type == "bigint", (table.name, column.name)
                checked.add("bigint")
            elif isinstance(column.type, String) and column.type.collation:
                assert row.collation_name == column.type.collation, (table.name, column.name)
                checked.add("collation")
    assert checked == {"timestamptz", "jsonb", "bigint", "collation"}
