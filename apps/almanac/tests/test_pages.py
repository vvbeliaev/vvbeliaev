import asyncio
import time

import pytest
from sqlalchemy import select

from almanac.errors import Conflict, NotFound, Refused
from almanac.models import Journal, RevisionFact
from almanac.store import pages
from almanac.store.source import Source

TYPES = {"people", "areas", "topics", "ideas"}
ANNA = "pages/people/anna.md"


async def _write(db, **over):
    args = {
        "client": "claude",
        "types": TYPES,
        "path": ANNA,
        "title": "Анна Петрова",
        "description": "Подруга из Берлина",
        "body": "Живёт в Берлине.\n",
        "aliases": ["Аня"],
        "source": Source(said="Аня переехала в Берлин"),
        "reason": "новый человек",
    }
    args.update(over)
    async with db.write() as session:
        return await pages.write(session, **args)


async def _edit(db, **over):
    args = {
        "client": "claude",
        "path": ANNA,
        "old": "Берлине",
        "new": "Мюнхене",
        "rev": 1,
        "source": Source(restructure=True),
        "reason": "правка",
    }
    args.update(over)
    async with db.write() as session:
        return await pages.edit(session, **args)


async def test_create_page(db, now):
    done = await _write(db)
    assert (done.path, done.rev, done.warnings) == (ANNA, 1, [])
    assert len(done.facts) == 1
    async with db.read() as session:
        page = await pages.get(session, ANNA)
        revision = await pages.revision(session, ANNA, 1)
        cited = (await session.scalars(select(RevisionFact.fact_id))).all()
        ops = [entry.op for entry in (await session.scalars(select(Journal).order_by(Journal.id))).all()]
    assert (page.title, page.aliases, page.updated_at) == ("Анна Петрова", ["Аня"], now)
    assert (revision.body, revision.reason, revision.deleted) == ("Живёт в Берлине.\n", "новый человек", False)
    assert list(cited) == done.facts
    assert ops == ["note", "write"]


async def test_create_needs_a_source(db, now):
    for source in (Source(), Source(restructure=True)):
        with pytest.raises(Refused, match="name the source"):
            await _write(db, source=source)


async def test_replace_needs_current_rev(db, now):
    await _write(db)
    with pytest.raises(Conflict, match="rev 1"):
        await _write(db, body="Новый текст.\n")
    with pytest.raises(Conflict, match="current rev is 1"):
        await _write(db, body="Новый текст.\n", rev=7)
    done = await _write(db, body="Новый текст.\n", rev=1, source=Source(restructure=True), reason="переписано")
    assert (done.rev, done.facts) == (2, [])


async def test_rev_on_missing_page_is_refused(db, now):
    with pytest.raises(Refused, match="omit `rev`"):
        await _write(db, rev=1)


@pytest.mark.parametrize(
    "title, aliases, named",
    [
        ("Аня", [], "Аня"),
        ("Анна П.", ["аня"], "Аня"),
        ("АННА ПЕТРОВА", [], "Анна Петрова"),
    ],
)
async def test_duplicate_name_points_at_existing_page(db, now, title, aliases, named):
    await _write(db)
    with pytest.raises(Refused) as refusal:
        await _write(db, path="pages/people/anya.md", title=title, aliases=aliases)
    assert ANNA in str(refusal.value)
    assert f'"{named}"' in str(refusal.value)


async def test_yo_and_e_are_the_same_name(db, now):
    await _write(db, title="Алёна", aliases=[])
    with pytest.raises(Refused, match="already has"):
        await _write(db, path="pages/people/alena.md", title="Алена", aliases=[])


async def test_edit_replaces_one_fragment(db, now):
    await _write(db, body="Живёт в Берлине. Работает в банке.\n")
    done = await _edit(db, old="в банке", new="в музее", source=Source(said="Аня ушла из банка в музей"))
    async with db.read() as session:
        page = await pages.get(session, ANNA)
        first = await pages.revision(session, ANNA, 1)
    assert (done.rev, len(done.facts)) == (2, 1)
    assert page.body == "Живёт в Берлине. Работает в музее.\n"
    assert first.body == "Живёт в Берлине. Работает в банке.\n"


@pytest.mark.parametrize("old, message", [("в Гамбурге", "not found"), ("е", "occurs 2 times")])
async def test_edit_refuses_ambiguous_fragment(db, now, old, message):
    await _write(db)
    with pytest.raises(Refused, match=message):
        await _edit(db, old=old)


async def test_edit_checks_rev_and_source(db, now):
    await _write(db)
    with pytest.raises(Conflict, match="current rev is 1"):
        await _edit(db, rev=3)
    with pytest.raises(Refused, match="restructure"):
        await _edit(db, source=Source())


async def test_remove_then_recreate(db, now):
    await _write(db)
    async with db.write() as session:
        gone = await pages.remove(session, client="claude", path=ANNA, rev=1, reason="ошибка")
    assert gone.rev == 2
    async with db.read() as session:
        with pytest.raises(NotFound):
            await pages.get(session, ANNA)
        history = await pages.history(session, ANNA)
    assert [(row.rev, row.deleted) for row in history] == [(2, True), (1, False)]
    back = await _write(db)
    assert back.rev == 3


async def test_broken_link_is_a_warning(db, now):
    done = await _write(db, body="Дружит с [[people/boris]] и [[people/anna|собой]].\n")
    assert done.warnings == ["broken link: pages/people/boris.md"]


async def test_backlinks(db, now):
    boris = "pages/people/boris.md"
    await _write(db)
    await _write(
        db, path=boris, title="Борис", aliases=[], description="Коллега",
        body="Знает [[people/anna]].\n", source=Source(said="Борис знает Аню"),
    )
    async with db.read() as session:
        assert await pages.backlinks(session, ANNA) == [boris]
        assert await pages.backlinks(session, boris) == []


@pytest.mark.parametrize(
    "over, message",
    [
        ({"path": "pages/pets/rex.md"}, "unknown page type"),
        ({"description": ""}, "description is empty"),
        ({"description": "две\nстроки"}, "one line"),
        ({"reason": ""}, "reason is empty"),
        ({"body": "карта 4111 1111 1111 1111"}, "looks like a secret"),
    ],
)
async def test_write_refuses(db, now, over, message):
    with pytest.raises(Refused, match=message):
        await _write(db, **over)


async def test_history_of_unknown_page(db, now):
    async with db.read() as session:
        with pytest.raises(NotFound):
            await pages.history(session, ANNA)


def test_links_are_found_with_and_without_label():
    assert pages.links("см. [[people/anna]] и [[people/anna|Аня]], [[topics/berlin|Берлин]]") == [
        "pages/people/anna.md",
        "pages/topics/berlin.md",
    ]
    assert pages.links("[[people/anna|Аня]]") == ["pages/people/anna.md"]


def test_links_do_not_slow_down_on_a_crafted_body():
    started = time.perf_counter()
    assert pages.links("[[a/b|" * 16000) == []
    assert time.perf_counter() - started < 1.0


async def test_two_edits_at_the_same_rev_one_wins(db, now):
    await _write(db)
    results = await asyncio.gather(
        _edit(db, old="Берлине", new="Мюнхене"),
        _edit(db, old="Берлине", new="Гамбурге"),
        return_exceptions=True,
    )
    failed = [result for result in results if isinstance(result, BaseException)]
    won = [result for result in results if not isinstance(result, BaseException)]
    assert len(won) == 1 and won[0].rev == 2
    assert len(failed) == 1 and isinstance(failed[0], Conflict)
    async with db.read() as session:
        page = await pages.get(session, ANNA)
        revisions = await pages.history(session, ANNA)
    assert page.rev == 2
    assert [revision.rev for revision in revisions] == [2, 1]


async def test_edit_refuses_a_secret_in_new(db, now):
    await _write(db)
    with pytest.raises(Refused, match="looks like a secret"):
        await _edit(db, new="ключ " + "sk-" + "a" * 24)
    async with db.read() as session:
        page = await pages.get(session, ANNA)
    assert (page.rev, page.body) == (1, "Живёт в Берлине.\n")


SECRET_REASON = "ключ " + "sk-" + "a" * 24


async def test_reason_with_a_secret_is_refused_everywhere(db, now):
    await _write(db)
    with pytest.raises(Refused, match="looks like a secret"):
        await _write(db, reason=SECRET_REASON, rev=1, body="Новый текст.\n")
    with pytest.raises(Refused, match="looks like a secret"):
        await _edit(db, reason=SECRET_REASON)
    with pytest.raises(Refused, match="looks like a secret"):
        async with db.write() as session:
            await pages.remove(session, client="claude", path=ANNA, rev=1, reason=SECRET_REASON)
    async with db.read() as session:
        page = await pages.get(session, ANNA)
        revisions = await pages.history(session, ANNA)
    assert (page.rev, len(revisions)) == (1, 1)


@pytest.mark.parametrize("rev", [0, -1, 2**31, 2**63, 10**30])
async def test_revision_number_no_column_can_hold_is_simply_not_found(db, now, rev):
    await _write(db)
    async with db.read() as session:
        with pytest.raises(NotFound, match="has no rev"):
            await pages.revision(session, ANNA, rev)
