import os
import sqlite3
import subprocess
import sys

import pytest
from alembic import command
from alembic.util.exc import CommandError

from almanac import backup, migrate

NEW_TABLE = 'op.create_table("extra", sa.Column("id", sa.Integer(), primary_key=True))'


@pytest.fixture
def paths(tmp_path, monkeypatch):
    """База и каталог копий во временном каталоге; рабочий каталог — тоже, чтобы `.env` не подмешался."""
    monkeypatch.chdir(tmp_path)
    database = tmp_path / "almanac.db"
    backups = tmp_path / "backups"
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{database}")
    monkeypatch.setenv("BACKUP_DIR", str(backups))
    monkeypatch.delenv("DATA_MOUNT", raising=False)
    return database, backups


def _tables(path):
    with sqlite3.connect(path) as connection:
        return {row[0] for row in connection.execute("select name from sqlite_master where type = 'table'")}


def _version(path):
    with sqlite3.connect(path) as connection:
        return connection.execute("select version_num from alembic_version").fetchone()[0]


def _database_at_0001(config, database):
    command.upgrade(config, "0001")
    with sqlite3.connect(database) as connection:
        connection.execute("create table marker (note text)")
        connection.execute("insert into marker values ('до миграции')")


def test_a_database_behind_head_is_copied_before_the_upgrade(paths, next_migration, capsys):
    database, backups = paths
    config = next_migration(NEW_TABLE)
    _database_at_0001(config, database)

    assert migrate.main(config) == 0

    copy = backups / "pre-0002.db"
    assert _version(copy) == "0001"  # копия снята до обновления
    assert "extra" not in _tables(copy)
    with sqlite3.connect(copy) as connection:
        assert connection.execute("select note from marker").fetchall() == [("до миграции",)]
    assert _version(database) == "0002"
    assert "extra" in _tables(database)
    assert [path.name for path in backups.iterdir()] == ["pre-0002.db"]


def test_an_up_to_date_database_is_not_copied(paths, next_migration):
    database, backups = paths
    config = next_migration(NEW_TABLE)
    command.upgrade(config, "head")

    assert migrate.main(config) == 0

    assert not backups.exists()
    assert _version(database) == "0002"


def test_an_existing_pre_copy_is_kept_as_it_is(paths, next_migration):
    database, backups = paths
    config = next_migration(NEW_TABLE)
    _database_at_0001(config, database)
    backups.mkdir()
    (backups / "pre-0002.db").write_bytes(b"taken by an earlier attempt")

    assert migrate.main(config) == 0

    assert (backups / "pre-0002.db").read_bytes() == b"taken by an earlier attempt"
    assert _version(database) == "0002"


def test_without_a_backup_directory_the_upgrade_still_runs(paths, next_migration, monkeypatch):
    database, backups = paths
    config = next_migration(NEW_TABLE)
    _database_at_0001(config, database)
    monkeypatch.delenv("BACKUP_DIR")

    assert migrate.main(config) == 0

    assert not backups.exists()
    assert _version(database) == "0002"


def test_a_new_database_is_created_without_a_copy(paths):
    database, backups = paths

    assert migrate.main() == 0

    assert _version(database) == "0001"
    assert not backups.exists()


def test_a_database_with_an_unknown_revision_is_neither_copied_nor_upgraded(paths):
    database, backups = paths
    migrate.main()
    with sqlite3.connect(database) as connection:
        connection.execute("update alembic_version set version_num = '9999'")

    with pytest.raises(CommandError):
        migrate.main()

    # Копия «перед миграцией» с чужой ревизией заняла бы имя настоящей и скрыла бы её.
    assert not backups.exists()


def test_a_copy_that_cannot_be_made_stops_the_migration(paths, next_migration, monkeypatch, capsys):
    database, backups = paths
    config = next_migration(NEW_TABLE)
    _database_at_0001(config, database)

    def no_space(_source, _directory):
        raise RuntimeError("not enough free space for a database copy")

    monkeypatch.setattr(backup, "require_space", no_space)

    assert migrate.main(config) == 1

    assert "not enough free space" in capsys.readouterr().err
    assert _version(database) == "0001"
    assert "extra" not in _tables(database)
    assert not list(backups.glob("pre-*"))


def test_an_unmounted_data_directory_stops_the_start_and_creates_nothing(paths, tmp_path, monkeypatch, capsys):
    database, backups = paths
    plain = tmp_path / "plain"
    plain.mkdir()
    monkeypatch.setenv("DATA_MOUNT", str(plain))

    assert migrate.main() == 1

    assert capsys.readouterr().err.strip() == (
        f"DATA_MOUNT={plain} is not a mounted volume: refusing to start on an empty database"
    )
    assert not database.exists()
    assert not backups.exists()


def test_a_missing_data_directory_is_not_a_mount_either(paths, tmp_path, monkeypatch):
    database, _ = paths
    monkeypatch.setenv("DATA_MOUNT", str(tmp_path / "nowhere"))

    assert migrate.main() == 1
    assert not database.exists()


def test_a_mounted_data_directory_lets_the_start_go_on(paths, tmp_path, monkeypatch):
    database, _ = paths
    monkeypatch.setenv("DATA_MOUNT", str(tmp_path))
    monkeypatch.setattr(os.path, "ismount", lambda path: str(path) == str(tmp_path))

    assert migrate.main() == 0
    assert database.exists()


def test_the_module_runs_as_a_command_and_exits_with_status_one(tmp_path):
    plain = tmp_path / "plain"
    plain.mkdir()
    env = {
        **os.environ,
        "DATA_MOUNT": str(plain),
        "DATABASE_URL": f"sqlite+aiosqlite:///{tmp_path / 'almanac.db'}",
    }

    result = subprocess.run(
        [sys.executable, "-m", "almanac.migrate"],
        env=env, cwd=tmp_path, capture_output=True, text=True, check=False,
    )

    assert result.returncode == 1
    assert "is not a mounted volume: refusing to start on an empty database" in result.stderr
    assert not (tmp_path / "almanac.db").exists()


def test_a_database_file_without_a_revision_is_copied_before_the_upgrade(paths):
    database, backups = paths
    sqlite3.connect(database).close()  # пустой файл: версии миграций в нём нет
    with sqlite3.connect(database) as connection:
        connection.execute("create table marker (note text)")
        connection.execute("insert into marker values ('до первой миграции')")

    # Такая база создана до миграций: `0001` создаст таблицы, а `marker` остаётся рядом.
    # Копия обязана появиться раньше, чем что-либо тронуто.
    assert migrate.main() == 0

    with sqlite3.connect(backups / "pre-0001.db") as connection:
        assert connection.execute("select note from marker").fetchall() == [("до первой миграции",)]
        assert "alembic_version" not in _tables(backups / "pre-0001.db")
    assert _version(database) == "0001"
