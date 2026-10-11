import sqlite3

import pytest
from alembic import command
from alembic.config import Config

from almanac.models import Base


def test_migrations_build_the_schema_of_the_models(tmp_path, monkeypatch):
    target = tmp_path / "migrated.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{target}")
    config = Config("alembic.ini")

    command.upgrade(config, "head")
    with sqlite3.connect(target) as connection:
        tables = {row[0] for row in connection.execute("select name from sqlite_master where type = 'table'")}
    assert set(Base.metadata.tables) <= tables

    # Модели и миграции не разошлись: автогенерации нечего добавить.
    command.check(config)


def _tables(path):
    with sqlite3.connect(path) as connection:
        return {row[0] for row in connection.execute("select name from sqlite_master where type = 'table'")}


def _version(path):
    with sqlite3.connect(path) as connection:
        return connection.execute("select version_num from alembic_version").fetchone()[0]


def test_a_migration_that_fails_halfway_leaves_nothing_behind(tmp_path, monkeypatch, next_migration):
    target = tmp_path / "half.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{target}")
    config = next_migration(
        """
        op.create_table("half_done", sa.Column("id", sa.Integer(), primary_key=True))
        raise RuntimeError("boom")
        """
    )
    command.upgrade(config, "0001")
    tables_before = _tables(target)

    with pytest.raises(RuntimeError, match="boom"):
        command.upgrade(config, "head")

    # DDL откатилась вместе с версией: следующий старт не упрётся в «table already exists».
    assert _tables(target) == tables_before
    assert "half_done" not in _tables(target)
    assert _version(target) == "0001"


def test_a_good_second_migration_applies_in_one_piece(tmp_path, monkeypatch, next_migration):
    target = tmp_path / "good.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{target}")
    config = next_migration('op.create_table("extra", sa.Column("id", sa.Integer(), primary_key=True))')

    command.upgrade(config, "head")

    assert "extra" in _tables(target)
    assert _version(target) == "0002"
