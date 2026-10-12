"""Время элемента: «через», целый день, длительность. Часы стоят на понедельнике 2026-10-12, 12:00 в Берлине."""

from datetime import UTC, date, datetime, timedelta

import pytest
from httpx import ASGITransport, AsyncClient
from icalendar import Calendar
from sqlalchemy import select

from almanac import clock, tree
from almanac.app import create_app
from almanac.config import Settings
from almanac.errors import Refused
from almanac.models import Firing, Journal
from almanac.store import items
from almanac.store.source import Source

TZ = "Europe/Berlin"
EVENING = datetime(2026, 10, 12, 18, 0)
SECRET = "feed-" + "a" * 32


async def _add(db, **over):
    args = {
        "client": "claude", "owner_tz": TZ, "kind": "event", "title": "Созвон",
        "source": Source(said="созвон по плану"), "reason": "расписание",
    }
    args.update(over)
    async with db.write() as session:
        return await items.add(session, **args)


async def _update(db, item_id, rev, changes):
    async with db.write() as session:
        return await items.update(
            session, client="claude", owner_tz=TZ, item_id=item_id, rev=rev, changes=changes, reason="правка"
        )


def _clock(monkeypatch, *parts):
    moment = datetime(*parts, tzinfo=UTC)
    monkeypatch.setattr(clock, "_now", lambda: moment)
    return moment


async def _text(db, ctx, path):
    async with db.read() as session:
        return (await tree.read(session, ctx, path)).text


def _by_day(agenda):
    """Повестка по дням: день -> строки элементов под его заголовком."""
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


async def _fires(db):
    async with db.read() as session:
        rows = (await session.scalars(select(Firing).order_by(Firing.fire_at))).all()
    return [row.fire_at for row in rows]


# --- in: от «сейчас» ---


async def test_in_counts_from_the_server_clock(db, now):
    event = await _add(db, in_="PT20M")
    task = await _add(db, kind="task", title="Выключить плиту", in_="PT1H30M")
    assert (event.at, event.all_day) == (datetime(2026, 10, 12, 12, 20), False)
    assert (task.at, task.due) == (datetime(2026, 10, 12, 13, 30), None)


@pytest.mark.parametrize(
    "second, microsecond, minute",
    [(0, 0, 20), (0, 1, 21), (1, 0, 21), (30, 0, 21), (59, 999999, 21)],
)
async def test_in_rounds_up_to_the_whole_minute(db, now, monkeypatch, second, microsecond, minute):
    moment = datetime(2026, 10, 12, 10, 0, second, microsecond, tzinfo=UTC)
    monkeypatch.setattr(clock, "_now", lambda: moment)
    event = await _add(db, in_="PT20M")
    assert event.at == datetime(2026, 10, 12, 12, minute)


async def test_in_with_whole_days_keeps_the_local_hour_across_the_clock_change(db, now, monkeypatch):
    # 24 октября в 12:00 летнее время; в ночь на 25-е часы идут назад. «Через день» — то же местное 12:00,
    # а «через 23 часа» — настоящие часы: на два часа раньше по стенным часам, потому что один из них лишний.
    _clock(monkeypatch, 2026, 10, 24, 10, 0)
    assert (await _add(db, in_="P1D")).at == datetime(2026, 10, 25, 12, 0)
    assert (await _add(db, in_="PT23H")).at == datetime(2026, 10, 25, 10, 0)
    assert (await _add(db, in_="P2DT30M")).at == datetime(2026, 10, 26, 12, 30)


async def test_in_uses_the_zone_of_the_item(db, now):
    # 10:00 UTC — в Нью-Йорке 06:00.
    event = await _add(db, in_="PT20M", tz="America/New_York")
    assert event.at == datetime(2026, 10, 12, 6, 20)


async def test_in_and_at_together_are_refused(db, now):
    with pytest.raises(Refused, match="pass `at` or `in`, not both"):
        await _add(db, in_="PT20M", at=EVENING)


async def test_in_with_a_bad_offset_is_refused(db, now):
    with pytest.raises(Refused, match="bad duration"):
        await _add(db, in_="20 minutes")


async def test_in_on_update_moves_the_item_and_journals_the_moment(db, now):
    event = await _add(db, at=EVENING)
    moved = await _update(db, event.id, 1, {"in": "PT2H"})
    assert (moved.at, moved.rev) == (datetime(2026, 10, 12, 14, 0), 2)
    async with db.read() as session:
        entry = (await session.scalars(select(Journal).where(Journal.op == "item_update"))).one()
    assert entry.detail == {"before": {"at": "2026-10-12T18:00:00"}, "after": {"at": "2026-10-12T14:00:00"}}


async def test_in_and_at_together_on_update_are_refused(db, now):
    event = await _add(db, at=EVENING)
    with pytest.raises(Refused, match="pass `at` or `in`, not both"):
        await _update(db, event.id, 1, {"in": "PT2H", "at": EVENING})


async def test_in_on_update_counts_in_the_zone_it_is_sent_with(db, now):
    event = await _add(db, at=EVENING)
    moved = await _update(db, event.id, 1, {"in": "PT20M", "tz": "America/New_York"})
    assert (moved.at, moved.tz) == (datetime(2026, 10, 12, 6, 20), "America/New_York")


async def test_a_null_in_on_update_is_just_absent(db, now):
    event = await _add(db, at=EVENING)
    noted = await _update(db, event.id, 1, {"in": None, "note": "взять ноутбук"})
    assert (noted.at, noted.note) == (EVENING, "взять ноутбук")
    with pytest.raises(Refused, match="nothing to change"):
        await _update(db, event.id, 2, {"in": None})


async def test_in_on_update_turns_a_whole_day_into_a_moment(db, now):
    trip = await _add(db, at=date(2026, 10, 20))
    moved = await _update(db, trip.id, 1, {"in": "PT1H"})
    assert (moved.all_day, moved.at) == (False, datetime(2026, 10, 12, 13, 0))


async def test_in_over_the_api(api, now):
    response = await api.post(
        "/api/items",
        json={"kind": "task", "title": "Выключить плиту", "in": "PT20M", "said": "плита", "reason": "напоминание"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["at"] == "2026-10-12T12:20"
    item = response.json()
    moved = await api.patch(f"/api/items/{item['id']}", json={"rev": 1, "in": "P1D", "reason": "позже"})
    assert moved.json()["at"] == "2026-10-13T12:00"


# --- at: день или момент ---


async def test_the_three_forms_of_at_over_the_api(api, now):
    async def add(at):
        response = await api.post(
            "/api/items",
            json={"kind": "event", "title": "Поездка", "at": at, "said": "поездка", "reason": "план"},
        )
        assert response.status_code == 200, response.text
        return response.json()

    assert (await add("2026-10-20"))["at"] == "2026-10-20"
    assert (await add("2026-10-20T00:00"))["at"] == "2026-10-20T00:00"
    assert (await add("2026-10-20T18:00"))["at"] == "2026-10-20T18:00"


async def test_a_date_is_a_whole_day_and_midnight_is_a_moment(db, now):
    whole = await _add(db, at=date(2026, 10, 20))
    midnight = await _add(db, at=datetime(2026, 10, 20, 0, 0))
    timed = await _add(db, at=datetime(2026, 10, 20, 18, 0))
    assert [item.all_day for item in (whole, midnight, timed)] == [True, False, False]
    assert whole.at == midnight.at == datetime(2026, 10, 20, 0, 0)


async def test_a_whole_day_event_prints_a_date_in_the_item_line(db, now):
    trip = await _add(db, title="Командировка", at=date(2026, 10, 20), end=date(2026, 10, 25))
    lesson = await _add(db, title="Английский", at=EVENING, end=datetime(2026, 10, 12, 19, 30))
    assert tree.render_item(trip) == f"- [ ] Командировка  at:2026-10-20  end:2026-10-25  ^{trip.id}"
    assert tree.render_item(lesson) == (
        f"- [ ] Английский  at:2026-10-12T18:00  end:2026-10-12T19:30  ^{lesson.id}"
    )


async def test_the_answer_prints_a_date_for_a_whole_day(api, now):
    response = await api.post(
        "/api/items",
        json={"kind": "event", "title": "Командировка", "at": "2026-10-20", "end": "2026-10-25",
              "said": "командировка", "reason": "план"},
    )
    answer = response.json()
    assert (answer["at"], answer["end"]) == ("2026-10-20", "2026-10-25")
    timed = await api.post(
        "/api/items",
        json={"kind": "event", "title": "Английский", "at": "2026-10-12T18:00", "said": "английский", "reason": "план"},
    )
    assert (timed.json()["at"], timed.json()["end"]) == ("2026-10-12T18:00", None)


@pytest.mark.parametrize("field", ["at", "end"])
@pytest.mark.parametrize("bad", ["garbage", "", "2026-02-30", "2026-10-20T25:00", 1760000000, 20261020])
async def test_a_bad_date_over_the_api_is_a_refusal_not_a_crash(api, now, field, bad):
    body = {"kind": "event", "title": "Поездка", "at": "2026-10-20", "said": "поездка", "reason": "план"}
    body[field] = bad
    response = await api.post("/api/items", json=body)
    assert response.status_code == 422, response.text


async def test_a_task_with_a_date_only_at_is_refused_over_the_api_with_the_fix(api, now):
    response = await api.post(
        "/api/items",
        json={"kind": "task", "title": "Позвонить", "at": "2026-10-20", "said": "позвонить", "reason": "план"},
    )
    assert response.status_code == 422
    assert "`due` for a date" in response.json()["detail"]


async def test_a_task_with_a_date_only_at_is_refused_with_the_fix(db, now):
    with pytest.raises(Refused, match="a task takes `due` for a date, `at` for a date and time"):
        await _add(db, kind="task", at=date(2026, 10, 20))


async def test_update_switches_between_a_day_and_a_moment(db, now):
    trip = await _add(db, at=date(2026, 10, 20))
    assert trip.all_day
    timed = await _update(db, trip.id, 1, {"at": datetime(2026, 10, 20, 18, 0)})
    assert (timed.all_day, timed.at) == (False, datetime(2026, 10, 20, 18, 0))
    midnight = await _update(db, trip.id, 2, {"at": datetime(2026, 10, 21, 0, 0)})
    assert (midnight.all_day, midnight.at) == (False, datetime(2026, 10, 21, 0, 0))
    day = await _update(db, trip.id, 3, {"at": date(2026, 10, 22)})
    assert (day.all_day, day.at) == (True, datetime(2026, 10, 22, 0, 0))


async def test_a_task_cannot_become_whole_day_by_update(db, now):
    task = await _add(db, kind="task", at=EVENING)
    with pytest.raises(Refused, match="a task takes `due` for a date"):
        await _update(db, task.id, 1, {"at": date(2026, 10, 20)})


async def test_update_journals_a_whole_day_as_a_date(db, now):
    trip = await _add(db, at=date(2026, 10, 20))
    await _update(db, trip.id, 1, {"at": date(2026, 10, 22)})
    async with db.read() as session:
        entry = (await session.scalars(select(Journal).where(Journal.op == "item_update"))).one()
    assert entry.detail == {"before": {"at": "2026-10-20"}, "after": {"at": "2026-10-22"}}


async def test_a_whole_day_event_reminds_from_the_start_of_the_day(db, now):
    await _add(db, title="День рождения", at=date(2026, 10, 20), remind=["P1D", "PT0M"])
    # 09:00 в Берлине летом — 07:00 UTC: накануне и в сам день.
    assert await _fires(db) == [datetime(2026, 10, 19, 7, 0, tzinfo=UTC), datetime(2026, 10, 20, 7, 0, tzinfo=UTC)]


async def test_a_repeating_whole_day_event_reminds_every_year_from_the_start_of_the_day(db, now):
    await _add(db, title="День рождения", at=date(2020, 3, 14), rrule="FREQ=YEARLY", remind=["PT0M"])
    # 14 марта 2027 в Берлине — ещё зима: 09:00 местного — это 08:00 UTC.
    assert await _fires(db) == [datetime(2027, 3, 14, 8, 0, tzinfo=UTC)]


# --- end: длительность ---


async def test_a_timed_event_has_a_range(db, now):
    lesson = await _add(db, at=EVENING, end=datetime(2026, 10, 12, 19, 30))
    assert lesson.end_at == datetime(2026, 10, 12, 19, 30)
    assert lesson.all_day is False


@pytest.mark.parametrize(
    "over, message",
    [
        ({"at": EVENING, "end": datetime(2026, 10, 12, 17, 0)}, "`end` must be after `at`"),
        ({"at": EVENING, "end": EVENING}, "`end` must be after `at`"),
        ({"at": date(2026, 10, 25), "end": date(2026, 10, 20)}, "`end` must not be before `at`"),
        ({"at": EVENING, "end": date(2026, 10, 13)}, "same form"),
        ({"at": date(2026, 10, 20), "end": datetime(2026, 10, 21, 12, 0)}, "same form"),
        ({"kind": "task", "at": EVENING, "end": datetime(2026, 10, 12, 19, 0)}, "`end` is for events only"),
        ({"kind": "task", "due": date(2026, 10, 20), "end": date(2026, 10, 21)}, "`end` is for events only"),
        ({"end": datetime(2026, 10, 12, 19, 0)}, "needs `at`"),
        ({"at": EVENING, "end": datetime(2026, 10, 12, 19, 0, tzinfo=UTC)}, "without an offset"),
        ({"at": EVENING.replace(tzinfo=UTC), "end": datetime(2026, 10, 12, 19, 0)}, "without an offset"),
    ],
)
async def test_end_is_refused(db, now, over, message):
    with pytest.raises(Refused, match=message):
        await _add(db, **over)


async def test_an_event_cannot_run_longer_than_a_year(db, now):
    year = await _add(db, at=date(2026, 10, 12), end=date(2027, 10, 13))
    assert year.end_at == datetime(2027, 10, 13, 0, 0)
    with pytest.raises(Refused, match="longer than 366 days"):
        await _add(db, at=date(2026, 10, 12), end=date(2027, 10, 14))
    with pytest.raises(Refused, match="longer than 366 days"):
        await _add(db, at=datetime(2020, 1, 1, 0, 0), end=datetime(2200, 1, 1, 0, 0))


async def test_end_may_be_the_same_day_for_a_whole_day(db, now):
    one = await _add(db, at=date(2026, 10, 20), end=date(2026, 10, 20))
    assert one.end_at == datetime(2026, 10, 20, 0, 0)


async def test_update_clears_and_moves_the_range(db, now):
    trip = await _add(db, at=date(2026, 10, 20), end=date(2026, 10, 25))
    moved = await _update(db, trip.id, 1, {"at": date(2026, 10, 21), "end": date(2026, 10, 26)})
    assert (moved.at, moved.end_at) == (datetime(2026, 10, 21, 0, 0), datetime(2026, 10, 26, 0, 0))
    cleared = await _update(db, trip.id, 2, {"end": None})
    assert (cleared.end_at, cleared.at) == (None, datetime(2026, 10, 21, 0, 0))
    again = await _update(db, trip.id, 3, {"end": date(2026, 10, 23)})
    assert again.end_at == datetime(2026, 10, 23, 0, 0)


async def test_update_that_breaks_the_range_says_to_send_both(db, now):
    trip = await _add(db, at=date(2026, 10, 20), end=date(2026, 10, 25))
    with pytest.raises(Refused, match="send both `at` and `end`"):
        await _update(db, trip.id, 1, {"at": datetime(2026, 10, 20, 18, 0)})
    with pytest.raises(Refused, match="send both `at` and `end`"):
        await _update(db, trip.id, 1, {"at": date(2026, 10, 27)})
    with pytest.raises(Refused, match="send both `at` and `end`"):
        await _update(db, trip.id, 1, {"end": datetime(2026, 10, 25, 12, 0)})
    with pytest.raises(Refused, match="send both `at` and `end`"):
        await _update(db, trip.id, 1, {"end": date(2026, 10, 19)})
    # Оба сразу в новом виде — можно.
    timed = await _update(
        db, trip.id, 1, {"at": datetime(2026, 10, 20, 18, 0), "end": datetime(2026, 10, 25, 12, 0)}
    )
    assert (timed.all_day, timed.end_at) == (False, datetime(2026, 10, 25, 12, 0))


async def test_update_that_moves_a_timed_event_past_its_end_says_to_send_both(db, now):
    lesson = await _add(db, at=EVENING, end=datetime(2026, 10, 12, 19, 0))
    with pytest.raises(Refused, match="send both `at` and `end`"):
        await _update(db, lesson.id, 1, {"in": "P1D"})
    later = await _update(db, lesson.id, 1, {"at": datetime(2026, 10, 13, 18, 0), "end": datetime(2026, 10, 13, 19, 0)})
    assert later.end_at == datetime(2026, 10, 13, 19, 0)


async def test_update_journals_the_range(db, now):
    trip = await _add(db, at=date(2026, 10, 20), end=date(2026, 10, 25))
    await _update(db, trip.id, 1, {"end": None})
    async with db.read() as session:
        entry = (await session.scalars(select(Journal).where(Journal.op == "item_update"))).one()
    assert entry.detail == {"before": {"end": "2026-10-25"}, "after": {"end": None}}


# --- окно и повестка ---


async def test_a_whole_day_range_shows_on_each_of_its_days(db, ctx, now, monkeypatch):
    _clock(monkeypatch, 2026, 10, 19, 10, 0)  # понедельник; неделя 19–25 октября
    trip = await _add(db, title="Командировка", at=date(2026, 10, 20), end=date(2026, 10, 25))
    async with db.read() as session:
        for day in range(19, 28):
            found = await items.query(session, owner_tz=TZ, start=date(2026, 10, day), end=date(2026, 10, day))
            assert [item.id for item in found] == ([trip.id] if 20 <= day <= 25 else []), day
        whole = await items.query(session, owner_tz=TZ, start=date(2026, 10, 22), end=date(2026, 10, 22))
        assert [item.id for item in whole] == [trip.id]
    week = _by_day(await _text(db, ctx, "views/week.md"))
    shown = [day for day, lines in week.items() if any("Командировка" in line for line in lines)]
    assert shown == [f"2026-10-{day}" for day in range(20, 26)]


async def test_a_timed_end_exactly_at_midnight_does_not_count_that_day(db, now):
    train = await _add(db, title="Поезд", at=datetime(2026, 10, 14, 22, 0), end=datetime(2026, 10, 15, 0, 0))
    flight = await _add(db, title="Рейс", at=datetime(2026, 10, 14, 22, 0), end=datetime(2026, 10, 15, 0, 30))

    async def ids(day):
        async with db.read() as session:
            return {item.id for item in await items.query(session, owner_tz=TZ, start=day, end=day)}

    assert await ids(date(2026, 10, 14)) == {train.id, flight.id}
    assert await ids(date(2026, 10, 15)) == {flight.id}
    assert await ids(date(2026, 10, 16)) == set()


async def test_a_repeating_event_has_the_same_length_on_every_occurrence(db, now):
    night = await _add(
        db, title="Ночная смена", at=datetime(2026, 10, 12, 22, 0), end=datetime(2026, 10, 13, 6, 0),
        rrule="FREQ=WEEKLY",
    )
    camp = await _add(
        db, title="Лагерь", at=date(2026, 10, 20), end=date(2026, 10, 22), rrule="FREQ=MONTHLY",
    )

    async def ids(day):
        async with db.read() as session:
            return {item.id for item in await items.query(session, owner_tz=TZ, start=day, end=day)}

    # Смена начинается в понедельник вечером и доходит до вторника; окно во вторник её видит.
    assert await ids(date(2026, 10, 13)) == {night.id}
    assert await ids(date(2026, 10, 20)) == {night.id, camp.id}
    assert await ids(date(2026, 10, 21)) == {camp.id}
    assert await ids(date(2026, 10, 14)) == set()
    # Лагерь — три дня подряд раз в месяц: 20–22 ноября.
    assert await ids(date(2026, 11, 22)) == {camp.id}
    assert await ids(date(2026, 11, 25)) == set()


# --- лента ---


async def _feed(db, to_add):
    async with db.write() as session:
        for args in to_add:
            await items.add(
                session, client="claude", owner_tz=TZ, source=Source(said="так сказал владелец"), reason="тест",
                **{"kind": "event", **args},
            )
    app = create_app(Settings(_env_file=None, owner_tz=TZ, ics_token=SECRET), db=db)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as http:
        response = await http.get(f"/calendar/{SECRET}.ics")
    return {str(event["summary"]): event for event in Calendar.from_ical(response.content).walk("VEVENT")}, response


async def test_feed_writes_dtend_for_a_range_a_whole_day_and_the_default(db, now):
    events, _ = await _feed(
        db,
        [
            {"title": "Командировка", "at": date(2026, 10, 20), "end": date(2026, 10, 25)},
            {"title": "Выходной", "at": date(2026, 10, 26)},
            {"title": "Встреча", "at": datetime(2026, 10, 14, 18, 0), "end": datetime(2026, 10, 14, 19, 30)},
            {"title": "Звонок", "at": datetime(2026, 10, 14, 20, 0)},
        ],
    )
    trip, free, meeting, call = (events[name] for name in ("Командировка", "Выходной", "Встреча", "Звонок"))
    # Целый день — даты, а конец ленты не включает последний день: 25 октября -> 26-е.
    assert (trip["dtstart"].dt, trip["dtend"].dt) == (date(2026, 10, 20), date(2026, 10, 26))
    assert (free["dtstart"].dt, free["dtend"].dt) == (date(2026, 10, 26), date(2026, 10, 27))
    assert type(trip["dtstart"].dt) is date
    assert meeting["dtend"].dt.replace(tzinfo=None) == datetime(2026, 10, 14, 19, 30)
    assert meeting["dtend"].params["TZID"] == TZ
    assert call["dtend"].dt - call["dtstart"].dt == timedelta(hours=1)


async def test_feed_ends_a_whole_day_rule_with_a_date(db, now):
    events, response = await _feed(
        db,
        [{"title": "День рождения", "at": date(2020, 3, 14), "rrule": "FREQ=YEARLY;UNTIL=20301231T235959"}],
    )
    birthday = events["День рождения"]
    assert (birthday["dtstart"].dt, birthday["dtend"].dt) == (date(2020, 3, 14), date(2020, 3, 15))
    assert b"UNTIL=20301231" in response.content
    assert b"UNTIL=20301231T" not in response.content
