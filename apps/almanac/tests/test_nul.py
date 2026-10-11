"""Нулевой символ: Postgres не хранит его в тексте, и без отказа на входе ручка отдала бы 500."""

import pytest
from sqlalchemy import func, select

from almanac.models import Fact, Journal, Page

NUL = "\x00"
PAGE = {
    "path": "pages/people/anna.md",
    "title": "Анна",
    "description": "Подруга",
    "body": "Живёт в Берлине.\n",
    "said": "Аня переехала в Берлин",
    "reason": "новый человек",
}
ITEM = {"kind": "task", "title": "Купить молоко", "said": "молоко кончилось", "reason": "покупка"}


def _where(response):
    assert response.status_code == 422, response.text
    assert "NUL" in response.json()["detail"]


@pytest.mark.parametrize(
    ("method", "url", "body"),
    [
        ("POST", "/api/facts", {"text": f"купить{NUL}лампочки"}),
        ("POST", "/api/facts", {"text": "купить лампочки", "url": f"https://example.org/{NUL}"}),
        ("PUT", "/api/pages", {**PAGE, "body": f"текст{NUL}"}),
        ("PUT", "/api/pages", {**PAGE, "title": f"Ан{NUL}на"}),
        ("PUT", "/api/pages", {**PAGE, "aliases": ["Аня", f"А{NUL}"]}),  # вложенный список
        ("PUT", "/api/pages", {**PAGE, "said": f"сказал{NUL}"}),
        ("POST", "/api/items", {**ITEM, "note": f"две{NUL}пачки"}),
        ("POST", "/api/items", {**ITEM, "remind": [f"PT1H{NUL}"]}),
        ("POST", "/api/pages/remove", {"path": "pages/people/anna.md", "rev": 1, "reason": f"ошибка{NUL}"}),
    ],
)
async def test_body_with_a_nul_is_refused_before_it_reaches_the_database(api, db, method, url, body):
    _where(await api.request(method, url, json=body))

    async with db.read() as session:
        stored = [await session.scalar(select(func.count()).select_from(table)) for table in (Fact, Page, Journal)]
    assert stored == [0, 0, 0]


@pytest.mark.parametrize(
    ("method", "url"),
    [
        ("GET", "/api/file?path=pages/people/anna.md%00"),
        ("GET", "/api/tree?path=pages%00"),
        ("GET", "/api/items?list=shopping%00"),
        ("GET", "/api/items?page=pages/people/anna.md%00"),
        ("GET", "/api/pages/history?path=pages/people/anna.md%00"),
        ("POST", "/api/facts/f_abcdefgh%00/dismiss"),  # параметр пути
        ("PATCH", "/api/items/i_abcdefgh%00"),
    ],
)
async def test_address_with_a_nul_is_refused(api, method, url):
    # Тело на ручках с телом верное: отказ именно за адрес.
    _where(await api.request(method, url, json={"reason": "r", "rev": 1}))


async def test_a_stranger_gets_401_before_anything_else(anon):
    assert (await anon.post("/api/facts", json={"text": f"a{NUL}b"})).status_code == 401


async def test_the_six_characters_backslash_u0000_are_plain_text(api):
    # В JSON это `\\u0000`: обратная косая и четыре цифры. Нулевого символа тут нет.
    response = await api.post("/api/facts", json={"text": r"в JSON пишут \u0000"})
    assert response.status_code == 200
    assert response.json()["text"] == r"в JSON пишут \u0000"


async def test_the_refusal_reaches_the_model_through_the_mcp_door(db, settings, now):
    from fastmcp import Client
    from fastmcp.exceptions import ToolError

    from almanac.app import create_app
    from almanac.identity import acting

    acting.set("claude-test")
    plain = settings.model_copy(update={"mcp_code_mode": False})
    async with Client(create_app(plain, db=db).state.mcp) as client:
        with pytest.raises(ToolError, match="NUL"):
            await client.call_tool("note", {"text": f"купить{NUL}лампочки"})
