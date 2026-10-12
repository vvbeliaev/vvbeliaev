"""Руководство, которое читает каждая модель, не должно расходиться с кодом:
инструменты, типы страниц и отображения, которые оно называет, существуют."""

import re

import pytest
from fastmcp import Client

from almanac import schema, tree
from almanac.api.shapes import GuideOut
from almanac.app import create_app
from almanac.identity import acting

# Инструменты, о которых руководство говорит прямо: пропал один из них из текста — тест напомнит проверить смысл.
EXPECTED = {"note", "grep", "edit", "write", "read", "move", "dismiss", "item_add", "items", "ls"}
# Верхние каталоги дерева: имя с косой чертой на конце, но не тип страницы.
TREE_DIRS = {"pages", "facts", "items", "views"}
SPAN = re.compile(r"`([^`\n]+)`")
# Похоже на инструмент: вызов `ls("pages")` или имя через подчёркивание `item_add`.
TOOLISH = re.compile(r"([a-z][a-z_]*)(\(.*\))?")
PAGE_FILE = re.compile(r"pages/([a-z0-9-]+)/[a-z0-9-]+\.md")
PAGE_DIR = re.compile(r"(?:pages/)?([a-z0-9-]+)/")
LINK = re.compile(r"\[\[([a-z0-9-]+)/[a-z0-9-]+(?:\|[^\]]*)?\]\]")
VIEW = re.compile(r"views/[a-z0-9-]+\.md")


@pytest.fixture
def guide(settings) -> str:
    return schema.load(settings.schema_dir).guide


@pytest.fixture
def spans(guide) -> list[str]:
    return SPAN.findall(guide)


@pytest.fixture
async def tools(db, settings, now) -> set[str]:
    """Инструменты MCP без Code Mode: те, что модель вызывает по имени."""
    acting.set("claude-test")
    plain = settings.model_copy(update={"mcp_code_mode": False})
    async with Client(create_app(plain, db=db).state.mcp) as client:
        return {tool.name for tool in await client.list_tools()}


def _tool_names(spans: list[str]) -> set[str]:
    found = set()
    for span in spans:
        match = TOOLISH.fullmatch(span)
        if match and (match.group(2) or "_" in match.group(1)):
            found.add(match.group(1))
    return found


def _page_types(spans: list[str]) -> set[str]:
    found = set()
    for span in spans:
        for pattern in (PAGE_FILE, LINK):
            found.update(pattern.findall(span))
        directory = PAGE_DIR.fullmatch(span)
        if directory and directory.group(1) not in TREE_DIRS:
            found.add(directory.group(1))
    return found


def test_the_guide_names_the_tools_it_relies_on(spans):
    plain = {span for span in spans if re.fullmatch(r"[a-z_]+", span)}
    called = {match.group(1) for span in spans if (match := TOOLISH.fullmatch(span)) and match.group(2)}
    assert EXPECTED <= plain | called


async def test_every_tool_the_guide_names_exists(spans, tools):
    assert EXPECTED <= tools
    # Поля ответа самого руководства (`day_start`) пишутся так же, как имена инструментов.
    assert _tool_names(spans) - set(GuideOut.model_fields) <= tools


def test_every_page_type_the_guide_names_is_in_the_schema(spans, settings):
    types = set(schema.load(settings.schema_dir).types)
    named = _page_types(spans)
    assert {"projects", "ideas", "people"} <= named
    assert named <= types, named - types


def test_every_view_the_guide_names_exists(guide):
    assert set(VIEW.findall(guide)) <= set(tree.VIEWS)

