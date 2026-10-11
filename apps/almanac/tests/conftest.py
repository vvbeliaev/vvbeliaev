import asyncio
import os
import secrets
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path

import asyncpg
import pytest
from alembic import command
from alembic.config import Config
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.engine import make_url

from almanac import clock
from almanac.auth import owner
from almanac.config import Settings
from almanac.db import Database
from almanac.identity import Caller, caller
from almanac.models import Base

# Ryuk — контейнер-уборщик testcontainers: ему нужен сокет Docker, смонтированный внутрь, а Colima этого не
# умеет. Контейнер прогона и так останавливается менеджером контекста; страховки нет только на kill -9.
# Переменная читается на импорте testcontainers, а тот импортируется внутри `pg_server`, уже после неё.
os.environ.setdefault("TESTCONTAINERS_RYUK_DISABLED", "true")

PASSWORD = "correct horse battery"
# Параметры слабее боевых (2**17), чтобы тесты шли быстро.
PASSWORD_HASH = owner.hash_password(PASSWORD, n=2**14)

PG_IMAGE = "postgres:18-alpine"
ALEMBIC_INI = Path(__file__).parents[1] / "alembic.ini"
# Все таблицы моделей: для TRUNCATE между тестами. Порядок не важен, CASCADE снимает внешние ключи.
TABLES = ", ".join(f'"{table.name}"' for table in Base.metadata.sorted_tables)


def _on_database(url: str, database: str) -> str:
    """Тот же сервер, другая база."""
    return make_url(url).set(database=database).render_as_string(hide_password=False)


def _run(work):
    """Короткая асинхронная работа из синхронной фикстуры: свой цикл событий в отдельном потоке,
    чтобы не задеть цикл pytest-asyncio."""
    with ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(asyncio.run, work).result()


async def _admin(server: str, statement: str) -> None:
    """Команда вне транзакции (`CREATE DATABASE` иначе не выполнить) от имени служебной базы сервера."""
    dsn = make_url(server).set(drivername="postgresql").render_as_string(hide_password=False)
    connection = await asyncpg.connect(dsn)
    try:
        await connection.execute(statement)
    finally:
        await connection.close()


def upgrade(url: str, revision: str = "head") -> None:
    """`alembic upgrade` на базе с этим адресом. Синхронная: `env.py` зовёт `asyncio.run`."""
    config = Config(str(ALEMBIC_INI))
    config.attributes["url"] = url
    command.upgrade(config, revision)


@pytest.fixture(autouse=True)
def _no_ambient_database(monkeypatch):
    """Адрес базы тесты берут только у своего контейнера: переменная окружения разработчика им не указ."""
    monkeypatch.delenv("DATABASE_URL", raising=False)


@pytest.fixture(scope="session")
def pg_server():
    """Единственный контейнер Postgres на прогон: адрес его служебной базы."""
    from testcontainers.community.postgres import PostgresContainer

    with PostgresContainer(PG_IMAGE, driver="asyncpg") as container:
        yield container.get_connection_url()


@pytest.fixture(scope="session")
def pg_url(pg_server) -> str:
    """База со схемой, накатанной миграциями (не `create_all`): тесты идут на той схеме, что в бою."""
    _run(_admin(pg_server, 'CREATE DATABASE "almanac_test"'))
    url = _on_database(pg_server, "almanac_test")
    upgrade(url)
    return url


@pytest.fixture
def fresh_database(pg_server):
    """Адрес новой пустой базы на том же сервере; после теста база удаляется.

    Нужна тестам, которым общая база мешает: миграциям, приложению со своим адресом, команде `revoke`."""
    name = f"almanac_{secrets.token_hex(4)}"
    _run(_admin(pg_server, f'CREATE DATABASE "{name}"'))
    try:
        yield _on_database(pg_server, name)
    finally:
        _run(_admin(pg_server, f'DROP DATABASE "{name}" WITH (FORCE)'))


@pytest.fixture
def migrated_database(fresh_database) -> str:
    """Новая база с боевой схемой: для тестов, которым нужна своя, а не общая."""
    upgrade(fresh_database)
    return fresh_database


@pytest.fixture
def migrate() -> Callable[..., None]:
    return upgrade


@pytest.fixture
async def db(pg_url):
    """Своя `Database` на тест: цикл событий у теста свой, а соединения привязаны к циклу."""
    database = Database(pg_url)
    async with database.engine.begin() as connection:
        await connection.execute(text(f"TRUNCATE {TABLES} RESTART IDENTITY CASCADE"))
    yield database
    await database.dispose()


@pytest.fixture
def now(monkeypatch):
    """Понедельник 2026-10-12, 10:00 UTC — в Берлине 12:00, летнее время до 25 октября."""
    moment = datetime(2026, 10, 12, 10, 0, tzinfo=UTC)
    monkeypatch.setattr(clock, "_now", lambda: moment)
    return moment


@pytest.fixture
def password():
    return PASSWORD


@pytest.fixture
def settings(pg_url):
    return Settings(_env_file=None, database_url=pg_url, owner_tz="Europe/Berlin", owner_password_hash=PASSWORD_HASH)


@pytest.fixture
def ctx(settings):
    from almanac import schema, tree

    return tree.Context(schema=schema.load(settings.schema_dir), owner_tz=settings.owner_tz)


@pytest.fixture
def app(db, settings, now):
    from almanac.app import create_app

    return create_app(settings, db=db)


@pytest.fixture
async def anon(app):
    """Клиент без личности: то, что видит посторонний."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client


@pytest.fixture
async def api(app):
    """Клиент с личностью `local`: тесты ядра не про вход."""
    app.dependency_overrides[caller] = lambda: Caller(client="local")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client
