from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# Ключ рекомендательного замка Postgres, один на всю базу. Значение произвольное: слово «almanac» байтами.
WRITE_LOCK_KEY = int.from_bytes(b"almanac")
# Замок общий для процессов, и один зависший писатель остановил бы всех. Поэтому два срока, в
# миллисекундах: ждущий замка получает ошибку, а не висит; соединение, застывшее посреди
# транзакции, база закрывает сама — и замок вместе с ним.
SESSION_LIMITS = {"lock_timeout": "10000", "idle_in_transaction_session_timeout": "60000"}


class Database:
    """Движок, фабрика сессий и замок записи.

    Писатель один на базу, а не на процесс: каждая запись первым запросом берёт замок уровня
    транзакции, и второй писатель ждёт, пока первый не закоммитит или не откатится. Поэтому
    проверка версии и сама запись не расходятся, даже когда в базу пишут два процесса —
    сервер и локальная дверь MCP. Замок снимает сама база в конце транзакции: оборвавшийся
    процесс его не удержит.
    """

    def __init__(self, url: str) -> None:
        # `pool_pre_ping`: база перезапустилась или машина проснулась — мёртвое соединение из пула
        # заменяется молча, а не роняет первый же запрос.
        self.engine = create_async_engine(
            url, pool_pre_ping=True, connect_args={"server_settings": SESSION_LIMITS}
        )
        self.sessions = async_sessionmaker(self.engine, expire_on_commit=False)

    async def dispose(self) -> None:
        await self.engine.dispose()

    @asynccontextmanager
    async def read(self) -> AsyncIterator[AsyncSession]:
        async with self.sessions() as session:
            yield session

    @asynccontextmanager
    async def write(self) -> AsyncIterator[AsyncSession]:
        """Одна транзакция: вышли без исключения — коммит, с исключением — ничего не записано."""
        async with self.sessions() as session:
            # Замок первым запросом: всё, что код прочтёт дальше, он читает уже после чужого коммита.
            await session.execute(text("select pg_advisory_xact_lock(:key)"), {"key": WRITE_LOCK_KEY})
            yield session
            await session.commit()
