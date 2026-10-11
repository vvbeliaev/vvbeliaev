"""Снять все допуски разом: `python -m almanac.auth.revoke`.

Единственное средство против ошибочно одобренного клиента, и у него нет веб-поверхности:
команда запускается там, откуда есть доступ к базе. Удаляет все токены, коды, ожидающие согласия,
клиентов и сессии владельца. После неё каждый клиент проходит согласие заново, а браузер
владельца входит по паролю.
"""

import asyncio
import sys

from sqlalchemy import delete
from sqlalchemy.exc import DBAPIError

from almanac.config import Settings
from almanac.db import Database
from almanac.models import AuthPending, OAuthClient, OAuthCode, OAuthToken, Session

# Порядок — как в отчёте команды.
TABLES = (OAuthToken, OAuthCode, AuthPending, OAuthClient, Session)


async def revoke_all(db: Database) -> dict[str, int]:
    """Очищает пять таблиц допусков одной транзакцией; возвращает, сколько строк убрано из каждой."""
    removed: dict[str, int] = {}
    async with db.write() as session:
        for model in TABLES:
            removed[model.__tablename__] = (await session.execute(delete(model))).rowcount
    return removed


async def main() -> int:
    db = Database(Settings().database_url)
    try:
        removed = await revoke_all(db)
    except (DBAPIError, OSError) as error:  # не отвечает, не пускает, нет таблиц; пароля в этих текстах нет
        print(f"База не готова ({getattr(error, 'orig', error)}): проверьте DATABASE_URL и миграции.", file=sys.stderr)
        return 1
    finally:
        await db.dispose()
    for table, count in removed.items():
        print(f"{table}: {count}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
