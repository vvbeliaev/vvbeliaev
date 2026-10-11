import shutil
import textwrap
from datetime import UTC, datetime
from pathlib import Path

import pytest
from alembic.config import Config
from httpx import ASGITransport, AsyncClient

from almanac import clock
from almanac.auth import owner
from almanac.config import Settings
from almanac.db import Database
from almanac.identity import Caller, caller

PASSWORD = "correct horse battery"
# Параметры слабее боевых (2**17), чтобы тесты шли быстро.
PASSWORD_HASH = owner.hash_password(PASSWORD, n=2**14)


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


MIGRATIONS = Path(__file__).parents[1] / "migrations"


@pytest.fixture
def next_migration(tmp_path):
    """Конфиг Alembic с временной копией миграций и лишней ревизией 0002 над 0001.

    Тело `upgrade()` задаёт тест; в репозиторий такая ревизия не попадает.
    """

    def build(upgrade_body: str) -> Config:
        scripts = tmp_path / "migrations"
        shutil.copytree(MIGRATIONS, scripts, ignore=shutil.ignore_patterns("__pycache__"))
        header = "import sqlalchemy as sa\nfrom alembic import op\n\n"
        header += "revision = '0002'\ndown_revision = '0001'\nbranch_labels = None\ndepends_on = None\n"
        body = textwrap.indent(textwrap.dedent(upgrade_body).strip(), "    ")
        (scripts / "versions" / "0002_extra.py").write_text(f"{header}\n\ndef upgrade() -> None:\n{body}\n")
        config = Config()
        config.set_main_option("script_location", str(scripts))
        return config

    return build
