"""Запуск цикла напоминаний и бота вместе с приложением. Сети нет: Scheduler и Telegram подменены."""

import asyncio

import pytest
from asgi_lifespan import LifespanManager

from almanac.app import create_app
from almanac.config import Settings

TOKEN = "12345678" + ":" + "x" * 35


@pytest.fixture
def started(monkeypatch):
    seen = {"built": [], "running": set(), "cancelled": []}

    class FakeScheduler:
        def __init__(self, db, messenger, **options):
            seen["built"].append((messenger, options))

        async def run(self):
            await self._forever("run")

        async def poll(self):
            await self._forever("poll")

        async def _forever(self, name):
            seen["running"].add(name)
            try:
                await asyncio.sleep(3600)
            except asyncio.CancelledError:
                seen["cancelled"].append(name)
                raise

    class FakeTelegram:
        def __init__(self, token, chat_id):
            self.token, self.chat_id = token, chat_id

    monkeypatch.setattr("almanac.app.Scheduler", FakeScheduler)
    monkeypatch.setattr("almanac.app.Telegram", FakeTelegram)
    return seen


def _settings(tmp_path, **over):
    return Settings(
        _env_file=None, database_url=f"sqlite+aiosqlite:///{tmp_path / 'life.db'}", owner_tz="Europe/Berlin",
        **over,
    )


async def _settle():
    for _ in range(5):
        await asyncio.sleep(0)


async def test_loops_start_with_the_app_and_stop_with_it(tmp_path, started):
    app = create_app(_settings(tmp_path, telegram_bot_token=TOKEN, telegram_owner_chat_id=42))
    async with LifespanManager(app):
        await _settle()
        assert started["running"] == {"run", "poll"}
        assert started["cancelled"] == []
    assert sorted(started["cancelled"]) == ["poll", "run"]
    messenger, options = started["built"][0]
    assert (messenger.token, messenger.chat_id) == (TOKEN, 42)
    assert options == {"owner_tz": "Europe/Berlin", "day_start": "09:00", "owner_chat_id": 42}


@pytest.mark.parametrize("over", [{}, {"telegram_bot_token": TOKEN}, {"telegram_owner_chat_id": 42}])
async def test_loops_stay_off_without_both_token_and_chat(tmp_path, started, over):
    app = create_app(_settings(tmp_path, **over))
    async with LifespanManager(app):
        await _settle()
    assert (started["built"], started["running"]) == ([], set())


async def test_loops_stay_off_when_tests_bring_their_own_database(db, started, tmp_path):
    app = create_app(_settings(tmp_path, telegram_bot_token=TOKEN, telegram_owner_chat_id=42), db=db)
    async with LifespanManager(app):
        await _settle()
    assert started["built"] == []


@pytest.fixture
def backups(monkeypatch):
    seen = {"started": [], "cancelled": 0}

    async def forever(db, directory):
        seen["started"].append(directory)
        try:
            await asyncio.sleep(3600)
        except asyncio.CancelledError:
            seen["cancelled"] += 1
            raise

    monkeypatch.setattr("almanac.app.backup.run", forever)
    return seen


async def test_backup_loop_runs_while_the_app_does(tmp_path, backups):
    directory = tmp_path / "copies"
    app = create_app(_settings(tmp_path, backup_dir=directory))
    async with LifespanManager(app):
        await _settle()
        assert backups["started"] == [directory]
        assert backups["cancelled"] == 0
    assert backups["cancelled"] == 1


async def test_backup_loop_stays_off_without_a_directory_or_with_a_borrowed_database(db, tmp_path, backups):
    async with LifespanManager(create_app(_settings(tmp_path))):
        await _settle()
    async with LifespanManager(create_app(_settings(tmp_path, backup_dir=tmp_path / "copies"), db=db)):
        await _settle()
    assert backups["started"] == []
