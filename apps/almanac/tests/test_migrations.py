import sqlite3

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
