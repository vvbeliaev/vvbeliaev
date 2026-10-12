"""Перенос страницы: новый путь, история с ней, ссылки и дела следом, одна запись в журнале."""

import pytest
from sqlalchemy import select

from almanac import tree
from almanac.errors import Conflict, NotFound, Refused
from almanac.models import Item, Journal, Page, PageRevision, RevisionFact
from almanac.store import items, pages
from almanac.store.source import Source

TYPES = {"people", "areas", "topics", "ideas", "projects"}
TZ = "Europe/Berlin"
IDEA = "pages/ideas/garden.md"
PROJECT = "pages/projects/garden.md"
ANNA = "pages/people/anna.md"
BORIS = "pages/people/boris.md"
LINK_REASON = f"link follows move: {IDEA} -> {PROJECT}"


async def _write(db, path=IDEA, **over):
    args = {
        "client": "claude", "types": TYPES, "path": path, "title": "Огород",
        "description": "Грядки на даче", "body": "Что сажаем и когда.\n",
        "source": Source(said="думаю про огород"), "reason": "новая идея",
    }
    args.update(over)
    async with db.write() as session:
        return await pages.write(session, **args)


async def _person(db, path, title, body):
    return await _write(
        db, path, title=title, description=f"{title} с дачи", body=body, source=Source(said=f"{title} знает про огород")
    )


async def _move(db, path=IDEA, to=PROJECT, rev=1, **over):
    args = {"client": "claude", "types": TYPES, "path": path, "to": to, "rev": rev, "reason": "стало делом"}
    args.update(over)
    async with db.write() as session:
        return await pages.move(session, **args)


async def _page(db, path):
    async with db.read() as session:
        return await pages.get(session, path)


async def _history(db, path):
    async with db.read() as session:
        return await pages.history(session, path)


async def _journal(db, op):
    async with db.read() as session:
        return list((await session.scalars(select(Journal).where(Journal.op == op).order_by(Journal.id))).all())


async def test_a_page_is_renamed_within_its_type(db, now):
    await _write(db, "pages/topics/garden-plan.md", title="План огорода")
    moved = await _move(db, "pages/topics/garden-plan.md", "pages/topics/garden-beds.md", reason="имя точнее")
    assert (moved.path, moved.rev, moved.relinked) == ("pages/topics/garden-beds.md", 2, [])
    page = await _page(db, "pages/topics/garden-beds.md")
    assert (page.title, page.description, page.body, page.rev) == ("План огорода", "Грядки на даче", "Что сажаем и когда.\n", 2)
    with pytest.raises(NotFound):
        await _page(db, "pages/topics/garden-plan.md")


async def test_an_idea_becomes_a_project(db, now):
    await _write(db)
    moved = await _move(db)
    assert (moved.path, moved.rev) == (PROJECT, 2)
    assert (await _page(db, PROJECT)).aliases == []
    with pytest.raises(NotFound):
        await _page(db, IDEA)


async def test_aliases_and_creation_time_come_along(db, now):
    await _write(db, aliases=["Дача", "Грядки"])
    before = await _page(db, IDEA)
    await _move(db)
    page = await _page(db, PROJECT)
    assert page.aliases == ["Дача", "Грядки"]
    assert (page.created_at, page.deleted_at) == (before.created_at, None)


async def test_history_follows_the_page_and_the_old_path_is_gone(db, now):
    first = await _write(db)
    async with db.write() as session:
        await pages.edit(
            session, client="claude", path=IDEA, old="сажаем", new="выращиваем", rev=1,
            source=Source(restructure=True), reason="точнее",
        )
    await _move(db, rev=2, reason="стало делом")
    revisions = await _history(db, PROJECT)
    assert [(row.rev, row.reason, row.deleted) for row in revisions] == [
        (3, "стало делом", False), (2, "точнее", False), (1, "новая идея", False),
    ]
    assert revisions[0].body == revisions[1].body  # перенос не меняет текст
    assert revisions[0].client == "claude"
    async with db.read() as session:
        cited = [(row.path, row.rev) for row in (await session.scalars(select(RevisionFact))).all()]
        assert (await session.scalars(select(PageRevision).where(PageRevision.path == IDEA))).first() is None
        assert await session.get(Page, IDEA) is None
        assert await session.get(PageRevision, (PROJECT, 1)) is not None
    assert cited == [(PROJECT, 1)]  # факты первой ревизии пошли за страницей, у переноса фактов нет
    assert first.facts
    with pytest.raises(NotFound):
        await _history(db, IDEA)


async def test_an_old_revision_is_read_at_the_new_path(db, ctx, now):
    await _write(db)
    await _move(db)
    async with db.read() as session:
        first = await tree.read(session, ctx, PROJECT, rev=1)
        with pytest.raises(NotFound):
            await tree.read(session, ctx, IDEA)
    assert "Что сажаем и когда." in first.text


async def test_the_old_path_is_free_again(db, now):
    await _write(db)
    await _move(db)
    again = await _write(db, title="Другой огород", description="Совсем другое", source=Source(said="новый огород"))
    assert again.rev == 1
    assert [row.rev for row in await _history(db, IDEA)] == [1]
    assert [row.rev for row in await _history(db, PROJECT)] == [2, 1]


async def test_links_with_and_without_a_label_follow_the_page(db, now):
    await _write(db, body="Начать с [[ideas/garden]], вернуться к [[ideas/garden|огороду]].\n")
    await _person(
        db, ANNA, "Анна",
        "Помогает: [[ideas/garden]] и [[ideas/garden|огород]]. Рядом [[ideas/garden-bed]] и [[topics/ideas/garden]].\n",
    )
    await _person(db, BORIS, "Борис", "Про огород не знает.\n")
    moved = await _move(db)
    assert moved.relinked == [ANNA]
    anna = await _page(db, ANNA)
    assert anna.body == (
        "Помогает: [[projects/garden]] и [[projects/garden|огород]]. "
        "Рядом [[ideas/garden-bed]] и [[topics/ideas/garden]].\n"
    )
    assert anna.rev == 2
    assert (await _page(db, BORIS)).rev == 1
    own = await _page(db, PROJECT)
    assert own.body == "Начать с [[projects/garden]], вернуться к [[projects/garden|огороду]].\n"
    assert moved.rev == own.rev == 2


async def test_a_page_that_follows_gets_a_revision_without_facts(db, now):
    await _write(db)
    await _person(db, ANNA, "Анна", "Помогает: [[ideas/garden]].\n")
    await _move(db)
    revisions = await _history(db, ANNA)
    assert [(row.rev, row.reason) for row in revisions] == [(2, LINK_REASON), (1, "новая идея")]
    assert revisions[0].client == "claude"
    async with db.read() as session:
        cited = (await session.scalars(select(RevisionFact).where(RevisionFact.path == ANNA))).all()
    assert [(row.rev) for row in cited] == [1]


async def test_backlinks_after_a_move_point_at_the_new_path(db, now):
    await _write(db)
    await _person(db, ANNA, "Анна", "Помогает: [[ideas/garden]].\n")
    await _move(db)
    async with db.read() as session:
        assert await pages.backlinks(session, PROJECT) == [ANNA]
        assert await pages.backlinks(session, IDEA) == []


async def test_attached_items_follow_the_page(db, ctx, now):
    await _write(db)
    async with db.write() as session:
        task = await items.add(
            session, client="claude", owner_tz=TZ, kind="task", title="Купить семена", page=IDEA,
            source=Source(said="надо семена"), reason="дело",
        )
        closed = await items.add(
            session, client="claude", owner_tz=TZ, kind="task", title="Купить лопату", page=IDEA,
            source=Source(said="надо лопату"), reason="дело",
        )
        await items.update(
            session, client="claude", owner_tz=TZ, item_id=closed.id, rev=1, changes={"status": "done"},
            reason="куплено",
        )
        stranger = await items.add(
            session, client="claude", owner_tz=TZ, kind="task", title="Чужое", source=Source(said="чужое"),
            reason="дело",
        )
    await _move(db)
    async with db.read() as session:
        moved = await session.get(Item, task.id)
        done = await session.get(Item, closed.id)
        other = await session.get(Item, stranger.id)
        shown = (await tree.read(session, ctx, PROJECT)).items
    assert (moved.page, moved.rev) == (PROJECT, 2)
    assert (done.page, done.rev) == (PROJECT, 3)
    assert (other.page, other.rev) == (None, 1)
    assert shown == [tree.render_item(moved)]
    assert f"page:{PROJECT}" in shown[0]


async def test_the_move_is_one_journal_row(db, now):
    await _write(db)
    await _person(db, ANNA, "Анна", "Помогает: [[ideas/garden]].\n")
    async with db.write() as session:
        await items.add(
            session, client="claude", owner_tz=TZ, kind="task", title="Купить семена", page=IDEA,
            source=Source(said="надо семена"), reason="дело",
        )
    await _move(db, client="claude-web", reason="стало делом")
    rows = await _journal(db, "move")
    assert len(rows) == 1
    assert (rows[0].client, rows[0].target, rows[0].reason) == ("claude-web", PROJECT, "стало делом")
    assert rows[0].detail == {"from": IDEA, "rev": 2, "relinked": [ANNA]}
    follows = [row for row in await _journal(db, "edit") if row.target == ANNA]
    assert len(follows) == 1
    assert (follows[0].reason, follows[0].detail) == (LINK_REASON, {"rev": 2, "facts": []})
    assert await _journal(db, "item_update") == []  # дела журнал не множат


async def test_a_stale_rev_is_refused_and_nothing_moves(db, now):
    await _write(db)
    with pytest.raises(Conflict, match="current rev is 1"):
        await _move(db, rev=4)
    assert (await _page(db, IDEA)).rev == 1
    assert await _journal(db, "move") == []


@pytest.mark.parametrize(
    "to, match",
    [
        (IDEA, "same"),
        ("pages/pets/garden.md", "unknown page type"),
        ("projects/garden.md", "bad page path"),
        ("pages/projects/Garden Beds.md", "bad page path"),
    ],
)
async def test_a_bad_target_is_refused_with_the_fix(db, now, to, match):
    await _write(db)
    with pytest.raises(Refused, match=match):
        await _move(db, to=to)
    assert (await _page(db, IDEA)).rev == 1
    assert await _journal(db, "move") == []


async def test_a_target_taken_by_a_live_page_is_a_conflict(db, now):
    await _write(db)
    await _write(db, PROJECT, title="Другой огород", description="Занято", source=Source(said="другой огород"))
    with pytest.raises(Conflict, match="pick another slug"):
        await _move(db)
    assert (await _page(db, IDEA)).rev == 1
    assert (await _page(db, PROJECT)).title == "Другой огород"


async def test_a_target_taken_by_a_removed_page_is_refused(db, now):
    await _write(db)
    await _write(db, PROJECT, title="Старый огород", description="Был", source=Source(said="старый огород"))
    async with db.write() as session:
        await pages.remove(session, client="claude", path=PROJECT, rev=1, reason="не нужен")
    with pytest.raises(Refused, match="removed page.*pick another slug"):
        await _move(db)
    assert (await _page(db, IDEA)).rev == 1
    assert [row.rev for row in await _history(db, PROJECT)] == [2, 1]


async def test_a_missing_or_removed_source_page_is_not_found(db, now):
    with pytest.raises(NotFound):
        await _move(db)
    await _write(db)
    async with db.write() as session:
        await pages.remove(session, client="claude", path=IDEA, rev=1, reason="ошибка")
    with pytest.raises(NotFound):
        await _move(db, rev=2)


async def test_a_secret_in_the_reason_is_refused(db, now):
    await _write(db)
    with pytest.raises(Refused, match="looks like a secret"):
        await _move(db, reason="ключ " + "sk-" + "a" * 24)
    assert (await _page(db, IDEA)).rev == 1


async def test_a_move_that_would_overflow_a_linking_page_is_refused_whole(db, now):
    await _write(db)
    crowded = "[[ideas/garden]]" * 6200  # ~99 тысяч знаков: после замены на более длинный путь не поместится
    await _person(db, ANNA, "Анна", crowded)
    with pytest.raises(Refused, match=r"pages/people/anna\.md would be longer"):
        await _move(db)
    assert (await _page(db, IDEA)).rev == 1
    assert (await _page(db, ANNA)).rev == 1
    assert await _journal(db, "move") == []
