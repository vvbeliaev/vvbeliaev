"""Перед стартом сервера: `python -m almanac.migrate`.

1. Том. Если задан `DATA_MOUNT`, это обязан быть смонтированный каталог: иначе контейнер
   запустился бы на пустой базе внутри собственного слоя, а данные остались бы на потерянном томе.
2. Копия. База есть и отстаёт от `head` — перед обновлением снимается `pre-<ревизия>.db`.
3. `alembic upgrade head`.

Выход с ненулевым кодом останавливает контейнер до запуска сервера.
"""

import os
import sqlite3
import sys
from contextlib import closing
from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from alembic.util.exc import CommandError
from sqlalchemy import create_engine
from sqlalchemy.engine import URL

from almanac import backup
from almanac.config import Settings

# src/almanac/migrate.py -> каталог проекта, где лежат alembic.ini и migrations.
PROJECT = Path(__file__).resolve().parents[2]


def _unmounted() -> str | None:
    path = os.environ.get("DATA_MOUNT")
    if path and not os.path.ismount(path):
        return f"DATA_MOUNT={path} is not a mounted volume: refusing to start on an empty database"
    return None


def _current_revision(database: Path) -> str | None:
    engine = create_engine(URL.create("sqlite", database=str(database)))
    try:
        with engine.connect() as connection:
            return MigrationContext.configure(connection).get_current_revision()
    finally:
        engine.dispose()


def _is_behind(script: ScriptDirectory, current: str | None, head: str) -> bool:
    """База отстаёт, если у неё нет ревизии или ревизия известна и не последняя.

    Чужую ревизию (образ откатили на старый код) не копируем: файл `pre-<head>.db` занял бы
    имя настоящей копии. `alembic upgrade` на такой базе и так упадёт с понятным текстом.
    """
    if current == head:
        return False
    if current is None:
        return True
    try:
        return script.get_revision(current) is not None
    except CommandError:
        return False


def _copy_before_upgrade(database: Path, target: Path) -> None:
    if target.exists():
        print(f"almanac.migrate: {target.name} already exists, not copying again")
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    backup.require_space(database, target.parent)
    with backup.staged_copy(target) as partial, closing(sqlite3.connect(database, isolation_level=None)) as source:
        source.execute("VACUUM INTO ?", (str(partial),))
    print(f"almanac.migrate: copied the database to {target}")


def main(config: Config | None = None) -> int:
    """Возвращает код выхода. `config` подменяют тесты; по умолчанию — `alembic.ini` проекта."""
    refusal = _unmounted()
    if refusal:
        print(refusal, file=sys.stderr)
        return 1

    config = config or Config(str(PROJECT / "alembic.ini"))
    settings = Settings()
    script = ScriptDirectory.from_config(config)
    head = script.get_current_head()
    database = backup.database_file(settings.database_url)
    copying = database is not None and settings.backup_dir is not None
    if copying and _is_behind(script, _current_revision(database), head):
        try:
            _copy_before_upgrade(database, settings.backup_dir / f"pre-{head}.db")
        except (OSError, RuntimeError, sqlite3.Error) as error:
            # Обновление без копии — ровно то, от чего копия страхует.
            print(f"almanac.migrate: cannot copy the database before migrating: {error}", file=sys.stderr)
            return 1

    command.upgrade(config, "head")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
