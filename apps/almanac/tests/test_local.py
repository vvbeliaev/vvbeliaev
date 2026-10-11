"""Локальная дверь: настоящий процесс `python -m almanac.local` и клиент MCP по stdio."""

import sys

import pytest
from fastmcp import Client
from fastmcp.client.transports import StdioTransport
from sqlalchemy import select

from almanac import local
from almanac.config import Settings
from almanac.models import Fact, Journal


@pytest.fixture
async def door(db, pg_url, tmp_path):
    """Дверь отдельным процессом на базе теста. Рабочий каталог пустой: `.env` разработчика ей не виден."""
    transport = StdioTransport(
        command=sys.executable, args=["-m", "almanac.local"], env={"DATABASE_URL": pg_url}, cwd=str(tmp_path),
        keep_alive=False,
    )
    async with Client(transport) as client:
        yield client


async def test_the_door_is_the_same_code_mode_server(door):
    assert {tool.name for tool in await door.list_tools()} == {"search", "get_schema", "execute"}


async def test_a_write_through_the_door_lands_in_the_database_as_local(door, db):
    result = await door.call_tool(
        "execute", {"code": "return await call_tool('note', {'text': 'Купить фильтр для воды'})"}
    )
    assert not result.is_error

    async with db.read() as session:
        fact = (await session.scalars(select(Fact))).one()
        entry = (await session.scalars(select(Journal))).one()
    assert (fact.text, fact.client, fact.origin) == ("Купить фильтр для воды", "local", "said")
    assert entry.client == "local"


async def test_a_refusal_reaches_the_client_as_text_to_act_on(door, db):
    result = await door.call_tool(
        "execute", {"code": "return await call_tool('note', {'text': 'x', 'colour': 'red'})"}, raise_on_error=False
    )
    assert result.is_error
    assert "unknown parameters: colour" in result.content[0].text
    async with db.read() as session:
        assert (await session.scalars(select(Fact))).all() == []


async def test_the_door_never_starts_the_bot(monkeypatch):
    """Бот и цикл напоминаний — дело сервера: дверь собирает приложение без токена."""
    seen = {}

    class Built(Exception):
        pass

    def create_app(settings):
        seen["token"] = settings.telegram_bot_token
        raise Built

    monkeypatch.setattr(local, "create_app", create_app)
    configured = Settings(_env_file=None, telegram_bot_token="made-up", telegram_owner_chat_id=1)
    with pytest.raises(Built):
        await local.serve(configured)
    assert seen["token"] == ""
