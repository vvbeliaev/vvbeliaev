"""Копии базы: раз в сутки целый файл рядом с данными.

Это защита от порчи и ошибочной записи, но не от потери диска: копию вне
сервера настраивает владелец отдельно.

Копия появляется под своим именем только целой: сначала пишется во временный
`*.partial`, проверяется `PRAGMA quick_check` и лишь потом переименовывается.
Оборванная запись не может стать «самой свежей копией».
"""

import asyncio
import logging
import os
import re
import shutil
import sqlite3
from collections.abc import Iterator
from contextlib import closing, contextmanager
from pathlib import Path

from sqlalchemy.engine import URL, make_url

from almanac.clock import utcnow
from almanac.db import Database

log = logging.getLogger(__name__)
DAY = 24 * 60 * 60
# Копия в `VACUUM INTO` не больше базы; запас — на журнал и округление до страниц.
SPACE_FACTOR = 1.2
DAILY = re.compile(r"almanac-\d{8}\.db")


def database_file(url: str | URL) -> Path | None:
    """Файл SQLite по адресу базы; нет файла, база в памяти или чужая СУБД — `None`."""
    parsed = make_url(url)
    if parsed.get_backend_name() != "sqlite" or not parsed.database or parsed.database == ":memory:":
        return None
    path = Path(parsed.database)
    return path if path.is_file() else None


def require_space(source: Path | None, directory: Path) -> None:
    """Не начинаем копию, которой не хватит места: полудиск хуже отсутствия копии."""
    if source is not None and shutil.disk_usage(directory).free < SPACE_FACTOR * source.stat().st_size:
        raise RuntimeError("not enough free space for a database copy")


def _quick_check(path: Path) -> None:
    # Блокирует цикл на миллисекунды раз в сутки: база личная и маленькая.
    with closing(sqlite3.connect(f"{path.as_uri()}?mode=ro", uri=True)) as connection:
        answer = connection.execute("PRAGMA quick_check").fetchall()
    if answer != [("ok",)]:
        raise RuntimeError(f"database copy failed quick_check: {answer[:3]}")


@contextmanager
def staged_copy(target: Path) -> Iterator[Path]:
    """Отдаёт имя для записи копии; целой копия становится только после проверки.

    Любой сбой, включая отмену задачи, стирает временный файл и пробрасывается дальше.
    """
    partial = target.with_name(target.name + ".partial")
    partial.unlink(missing_ok=True)  # остаток от убитого процесса не должен мешать `VACUUM INTO`
    try:
        yield partial
        _quick_check(partial)
        os.replace(partial, target)
    except BaseException:
        partial.unlink(missing_ok=True)
        raise


async def _vacuum_into(db: Database, target: Path) -> None:
    async with db.engine.connect() as connection:
        autocommit = await connection.execution_options(isolation_level="AUTOCOMMIT")
        await autocommit.exec_driver_sql("VACUUM INTO ?", (str(target),))


def _prune(directory: Path, keep: int) -> None:
    """Оставляет `keep` последних суточных копий; `pre-*.db` и всё прочее не трогает."""
    daily = sorted(path for path in directory.iterdir() if DAILY.fullmatch(path.name))
    for old in daily[:-keep]:
        old.unlink()


async def snapshot(db: Database, directory: Path, keep: int = 14) -> Path:
    """Согласованная копия базы одним файлом, одна на сутки UTC; сегодняшняя уже есть — её и возвращаем."""
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / f"almanac-{utcnow():%Y%m%d}.db"
    if target.exists():
        return target
    require_space(database_file(db.engine.url), directory)
    with staged_copy(target) as partial:
        await _vacuum_into(db, partial)
    _prune(directory, keep)
    return target


async def run(db: Database, directory: Path) -> None:
    while True:
        try:
            await snapshot(db, directory)
        except Exception:
            log.exception("backup failed")
        await asyncio.sleep(DAY)
