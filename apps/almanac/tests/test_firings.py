from datetime import UTC, date, datetime, timedelta

from sqlalchemy import select

from almanac import clock
from almanac.models import Firing, Item
from almanac.store import firings, items
from almanac.store.source import Source
from almanac.timeline import plan

TZ = "Europe/Berlin"


def _item(**over):
    fields = {
        "id": "i_test0001", "kind": "event", "title": "Английский", "note": "", "remind": ["PT1H"],
        "status": "open", "rev": 1, "at": datetime(2026, 10, 12, 18, 0),
    }
    fields.update(over)
    return Item(**fields)


def _utc(*parts):
    return datetime(*parts, tzinfo=UTC)


def test_single_event_fires_before_its_moment(now):
    # 18:00 в Берлине летом — это 16:00 UTC.
    assert plan.upcoming(_item(), TZ, "09:00", now) == [(_utc(2026, 10, 12, 16, 0), _utc(2026, 10, 12, 15, 0))]


def test_past_offsets_are_dropped(now):
    pairs = plan.upcoming(_item(remind=["P1D", "PT1H", "PT0M"]), TZ, "09:00", now)
    assert [fire for _anchor, fire in pairs] == [_utc(2026, 10, 12, 15, 0), _utc(2026, 10, 12, 16, 0)]


def test_passed_event_has_nothing_to_fire(now):
    assert plan.upcoming(_item(at=datetime(2026, 10, 11, 18, 0)), TZ, "09:00", now) == []


def test_repeating_event_moves_to_the_next_occurrence():
    weekly = _item(at=datetime(2026, 10, 5, 18, 0), rrule="FREQ=WEEKLY")
    after_reminder = _utc(2026, 10, 12, 15, 30)
    pairs = plan.upcoming(weekly, TZ, "09:00", after_reminder)
    assert pairs == [(_utc(2026, 10, 19, 16, 0), _utc(2026, 10, 19, 15, 0))]


def test_repeat_keeps_local_time_after_clock_change():
    weekly = _item(at=datetime(2026, 10, 5, 18, 0), rrule="FREQ=WEEKLY")
    pairs = plan.upcoming(weekly, TZ, "09:00", _utc(2026, 10, 20, 0, 0))
    # 26 октября в Берлине уже зимнее время: 18:00 — это 17:00 UTC.
    assert pairs == [(_utc(2026, 10, 26, 17, 0), _utc(2026, 10, 26, 16, 0))]


def test_task_with_due_counts_from_day_start(now):
    task = _item(kind="task", at=None, due=date(2026, 10, 14), remind=["PT0M", "P1D"])
    pairs = plan.upcoming(task, TZ, "09:00", now)
    assert [fire for _anchor, fire in pairs] == [_utc(2026, 10, 13, 7, 0), _utc(2026, 10, 14, 7, 0)]


def test_closed_or_silent_item_fires_nothing(now):
    assert plan.upcoming(_item(status="cancelled"), TZ, "09:00", now) == []
    assert plan.upcoming(_item(remind=[]), TZ, "09:00", now) == []


def _daily(**over):
    return _item(at=datetime(2026, 10, 5, 18, 0), rrule="FREQ=DAILY", **over)


def test_long_offset_of_a_daily_event_is_planned(now):
    # Напоминание за два дня: на 14 октября оно приходится на сегодня, 12 октября, 18:00 местного.
    pairs = plan.upcoming(_daily(remind=["P2D"]), TZ, "09:00", now)
    assert pairs == [(_utc(2026, 10, 14, 16, 0), _utc(2026, 10, 12, 16, 0))]


def test_day_before_and_at_time_share_one_moment(now):
    pairs = plan.upcoming(_daily(remind=["P1D", "PT0M"]), TZ, "09:00", now)
    # «За день» к завтрашнему и «в момент» для сегодняшнего совпали: момент один, а не два.
    assert [fire for _anchor, fire in pairs] == [_utc(2026, 10, 12, 16, 0), _utc(2026, 10, 13, 16, 0)]
    assert pairs[0][0] == _utc(2026, 10, 12, 16, 0)


def test_planning_after_the_send_covers_tomorrow():
    after_send = _utc(2026, 10, 12, 16, 0)
    pairs = plan.upcoming(_daily(remind=["P1D", "PT0M"]), TZ, "09:00", after_send)
    assert next(fire for _anchor, fire in pairs) == _utc(2026, 10, 13, 16, 0)


def test_weekly_event_with_a_two_week_offset_is_planned(now):
    weekly = _item(at=datetime(2026, 10, 5, 18, 0), rrule="FREQ=WEEKLY", remind=["P2W"])
    # 26 октября уже зимнее время (17:00 UTC), а «за две недели» — тот же местный час: 12 октября, 18:00 = 16:00 UTC.
    assert plan.upcoming(weekly, TZ, "09:00", now) == [(_utc(2026, 10, 26, 17, 0), _utc(2026, 10, 12, 16, 0))]


def test_offset_longer_than_the_walk_plans_nothing(now):
    assert plan.upcoming(_daily(remind=["P9999W"]), TZ, "09:00", now) == []


def test_minutes_before_an_event_after_spring_forward_are_real_minutes():
    # Берлин, 29 марта 2026: 02:00 → 03:00. Событие в 03:10 — это 01:10 UTC.
    event = _item(at=datetime(2026, 3, 29, 3, 10), remind=["PT30M"])
    pairs = plan.upcoming(event, TZ, "09:00", _utc(2026, 3, 1, 0, 0))
    assert pairs == [(_utc(2026, 3, 29, 1, 10), _utc(2026, 3, 29, 0, 40))]


def test_an_hour_before_an_event_after_fall_back_is_a_real_hour():
    # Берлин, 25 октября 2026: 03:00 → 02:00. Событие в 03:30 — это 02:30 UTC.
    event = _item(at=datetime(2026, 10, 25, 3, 30), remind=["PT1H"])
    pairs = plan.upcoming(event, TZ, "09:00", _utc(2026, 10, 20, 0, 0))
    assert pairs == [(_utc(2026, 10, 25, 2, 30), _utc(2026, 10, 25, 1, 30))]


def test_a_day_before_keeps_the_local_hour_across_the_clock_change():
    event = _item(at=datetime(2026, 10, 25, 18, 0), remind=["P1D", "P1DT2H"])
    pairs = plan.upcoming(event, TZ, "09:00", _utc(2026, 10, 20, 0, 0))
    # 25 октября 18:00 — зимнее время (17:00 UTC); 24 октября 18:00 — ещё летнее (16:00 UTC); «и два часа» — настоящие.
    assert [fire for _anchor, fire in pairs] == [_utc(2026, 10, 24, 14, 0), _utc(2026, 10, 24, 16, 0)]


async def _pending(db):
    async with db.read() as session:
        rows = (await session.scalars(select(Firing).order_by(Firing.fire_at))).all()
    return [(row.fire_at, row.state) for row in rows]


async def test_adding_an_item_plans_its_firings(db, now):
    async with db.write() as session:
        await items.add(
            session, client="claude", owner_tz=TZ, kind="event", title="Английский",
            at=datetime(2026, 10, 12, 18, 0), remind=["PT1H"],
            source=Source(said="английский в шесть"), reason="расписание",
        )
    assert await _pending(db) == [(_utc(2026, 10, 12, 15, 0), "pending")]


async def test_update_replans_and_closing_skips(db, now):
    async with db.write() as session:
        item = await items.add(
            session, client="claude", owner_tz=TZ, kind="task", title="Сдать отчёт", due=date(2026, 10, 14),
            remind=["PT0M"], source=Source(said="отчёт к среде"), reason="срок",
        )
    assert await _pending(db) == [(_utc(2026, 10, 14, 7, 0), "pending")]

    async with db.write() as session:
        await items.update(
            session, client="claude", owner_tz=TZ, item_id=item.id, rev=1,
            changes={"due": date(2026, 10, 15)}, reason="перенос",
        )
    assert await _pending(db) == [(_utc(2026, 10, 15, 7, 0), "pending")]

    async with db.write() as session:
        await items.update(
            session, client="claude", owner_tz=TZ, item_id=item.id, rev=2,
            changes={"status": "done"}, reason="сдал",
        )
    assert await _pending(db) == [(_utc(2026, 10, 15, 7, 0), "skipped")]


async def test_replan_keeps_sent_and_manual_firings(db, now, monkeypatch):
    async with db.write() as session:
        item = await items.add(
            session, client="claude", owner_tz=TZ, kind="event", title="Английский",
            at=datetime(2026, 10, 5, 18, 0), rrule="FREQ=WEEKLY", remind=["PT1H"],
            source=Source(said="английский по понедельникам"), reason="расписание",
        )
    async with db.write() as session:
        first = (await session.scalars(select(Firing))).one()
        first.state = "sent"
        session.add(Firing(
            id="r_manual01", item_id=item.id, occurrence=first.occurrence,
            fire_at=now + timedelta(hours=7), state="pending", attempts=0, manual=True,
        ))
    monkeypatch.setattr(clock, "_now", lambda: _utc(2026, 10, 12, 15, 30))
    async with db.write() as session:
        await firings.replan(session, await session.get(Item, item.id), owner_tz=TZ, day_start="09:00")
    assert await _pending(db) == [
        (_utc(2026, 10, 12, 15, 0), "sent"),
        (_utc(2026, 10, 12, 17, 0), "pending"),
        (_utc(2026, 10, 19, 15, 0), "pending"),
    ]
    async with db.read() as session:
        assert [row.id for row in await firings.due(session, _utc(2026, 10, 12, 17, 0))] == ["r_manual01"]


async def test_reopening_an_item_plans_its_firings_again(db, now):
    async with db.write() as session:
        item = await items.add(
            session, client="claude", owner_tz=TZ, kind="task", title="Сдать отчёт", due=date(2026, 10, 14),
            remind=["PT0M"], source=Source(said="отчёт к среде"), reason="срок",
        )
    async with db.write() as session:
        await items.update(
            session, client="claude", owner_tz=TZ, item_id=item.id, rev=1,
            changes={"status": "done"}, reason="сдал",
        )
    assert await _pending(db) == [(_utc(2026, 10, 14, 7, 0), "skipped")]

    async with db.write() as session:
        await items.update(
            session, client="claude", owner_tz=TZ, item_id=item.id, rev=2,
            changes={"status": "open"}, reason="сдача не принята",
        )
    # Порядок двух срабатываний с одним моментом не задан, поэтому сравниваем отсортированно.
    assert sorted(await _pending(db)) == [
        (_utc(2026, 10, 14, 7, 0), "pending"),
        (_utc(2026, 10, 14, 7, 0), "skipped"),
    ]


async def test_replan_keeps_a_ripe_firing(db, now, monkeypatch):
    async with db.write() as session:
        item = await items.add(
            session, client="claude", owner_tz=TZ, kind="event", title="Английский",
            at=datetime(2026, 10, 12, 18, 0), remind=["PT1H", "PT0M"],
            source=Source(said="английский в шесть"), reason="расписание",
        )
    assert await _pending(db) == [(_utc(2026, 10, 12, 15, 0), "pending"), (_utc(2026, 10, 12, 16, 0), "pending")]
    # Оба срока прошли, а сервер ещё ничего не отправил: правка не должна стереть созревшее.
    monkeypatch.setattr(clock, "_now", lambda: _utc(2026, 10, 12, 16, 10))
    async with db.write() as session:
        await firings.replan(session, await session.get(Item, item.id), owner_tz=TZ, day_start="09:00")
    assert await _pending(db) == [(_utc(2026, 10, 12, 15, 0), "pending"), (_utc(2026, 10, 12, 16, 0), "pending")]


async def test_replan_of_a_daily_event_with_day_before_and_at_time_plans_one_firing_per_moment(db, now):
    async with db.write() as session:
        await items.add(
            session, client="claude", owner_tz=TZ, kind="event", title="Зарядка",
            at=datetime(2026, 10, 5, 18, 0), rrule="FREQ=DAILY", remind=["P1D", "PT0M"],
            source=Source(said="зарядка каждый день"), reason="расписание",
        )
    assert await _pending(db) == [(_utc(2026, 10, 12, 16, 0), "pending"), (_utc(2026, 10, 13, 16, 0), "pending")]
