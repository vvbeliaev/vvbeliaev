"""Проекты: тип страницы и страница, которая показывает привязанные к ней дела."""

from datetime import date, datetime

from almanac import schema, tree
from almanac.store import items, pages
from almanac.store.source import Source

TZ = "Europe/Berlin"
PROJECT = "pages/projects/garden.md"
OTHER = "pages/projects/kitchen.md"


async def _page(db, ctx, path, **over):
    args = {
        "client": "claude", "types": ctx.schema.types, "path": path, "title": "Огород",
        "description": "Грядки на даче", "body": "Что сажаем и когда.\n",
        "source": Source(said="завожу огород"), "reason": "новый проект",
    }
    args.update(over)
    async with db.write() as session:
        return await pages.write(session, **args)


async def _item(db, **over):
    args = {
        "client": "claude", "owner_tz": TZ, "kind": "task", "title": "Купить семена",
        "source": Source(said="надо купить семена"), "reason": "дело",
    }
    args.update(over)
    async with db.write() as session:
        return await items.add(session, **args)


async def _read(db, ctx, path, rev=None):
    async with db.read() as session:
        return await tree.read(session, ctx, path, rev)


def test_projects_is_a_page_type_between_areas_and_topics(settings):
    types = list(schema.load(settings.schema_dir).types)
    assert types.index("areas") < types.index("projects") < types.index("topics")
    assert "outcome" in schema.load(settings.schema_dir).types["projects"]


async def test_a_page_lists_its_open_items_in_agenda_order(db, ctx, now):
    await _page(db, ctx, PROJECT)
    late = await _item(db, title="Собрать урожай", due=date(2026, 11, 1), page=PROJECT)
    undated = await _item(db, title="Подумать о теплице", page=PROJECT)
    visit = await _item(
        db, kind="event", title="Приехать на дачу", at=datetime(2026, 10, 17, 9, 0), page=PROJECT
    )
    soon = await _item(db, title="Вскопать грядки", due=date(2026, 10, 14), page=PROJECT)
    found = await _read(db, ctx, PROJECT)
    assert found.items == [tree.render_item(item) for item in (soon, visit, late, undated)]
    assert all(f"page:{PROJECT}" in line for line in found.items)


async def test_a_page_lists_only_open_items_that_are_its_own(db, ctx, now):
    await _page(db, ctx, PROJECT)
    await _page(db, ctx, OTHER, title="Кухня", description="Ремонт кухни", source=Source(said="ремонт кухни"))
    mine = await _item(db, title="Купить семена", page=PROJECT)
    done = await _item(db, title="Купить лопату", page=PROJECT)
    dropped = await _item(db, title="Купить шланг", page=PROJECT)
    await _item(db, title="Выбрать плитку", page=OTHER)
    await _item(db, title="Без страницы")
    async with db.write() as session:
        await items.update(
            session, client="claude", owner_tz=TZ, item_id=done.id, rev=1, changes={"status": "done"}, reason="куплено"
        )
        await items.update(
            session, client="claude", owner_tz=TZ, item_id=dropped.id, rev=1,
            changes={"status": "cancelled"}, reason="не нужно",
        )
    assert (await _read(db, ctx, PROJECT)).items == [tree.render_item(mine)]


async def test_a_page_without_items_has_an_empty_list(db, ctx, now):
    await _page(db, ctx, PROJECT)
    assert (await _read(db, ctx, PROJECT)).items == []


async def test_only_a_live_page_has_items(db, ctx, now):
    await _page(db, ctx, PROJECT)
    await _item(db, title="Купить семена", page=PROJECT)
    assert (await _read(db, ctx, PROJECT, rev=1)).items is None
    for path in ("views/week.md", "views/inbox.md", "items/tasks.md", "guide.md"):
        assert (await _read(db, ctx, path)).items is None, path


async def test_the_api_answers_with_items_for_a_live_page_only(api):
    page = {
        "path": PROJECT, "title": "Огород", "description": "Грядки на даче", "body": "Что сажаем.\n",
        "said": "завожу огород", "reason": "новый проект",
    }
    assert (await api.put("/api/pages", json=page)).status_code == 200
    await api.post(
        "/api/items",
        json={"kind": "task", "title": "Купить семена", "page": PROJECT, "due": "2026-10-14",
              "said": "надо купить семена", "reason": "дело"},
    )
    current = (await api.get("/api/file", params={"path": PROJECT})).json()
    assert len(current["items"]) == 1
    assert current["items"][0].startswith("- [ ] Купить семена  due:2026-10-14  page:" + PROJECT)
    old = (await api.get("/api/file", params={"path": PROJECT, "rev": 1})).json()
    assert old["items"] is None
    view = (await api.get("/api/file", params={"path": "views/week.md"})).json()
    assert view["items"] is None
