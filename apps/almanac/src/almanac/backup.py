"""Копии базы: раз в сутки целый файл рядом с данными.

Это защита от порчи и ошибочной записи, но не от потери диска: копию вне
сервера настраивает владелец отдельно.
"""

import asyncio
import logging
from pathlib import Path

from almanac.clock import utcnow
from almanac.db import Database

log = logging.getLogger(__name__)
DAY = 24 * 60 * 60


async def snapshot(db: Database, directory: Path, keep: int = 14) -> Path:
    """Согласованная копия базы одним файлом; старше `keep` последних — удаляются."""
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / f"almanac-{utcnow():%Y%m%d-%H%M%S}.db"
    async with db.engine.connect() as connection:
        autocommit = await connection.execution_options(isolation_level="AUTOCOMMIT")
        # Путь собран из настройки и даты, не из запроса: подставлять его в текст можно.
        await autocommit.exec_driver_sql(f"VACUUM INTO '{target}'")
    for old in sorted(directory.glob("almanac-*.db"))[:-keep]:
        old.unlink()
    return target


async def run(db: Database, directory: Path) -> None:
    while True:
        try:
            await snapshot(db, directory)
        except Exception:
            log.exception("backup failed")
        await asyncio.sleep(DAY)
