from datetime import date, datetime

import pytest
from sqlalchemy import select

from almanac.errors import Conflict, NotFound, Refused
from almanac.models import ItemFact, Journal
from almanac.store import items
from almanac.store.source import Source
from almanac.timeline import occur

TZ = "Europe/Berlin"
EVENING = datetime(2026, 10, 12, 18, 0)


async def _add(db, **over):
    args = {
        "client": "claude",
        "owner_tz": TZ,
        "kind": "task",
        "title": "Купить молоко",
        "source": Source(said="молоко кончилось"),
        "reason": "покупка",
    }
    args.update(over)
    async with db.write() as session:
        return await items.add(session, **args)


async def _update(db, item_id, rev, changes, client="claude"):
    async with db.write() as session:
        return await items.update(
            session, client=client, owner_tz=TZ, item_id=item_id, rev=rev, changes=changes, reason="правка"
        )


async def test_add_task(db, now):
    item = await _add(db, list_="shopping", due=date(2026, 10, 14))
    async with db.read() as session:
        cited = (await session.scalars(select(ItemFact.fact_id).where(ItemFact.item_id == item.id))).all()
        ops = [entry.op for entry in (await session.scalars(select(Journal).order_by(Journal.id))).all()]
    assert (item.kind, item.status, item.rev, item.list_) == ("task", "open", 1, "shopping")
    assert item.id.startswith("i_")
    assert len(cited) == 1
    assert ops == ["note", "item_add"]


async def test_add_needs_a_source(db, now):
    with pytest.raises(Refused, match="name the source"):
        await _add(db, source=Source(restructure=True))


@pytest.mark.parametrize(
    "over, message",
    [
        ({"kind": "habit"}, "unknown kind"),
        ({"title": " "}, "title is empty"),
        ({"kind": "event"}, "an event needs `at`"),
        ({"rrule": "FREQ=WEEKLY", "at": EVENING}, "events only"),
        ({"kind": "event", "at": EVENING, "rrule": "FREQ=SOMETIMES"}, "bad rrule"),
        ({"kind": "event", "at": EVENING, "list_": "shopping"}, "tasks only"),
        ({"list_": "Shopping List"}, "bad list"),
        ({"remind": ["PT1H"]}, "needs `at` or `due`"),
        ({"due": date(2026, 10, 14), "remind": ["1 hour"]}, "bad duration"),
        ({"tz": "Mars/Olympus"}, "unknown time zone"),
        ({"at": EVENING.replace(tzinfo=occur.zone("UTC"))}, "without an offset"),
        ({"page": "pages/people/nobody.md"}, "does not exist"),
        ({"title": "ключ " + "sk-" + "a" * 24}, "looks like a secret"),
    ],
)
async def test_add_refuses(db, now, over, message):
    with pytest.raises(Refused, match=message):
        await _add(db, **over)


async def test_update_closes_and_reopens_task(db, now):
    item = await _add(db)
    done = await _update(db, item.id, 1, {"status": "done"}, client="telegram")
    assert (done.status, done.rev, done.done_at) == ("done", 2, now)
    again = await _update(db, item.id, 2, {"status": "open", "due": date(2026, 10, 20)})
    assert (again.status, again.done_at, again.due, again.rev) == ("open", None, date(2026, 10, 20), 3)


async def test_update_moves_task_between_lists(db, now):
    item = await _add(db, list_="shopping")
    moved = await _update(db, item.id, 1, {"list": "pharmacy", "note": None, "remind": None})
    assert (moved.list_, moved.note, moved.remind) == ("pharmacy", "", [])


@pytest.mark.parametrize(
    "rev, changes, error, message",
    [
        (5, {"status": "done"}, Conflict, "current rev is 1"),
        (1, {}, Refused, "nothing to change"),
        (1, {"colour": "red"}, Refused, "unknown fields: colour"),
        (1, {"title": None}, Refused, "title cannot be null"),
        (1, {"status": "paused"}, Refused, "unknown status"),
        (1, {"remind": ["PT1H"]}, Refused, "needs `at` or `due`"),
    ],
)
async def test_update_refuses(db, now, rev, changes, error, message):
    item = await _add(db)
    with pytest.raises(error, match=message):
        await _update(db, item.id, rev, changes)


async def test_event_cannot_be_done(db, now):
    event = await _add(db, kind="event", title="Английский", at=EVENING)
    with pytest.raises(Refused, match="unknown status"):
        await _update(db, event.id, 1, {"status": "done"})


async def test_update_unknown_item(db, now):
    with pytest.raises(NotFound):
        await _update(db, "i_missing0", 1, {"status": "done"})


async def test_query_filters_and_window(db, now):
    milk = await _add(db, list_="shopping", due=date(2026, 10, 14))
    weekly = await _add(db, kind="event", title="Английский", at=datetime(2026, 10, 5, 18, 0), rrule="FREQ=WEEKLY")
    birthday = await _add(db, kind="event", title="ДР Ани", at=datetime(2020, 3, 14, 9, 0), rrule="FREQ=YEARLY")
    someday = await _add(db, title="Разобрать шкаф")

    async def ids(**filters):
        async with db.read() as session:
            return {item.id for item in await items.query(session, owner_tz=TZ, **filters)}

    assert await ids() == {milk.id, weekly.id, birthday.id, someday.id}
    assert await ids(kind="task") == {milk.id, someday.id}
    assert await ids(list_="shopping") == {milk.id}
    assert await ids(start=date(2026, 10, 12), end=date(2026, 10, 18)) == {milk.id, weekly.id}
    assert await ids(start=date(2026, 10, 19), end=date(2026, 10, 25)) == {weekly.id}
    assert await ids(start=date(2027, 3, 14), end=date(2027, 3, 14)) == {birthday.id}


async def test_query_by_status(db, now):
    item = await _add(db)
    await _update(db, item.id, 1, {"status": "done"})
    async with db.read() as session:
        assert await items.query(session, owner_tz=TZ) == []
        assert [found.id for found in await items.query(session, owner_tz=TZ, status="done")] == [item.id]
        assert [found.id for found in await items.query(session, owner_tz=TZ, status="any")] == [item.id]


async def test_window_needs_both_ends(db, now):
    async with db.read() as session:
        with pytest.raises(Refused, match="both"):
            await items.query(session, owner_tz=TZ, start=date(2026, 10, 12))


def test_weekly_event_keeps_local_time_across_clock_change():
    berlin = occur.zone(TZ)
    moments = occur.occurrences(
        datetime(2026, 10, 5, 18, 0),
        "FREQ=WEEKLY",
        TZ,
        datetime(2026, 10, 19, tzinfo=berlin),
        datetime(2026, 11, 2, tzinfo=berlin),
    )
    seen = [(moment.day, moment.hour, moment.utcoffset().total_seconds() / 3600) for moment in moments]
    assert seen == [(19, 18, 2.0), (26, 18, 1.0)]


def test_single_event_is_in_window_only_at_its_moment():
    berlin = occur.zone(TZ)

    def midnight(day):
        return datetime(2026, 10, day, tzinfo=berlin)

    assert len(occur.occurrences(EVENING, None, TZ, midnight(12), midnight(13))) == 1
    assert occur.occurrences(EVENING, None, TZ, midnight(13), midnight(14)) == []
