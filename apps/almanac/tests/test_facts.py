import pytest
from sqlalchemy import select

from almanac.errors import NotFound, Refused
from almanac.models import Fact, Item, ItemFact, Journal, RevisionFact
from almanac.store import facts
from almanac.store.source import Source, resolve


async def _note(db, text="Аня переехала в Берлин", **extra):
    async with db.write() as session:
        return await facts.add(session, client="claude", text=text, **extra)


async def test_note_stores_fact_and_journal(db, now):
    fact = await _note(db, text="  Аня переехала в Берлин  ")
    async with db.read() as session:
        stored = await session.get(Fact, fact.id)
        entries = (await session.scalars(select(Journal))).all()
    assert stored.text == "Аня переехала в Берлин"
    assert stored.origin == "said"
    assert stored.at == now
    assert [(e.op, e.target, e.client) for e in entries] == [("note", fact.id, "claude")]


@pytest.mark.parametrize(
    "extra, message",
    [
        ({"text": "   "}, "empty"),
        ({"origin": "rumor"}, "unknown origin"),
        ({"supersedes": "f_missing0"}, "does not exist"),
        ({"text": "пароль от всего " + "sk-" + "a" * 24}, "looks like a secret"),
    ],
)
async def test_note_refuses(db, now, extra, message):
    args = {"client": "claude", "text": "факт", **extra}
    with pytest.raises(Refused, match=message):
        async with db.write() as session:
            await facts.add(session, **args)


async def test_inbox_holds_facts_nothing_was_built_from(db, now):
    loose = await _note(db, text="купить лампочки")
    cited_by_page = await _note(db, text="Аня переехала")
    cited_by_item = await _note(db, text="позвонить врачу")
    old = await _note(db, text="встреча во вторник")
    new = await _note(db, text="встреча в среду", supersedes=old.id)
    closed = await _note(db, text="хороший день")
    async with db.write() as session:
        # У `item_facts.item_id` есть внешний ключ, поэтому элемент должен существовать.
        session.add(Item(
            id="i_test0001", kind="task", title="позвонить врачу", note="", remind=[], status="open",
            rev=1, created_at=now, updated_at=now,
        ))
        await session.flush()
        session.add(RevisionFact(path="pages/people/anna.md", rev=1, fact_id=cited_by_page.id))
        session.add(ItemFact(item_id="i_test0001", fact_id=cited_by_item.id))
        await facts.dismiss(session, client="claude", fact_id=closed.id, reason="дневниковая запись")
    async with db.read() as session:
        ids = {fact.id for fact in await facts.inbox(session)}
    # Часы в тесте стоят, порядок фактов одного момента не определён — сравниваем множества.
    assert ids == {loose.id, new.id}


async def test_dismiss_unknown_fact(db, now):
    with pytest.raises(NotFound):
        async with db.write() as session:
            await facts.dismiss(session, client="claude", fact_id="f_missing0", reason="нет такого")


async def test_require_reports_unknown_ids(db, now):
    fact = await _note(db)
    async with db.read() as session:
        assert await facts.require(session, [fact.id, fact.id]) == [fact.id]
        with pytest.raises(Refused, match="unknown facts: f_missing0"):
            await facts.require(session, [fact.id, "f_missing0"])


async def test_source_from_said_records_a_fact(db, now):
    async with db.write() as session:
        ids = await resolve(session, client="claude", source=Source(said="молоко кончилось"), allow_restructure=False)
    async with db.read() as session:
        fact = await session.get(Fact, ids[0])
    assert fact.text == "молоко кончилось"
    assert fact.origin == "said"


async def test_source_joins_ids_and_said(db, now):
    known = await _note(db)
    async with db.write() as session:
        ids = await resolve(
            session, client="claude", source=Source(facts=(known.id,), said="и ещё вот что"), allow_restructure=False
        )
    assert ids[0] == known.id
    assert len(ids) == 2


async def test_source_is_required(db, now):
    with pytest.raises(Refused, match="name the source") as refusal:
        async with db.write() as session:
            await resolve(session, client="claude", source=Source(), allow_restructure=True)
    assert "restructure" in str(refusal.value)

    with pytest.raises(Refused) as creation:
        async with db.write() as session:
            await resolve(session, client="claude", source=Source(restructure=True), allow_restructure=False)
    assert "restructure" not in str(creation.value)


async def test_restructure_needs_no_facts(db, now):
    async with db.write() as session:
        ids = await resolve(session, client="claude", source=Source(restructure=True), allow_restructure=True)
    assert ids == []
