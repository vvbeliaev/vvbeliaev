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
        ({"list_": "shopping\n"}, "bad list"),
        ({"reason": "ключ " + "sk-" + "a" * 24}, "looks like a secret"),
        ({"kind": "event", "at": EVENING, "rrule": "FREQ=WEEKLY;UNTIL=20261231T000000Z"}, "without Z"),
        ({"kind": "event", "at": EVENING, "rrule": "FREQ=WEEKLY;UNTIL=20261231"}, "UNTIL as local date-time"),
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


async def test_update_journals_old_and_new_values(db, now):
    item = await _add(db, list_="shopping", due=date(2026, 10, 14))
    await _update(db, item.id, 1, {"due": date(2026, 10, 20), "list": None, "note": "  у метро "})
    event = await _add(db, kind="event", title="Английский", at=EVENING)
    await _update(db, event.id, 1, {"at": datetime(2026, 10, 12, 19, 30)})
    async with db.read() as session:
        entries = (await session.scalars(select(Journal).where(Journal.op == "item_update").order_by(Journal.id))).all()
    assert [entry.detail for entry in entries] == [
        {
            "before": {"due": "2026-10-14", "list": "shopping", "note": ""},
            "after": {"due": "2026-10-20", "list": None, "note": "у метро"},
        },
        {"before": {"at": "2026-10-12T18:00:00"}, "after": {"at": "2026-10-12T19:30:00"}},
    ]


async def test_update_with_a_secret_in_reason_is_refused(db, now):
    item = await _add(db)
    with pytest.raises(Refused, match="looks like a secret"):
        async with db.write() as session:
            await items.update(
                session, client="claude", owner_tz=TZ, item_id=item.id, rev=1,
                changes={"status": "done"}, reason="ключ " + "sk-" + "a" * 24,
            )


async def test_query_refuses_unknown_kind_and_status(db, now):
    async with db.read() as session:
        with pytest.raises(Refused, match="unknown kind 'habit'; one of: task, event"):
            await items.query(session, owner_tz=TZ, kind="habit")
        with pytest.raises(Refused, match="unknown status 'closed'; one of: open, done, cancelled, any"):
            await items.query(session, owner_tz=TZ, status="closed")


@pytest.mark.parametrize(
    "text",
    [
        "FREQ=WEEKLY\nFREQ=DAILY",
        "FREQ=WEEKLY\r\nCOUNT=3",
        "FREQ=WEEKLY\nEXDATE:20261019T180000",
        "FREQ=WEEKLY;EXDATE=20261019T180000",
        "DTSTART:20261012T180000\nRRULE:FREQ=WEEKLY",
        "FREQ=WEEKLY;rdate=20261019T180000",
    ],
)
def test_rrule_is_one_rule_without_dates(text):
    with pytest.raises(Refused, match="one rule only, no DTSTART, EXDATE or RDATE"):
        occur.rule(text, EVENING)


def test_rrule_until_must_be_local_time():
    with pytest.raises(Refused, match="write UNTIL as local time without Z"):
        occur.rule("FREQ=WEEKLY;UNTIL=20261231T000000Z", EVENING)
    assert occur.rule("FREQ=WEEKLY;UNTIL=20261231T000000", EVENING).count() == 12


@pytest.mark.parametrize(
    "text", ["FREQ=WEEKLY;UNTIL=20261231", "RRULE:FREQ=WEEKLY;until=20261231", "FREQ=WEEKLY;UNTIL=20261231;BYDAY=MO"]
)
def test_rrule_until_must_not_be_a_bare_date(text):
    with pytest.raises(Refused, match="write UNTIL as local date-time like 20261231T235959"):
        occur.rule(text, EVENING)


def test_rrule_until_as_local_date_time_stays_valid():
    assert occur.rule("FREQ=WEEKLY;UNTIL=20261231T235959", EVENING).count() == 12


# Postgres проверяет длину колонок. Всё, что идёт в `String(n)` без своего предела, должно получить отказ
# на входе, а не ошибку базы и 500.


async def test_list_slug_is_limited_to_its_column(db, now):
    item = await _add(db, list_="a" * 60)
    assert item.list_ == "a" * 60
    with pytest.raises(Refused, match="60 characters"):
        await _add(db, list_="a" * 61)


def _rule(length):
    """Правило ровно такой длины: нули в `INTERVAL` ничего не меняют."""
    base = "FREQ=WEEKLY;INTERVAL=1;BYDAY=MO"
    return base.replace("INTERVAL=1", "INTERVAL=" + "0" * (length - len(base)) + "1")


async def test_rrule_is_limited_to_its_column(db, now):
    assert len(_rule(300)) == 300
    item = await _add(db, kind="event", at=EVENING, rrule=_rule(300))
    assert item.rrule == _rule(300)
    with pytest.raises(Refused, match="300 characters"):
        await _add(db, kind="event", at=EVENING, rrule=_rule(301))


async def test_page_name_longer_than_its_column_is_simply_not_found(db, now):
    long = "pages/people/" + "a" * 200 + ".md"
    with pytest.raises(NotFound):
        await _add(db, page=long)
    item = await _add(db)
    with pytest.raises(NotFound):
        await _update(db, item.id, item.rev, {"page": long})
    async with db.read() as session:
        assert (await session.get(type(item), item.id)).page is None
