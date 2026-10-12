"""Повторяющиеся задачи: привычка — одна строка, чей срок или время — ближайшее повторение.
Часы стоят на понедельнике 2026-10-12, 12:00 в Берлине."""

from datetime import UTC, date, datetime

import pytest
from httpx import ASGITransport, AsyncClient
from icalendar import Calendar
from sqlalchemy import select

from almanac import clock, tree
from almanac.app import create_app
from almanac.config import Settings
from almanac.errors import Refused
from almanac.models import Firing, Item, Journal
from almanac.store import items
from almanac.store.source import Source
from almanac.timeline import plan

TZ = "Europe/Berlin"
SECRET = "feed-" + "a" * 32


async def _add(db, **over):
    args = {
        "client": "claude", "owner_tz": TZ, "kind": "task", "title": "Зарядка",
        "source": Source(said="зарядка каждый день"), "reason": "привычка",
    }
    args.update(over)
    async with db.write() as session:
        return await items.add(session, **args)


async def _update(db, item_id, rev, changes, client="claude"):
    async with db.write() as session:
        return await items.update(
            session, client=client, owner_tz=TZ, item_id=item_id, rev=rev, changes=changes, reason="сделано"
        )


def _clock(monkeypatch, *parts):
    moment = datetime(*parts, tzinfo=UTC)
    monkeypatch.setattr(clock, "_now", lambda: moment)
    return moment


async def _text(db, ctx, path):
    async with db.read() as session:
        return (await tree.read(session, ctx, path)).text


async def _firings(db):
    async with db.read() as session:
        rows = (await session.scalars(select(Firing).order_by(Firing.fire_at))).all()
    return [(row.state, row.fire_at, row.manual) for row in rows]


async def _journal(db, op):
    async with db.read() as session:
        return [row.detail for row in (await session.scalars(select(Journal).where(Journal.op == op))).all()]


def _utc(*parts):
    return datetime(*parts, tzinfo=UTC)


# --- закрытие повторения ---


async def test_closing_a_daily_habit_by_date_moves_it_to_tomorrow(db, now):
    habit = await _add(db, due=date(2026, 10, 12), rrule="FREQ=DAILY")
    done = await _update(db, habit.id, 1, {"status": "done"})
    assert (done.status, done.due, done.rev) == ("open", date(2026, 10, 13), 2)
    assert done.done_at == now
    assert await _journal(db, "item_done") == [{"occurrence": "2026-10-12", "next": "2026-10-13"}]
    assert await _journal(db, "item_update") == []


async def test_a_habit_closed_three_days_late_moves_to_tomorrow_not_to_yesterday(db, now):
    habit = await _add(db, due=date(2026, 10, 9), rrule="FREQ=DAILY")
    done = await _update(db, habit.id, 1, {"status": "done"})
    assert done.due == date(2026, 10, 13)
    assert await _journal(db, "item_done") == [{"occurrence": "2026-10-09", "next": "2026-10-13"}]


async def test_a_habit_closed_ahead_of_time_skips_to_the_day_after_its_date(db, now):
    habit = await _add(db, due=date(2026, 10, 14), rrule="FREQ=DAILY")
    done = await _update(db, habit.id, 1, {"status": "done"})
    assert done.due == date(2026, 10, 15)


async def test_a_habit_by_time_closed_before_its_hour_moves_to_the_next_day(db, now):
    # Сейчас 12:00, срок сегодня в 18:00: следующее повторение — завтра в 18:00, а не сегодняшнее ещё раз.
    habit = await _add(db, at=datetime(2026, 10, 12, 18, 0), rrule="FREQ=DAILY")
    done = await _update(db, habit.id, 1, {"status": "done"})
    assert (done.status, done.at) == ("open", datetime(2026, 10, 13, 18, 0))
    assert await _journal(db, "item_done") == [
        {"occurrence": "2026-10-12T18:00:00", "next": "2026-10-13T18:00:00"}
    ]


async def test_a_habit_by_time_closed_three_days_late_moves_to_the_next_hour_after_now(db, now):
    habit = await _add(db, at=datetime(2026, 10, 9, 8, 0), rrule="FREQ=DAILY")
    done = await _update(db, habit.id, 1, {"status": "done"})
    assert done.at == datetime(2026, 10, 13, 8, 0)


async def test_a_weekly_habit_moves_along_its_days(db, now, monkeypatch):
    gym = await _add(db, title="Тренировка", at=datetime(2026, 10, 12, 18, 0), rrule="FREQ=WEEKLY;BYDAY=MO,TH")
    first = await _update(db, gym.id, 1, {"status": "done"})
    assert first.at == datetime(2026, 10, 15, 18, 0)
    _clock(monkeypatch, 2026, 10, 15, 16, 30)  # четверг, 18:30 в Берлине
    second = await _update(db, gym.id, 2, {"status": "done"})
    assert second.at == datetime(2026, 10, 19, 18, 0)


async def test_at_and_due_move_together(db, now):
    report = await _add(db, title="Отчёт", at=datetime(2026, 10, 12, 17, 0), due=date(2026, 10, 12), rrule="FREQ=WEEKLY")
    done = await _update(db, report.id, 1, {"status": "done"})
    assert (done.at, done.due) == (datetime(2026, 10, 19, 17, 0), date(2026, 10, 19))
    assert await _journal(db, "item_done") == [
        {
            "occurrence": "2026-10-12T17:00:00", "next": "2026-10-19T17:00:00",
            "before": {"due": "2026-10-12"}, "after": {"due": "2026-10-19"},
        }
    ]


async def test_other_fields_changed_with_the_completion_are_journaled(db, now):
    habit = await _add(db, due=date(2026, 10, 12), rrule="FREQ=DAILY")
    done = await _update(db, habit.id, 1, {"status": "done", "note": "  двадцать минут "})
    assert done.note == "двадцать минут"
    assert await _journal(db, "item_done") == [
        {
            "occurrence": "2026-10-12", "next": "2026-10-13",
            "before": {"note": ""}, "after": {"note": "двадцать минут"},
        }
    ]


async def test_a_habit_can_be_closed_again_and_again(db, now, monkeypatch):
    habit = await _add(db, due=date(2026, 10, 12), rrule="FREQ=DAILY")
    one = await _update(db, habit.id, 1, {"status": "done"})
    _clock(monkeypatch, 2026, 10, 13, 10, 0)
    two = await _update(db, one.id, 2, {"status": "done"})
    assert (two.due, two.rev, two.status) == (date(2026, 10, 14), 3, "open")
    assert two.done_at == _utc(2026, 10, 13, 10, 0)


async def test_the_last_occurrence_closes_the_task_as_any_task(db, now):
    course = await _add(db, title="Курс", due=date(2026, 10, 12), rrule="FREQ=DAILY;UNTIL=20261012T235959")
    closed = await _update(db, course.id, 1, {"status": "done"})
    assert (closed.status, closed.due, closed.done_at) == ("done", date(2026, 10, 12), now)
    assert await _journal(db, "item_done") == []
    assert len(await _journal(db, "item_update")) == 1


async def test_a_rule_that_ended_in_the_past_closes_the_task(db, now):
    course = await _add(db, title="Курс", at=datetime(2026, 10, 5, 18, 0), rrule="FREQ=DAILY;UNTIL=20261008T235959")
    closed = await _update(db, course.id, 1, {"status": "done"})
    assert (closed.status, closed.at) == ("done", datetime(2026, 10, 5, 18, 0))


async def test_cancelling_ends_the_series(db, now):
    habit = await _add(db, due=date(2026, 10, 12), rrule="FREQ=DAILY", remind=["P1D"])
    cancelled = await _update(db, habit.id, 1, {"status": "cancelled"})
    assert (cancelled.status, cancelled.due, cancelled.done_at) == ("cancelled", date(2026, 10, 12), None)
    assert {state for state, _, _ in await _firings(db)} <= {"skipped"}


async def test_dropping_the_rule_and_closing_in_one_call_closes_the_task(db, now):
    habit = await _add(db, due=date(2026, 10, 12), rrule="FREQ=DAILY")
    closed = await _update(db, habit.id, 1, {"status": "done", "rrule": None})
    assert (closed.status, closed.due, closed.rrule) == ("done", date(2026, 10, 12), None)


async def test_closing_together_with_a_new_date_is_refused(db, now):
    habit = await _add(db, due=date(2026, 10, 12), rrule="FREQ=DAILY")
    with pytest.raises(Refused, match="moves to its next occurrence by itself"):
        await _update(db, habit.id, 1, {"status": "done", "due": date(2026, 10, 20)})
    with pytest.raises(Refused, match="moves to its next occurrence by itself"):
        await _update(db, habit.id, 1, {"status": "done", "in": "PT1H"})


async def test_a_repeating_event_is_not_moved_by_anything(db, now):
    event = await _add(db, kind="event", title="Английский", at=datetime(2026, 10, 12, 18, 0), rrule="FREQ=WEEKLY")
    with pytest.raises(Refused, match="unknown status"):
        await _update(db, event.id, 1, {"status": "done"})
    cancelled = await _update(db, event.id, 1, {"status": "cancelled"})
    assert (cancelled.status, cancelled.at) == ("cancelled", datetime(2026, 10, 12, 18, 0))


async def test_a_one_off_task_closes_as_before(db, now):
    task = await _add(db, title="Купить молоко", due=date(2026, 10, 14))
    done = await _update(db, task.id, 1, {"status": "done"})
    assert (done.status, done.due, done.done_at) == ("done", date(2026, 10, 14), now)
    assert await _journal(db, "item_done") == []


async def test_a_note_edit_does_not_forget_the_last_completion(db, now):
    habit = await _add(db, due=date(2026, 10, 12), rrule="FREQ=DAILY")
    one = await _update(db, habit.id, 1, {"status": "done"})
    again = await _update(db, one.id, 2, {"status": "open", "note": "заметка"})
    assert again.done_at == now


async def test_closing_over_the_api_moves_the_habit(api, now):
    added = await api.post(
        "/api/items",
        json={"kind": "task", "title": "Зарядка", "due": "2026-10-12", "rrule": "FREQ=DAILY",
              "said": "зарядка каждый день", "reason": "привычка"},
    )
    assert added.status_code == 200, added.text
    done = await api.patch(f"/api/items/{added.json()['id']}", json={"rev": 1, "status": "done", "reason": "сделано"})
    answer = done.json()
    assert (answer["status"], answer["due"], answer["rev"]) == ("open", "2026-10-13", 2)
    assert answer["done_at"] == "2026-10-12T10:00:00+00:00"


# --- что разрешено ---


@pytest.mark.parametrize("rule", ["FREQ=DAILY;COUNT=3", "FREQ=DAILY;count=3", "FREQ=WEEKLY;BYDAY=MO;COUNT=10"])
async def test_count_is_refused_on_a_task_with_the_fix(db, now, rule):
    with pytest.raises(Refused, match="use UNTIL"):
        await _add(db, due=date(2026, 10, 12), rrule=rule)


async def test_count_is_refused_when_a_task_gets_its_rule_by_update(db, now):
    task = await _add(db, due=date(2026, 10, 12))
    with pytest.raises(Refused, match="use UNTIL"):
        await _update(db, task.id, 1, {"rrule": "FREQ=DAILY;COUNT=3"})
    habit = await _update(db, task.id, 1, {"rrule": "FREQ=DAILY;UNTIL=20261231T235959"})
    assert habit.rrule == "FREQ=DAILY;UNTIL=20261231T235959"


async def test_an_event_keeps_count(db, now):
    event = await _add(db, kind="event", at=datetime(2026, 10, 12, 18, 0), rrule="FREQ=DAILY;COUNT=3")
    assert event.rrule == "FREQ=DAILY;COUNT=3"


async def test_a_rule_on_a_task_needs_a_date_to_repeat_from(db, now):
    with pytest.raises(Refused, match="needs `due` or `at` to repeat from"):
        await _add(db, rrule="FREQ=DAILY")
    habit = await _add(db, due=date(2026, 10, 12), rrule="FREQ=DAILY")
    with pytest.raises(Refused, match="needs `due` or `at` to repeat from"):
        await _update(db, habit.id, 1, {"due": None})


async def test_a_bad_rule_on_a_task_is_still_refused(db, now):
    with pytest.raises(Refused, match="bad rrule"):
        await _add(db, due=date(2026, 10, 12), rrule="FREQ=SOMETIMES")


# --- повестка ---


def _days(agenda):
    days, current = {}, None
    for line in agenda.splitlines():
        if line.startswith("## 20"):
            current = line[3:13]
            days[current] = []
        elif line.startswith("## "):
            current = None
        elif current and line.startswith("- ["):
            days[current].append(line)
    return days


@pytest.mark.parametrize("over", [{"due": date(2026, 10, 12)}, {"at": datetime(2026, 10, 12, 18, 0)}])
async def test_a_daily_habit_is_on_every_day_of_the_week(db, ctx, now, over):
    await _add(db, rrule="FREQ=DAILY", **over)
    week = _days(await _text(db, ctx, "views/week.md"))
    assert sorted(week) == [f"2026-10-{day}" for day in range(12, 19)]
    assert all(any("Зарядка" in line for line in lines) for lines in week.values())
    today = _days(await _text(db, ctx, "views/today.md"))
    assert list(today) == ["2026-10-12"]


async def test_a_habit_by_date_shows_only_on_its_coming_days(db, now):
    await _add(db, due=date(2026, 10, 12), rrule="FREQ=WEEKLY;BYDAY=MO,TH")

    async def found(day):
        async with db.read() as session:
            return bool(await items.query(session, owner_tz=TZ, start=day, end=day))

    assert [await found(date(2026, 10, day)) for day in range(11, 17)] == [False, True, False, False, True, False]
    assert await found(date(2026, 10, 19))


async def test_the_item_line_says_when_a_habit_was_last_done(db, now):
    habit = await _add(db, due=date(2026, 10, 12), rrule="FREQ=DAILY")
    done = await _update(db, habit.id, 1, {"status": "done"})
    assert tree.render_item(done) == (
        f"- [ ] Зарядка  due:2026-10-13  every:FREQ=DAILY  last:2026-10-12  ^{done.id}"
    )
    plain = await _add(db, title="Купить хлеб", due=date(2026, 10, 14))
    closed = await _update(db, plain.id, 1, {"status": "done"})
    assert tree.render_item(closed) == f"- [x] Купить хлеб  due:2026-10-14  done:2026-10-12  ^{closed.id}"


# --- напоминания ---


def _task(**over):
    fields = {"id": "i_test0001", "kind": "task", "title": "Зарядка", "note": "", "remind": ["PT0M"],
              "status": "open", "rev": 1}
    fields.update(over)
    return Item(**fields)


def test_a_repeating_task_by_date_reminds_from_the_start_of_each_day(now):
    habit = _task(due=date(2026, 10, 12), rrule="FREQ=DAILY")
    # Сегодняшние 09:00 уже прошли; завтрашние — 07:00 UTC.
    assert plan.upcoming(habit, TZ, "09:00", now) == [(_utc(2026, 10, 13, 7, 0), _utc(2026, 10, 13, 7, 0))]


def test_a_repeating_task_by_date_reminds_ahead_of_each_day(now):
    habit = _task(due=date(2026, 10, 12), rrule="FREQ=DAILY", remind=["P1D"])
    # «За день» к завтрашнему уже в прошлом (сегодня 07:00 UTC прошло); ближайшее — к 14-му, 13-го в 07:00 UTC.
    assert plan.upcoming(habit, TZ, "09:00", now) == [(_utc(2026, 10, 14, 7, 0), _utc(2026, 10, 13, 7, 0))]


def test_a_repeating_task_by_date_never_asks_the_rule_for_every_hour(now):
    habit = _task(due=date(2026, 10, 12), rrule="FREQ=HOURLY")
    pairs = plan.upcoming(habit, TZ, "09:00", now)
    assert [fire for _anchor, fire in pairs] == [_utc(2026, 10, 13, 7, 0)]


async def test_closing_skips_the_reminder_of_the_closed_occurrence_and_plans_the_next(db, now):
    habit = await _add(db, at=datetime(2026, 10, 12, 18, 0), rrule="FREQ=DAILY", remind=["PT1H"])
    assert await _firings(db) == [("pending", _utc(2026, 10, 12, 15, 0), False)]
    await _update(db, habit.id, 1, {"status": "done"})
    assert await _firings(db) == [
        ("skipped", _utc(2026, 10, 12, 15, 0), False),
        ("pending", _utc(2026, 10, 13, 15, 0), False),
    ]


async def test_closing_ahead_of_time_skips_the_reminder_of_the_date_it_was_closed_for(db, now):
    await _add(db, due=date(2026, 10, 13), rrule="FREQ=DAILY", remind=["PT0M"])
    assert await _firings(db) == [("pending", _utc(2026, 10, 13, 7, 0), False)]
    async with db.read() as session:
        habit = (await session.scalars(select(Item))).one()
    done = await _update(db, habit.id, 1, {"status": "done"})
    # Закрыли заранее то, что назначено на завтра; следующее — послезавтра.
    assert done.due == date(2026, 10, 14)
    assert await _firings(db) == [
        ("skipped", _utc(2026, 10, 13, 7, 0), False),
        ("pending", _utc(2026, 10, 14, 7, 0), False),
    ]


async def test_closing_skips_snoozed_reminders_of_the_closed_occurrence(db, now):
    habit = await _add(db, at=datetime(2026, 10, 12, 18, 0), rrule="FREQ=DAILY", remind=["PT1H"])
    async with db.write() as session:
        old = (await session.scalars(select(Firing))).one()
        old.state = "snoozed"
        session.add(
            Firing(
                id="r_snooze01", item_id=habit.id, occurrence=old.occurrence, fire_at=_utc(2026, 10, 12, 16, 30),
                state="pending", attempts=0, manual=True,
            )
        )
    await _update(db, habit.id, 1, {"status": "done"})
    assert await _firings(db) == [
        ("snoozed", _utc(2026, 10, 12, 15, 0), False),
        ("skipped", _utc(2026, 10, 12, 16, 30), True),
        ("pending", _utc(2026, 10, 13, 15, 0), False),
    ]


# --- лента ---


async def _feed(db, to_add):
    async with db.write() as session:
        for args in to_add:
            await items.add(
                session, client="claude", owner_tz=TZ, source=Source(said="так сказал владелец"), reason="тест", **args
            )
    app = create_app(Settings(_env_file=None, owner_tz=TZ, ics_token=SECRET), db=db)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as http:
        response = await http.get(f"/calendar/{SECRET}.ics")
    return {str(event["summary"]): event for event in Calendar.from_ical(response.content).walk("VEVENT")}, response


async def test_feed_carries_the_rule_of_a_repeating_task(db, now):
    events, response = await _feed(
        db,
        [
            {"kind": "task", "title": "Зарядка", "due": date(2026, 10, 12), "rrule": "FREQ=DAILY;UNTIL=20261231T235959"},
            {"kind": "task", "title": "Тренировка", "at": datetime(2026, 10, 12, 18, 0), "rrule": "FREQ=WEEKLY;BYDAY=MO"},
        ],
    )
    morning, gym = events["☐ Зарядка"], events["☐ Тренировка"]
    assert morning["dtstart"].dt == date(2026, 10, 12)
    assert morning["rrule"]["FREQ"] == ["DAILY"]
    assert gym["dtstart"].dt.replace(tzinfo=None) == datetime(2026, 10, 12, 18, 0)
    assert gym["rrule"]["BYDAY"] == ["MO"]
    # У даты в начале правило кончается датой, у времени — моментом в UTC.
    assert b"UNTIL=20261231\r\n" in response.content
