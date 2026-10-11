from datetime import UTC, datetime

import pytest
from httpx import ASGITransport, AsyncClient

from almanac import clock
from almanac.auth import owner
from almanac.config import Settings
from almanac.db import Database
from almanac.identity import Caller, caller

PASSWORD = "correct horse battery"
PASSWORD_HASH = owner.hash_password(PASSWORD)


@pytest.fixture
async def db(tmp_path):
    database = Database(f"sqlite+aiosqlite:///{tmp_path / 'test.db'}")
    await database.create_all()
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
def settings():
    return Settings(_env_file=None, owner_tz="Europe/Berlin", owner_password_hash=PASSWORD_HASH)


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
