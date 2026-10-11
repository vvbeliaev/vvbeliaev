from datetime import date, datetime

from httpx import ASGITransport, AsyncClient
from icalendar import Calendar

from almanac.app import create_app
from almanac.config import Settings
from almanac.store import items
from almanac.store.source import Source

TZ = "Europe/Berlin"
SECRET = "feed-" + "a" * 24


async def _seed(db):
    async with db.write() as session:
        await items.add(
            session, client="claude", owner_tz=TZ, kind="event", title="Английский",
            at=datetime(2026, 10, 5, 18, 0), rrule="FREQ=WEEKLY",
            source=Source(said="английский по понедельникам"), reason="расписание",
        )
        await items.add(
            session, client="claude", owner_tz=TZ, kind="task", title="Сдать отчёт", due=date(2026, 10, 14),
            source=Source(said="отчёт к среде"), reason="срок",
        )
        await items.add(
            session, client="claude", owner_tz=TZ, kind="task", title="Разобрать шкаф",
            source=Source(said="шкаф когда-нибудь"), reason="без срока",
        )


async def test_feed_lists_events_and_dated_tasks(db, now):
    await _seed(db)
    settings = Settings(_env_file=None, owner_tz=TZ, ics_token=SECRET)
    app = create_app(settings, db=db)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as http:
        feed = await http.get(f"/calendar/{SECRET}.ics")
        wrong = await http.get("/calendar/guess.ics")
    assert feed.status_code == 200
    assert feed.headers["content-type"].startswith("text/calendar")
    assert wrong.status_code == 404

    events = {str(event["summary"]): event for event in Calendar.from_ical(feed.content).walk("VEVENT")}
    assert set(events) == {"Английский", "☐ Сдать отчёт"}
    lesson = events["Английский"]
    assert lesson["dtstart"].dt.replace(tzinfo=None) == datetime(2026, 10, 5, 18, 0)
    assert lesson["dtstart"].params["TZID"] == TZ
    assert lesson["rrule"]["FREQ"] == ["WEEKLY"]
    assert events["☐ Сдать отчёт"]["dtstart"].dt == date(2026, 10, 14)


async def test_feed_carries_the_timezone_definition_of_its_events(db, now):
    await _seed(db)
    settings = Settings(_env_file=None, owner_tz=TZ, ics_token=SECRET)
    app = create_app(settings, db=db)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as http:
        feed = await http.get(f"/calendar/{SECRET}.ics")
    # `TZID=Europe/Berlin` без VTIMEZONE клиенты читают по-разному: описание пояса едет в самой ленте.
    zones = list(Calendar.from_ical(feed.content).walk("VTIMEZONE"))
    assert [str(zone["tzid"]) for zone in zones] == [TZ]
    assert b"BEGIN:VTIMEZONE" in feed.content


async def test_feed_is_off_without_a_token(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as http:
        assert (await http.get("/calendar/.ics")).status_code == 404
        assert (await http.get("/calendar/anything.ics")).status_code == 404
