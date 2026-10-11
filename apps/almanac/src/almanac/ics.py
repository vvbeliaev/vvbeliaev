"""Календарная лента: события и задачи со сроком в iCalendar. Только чтение.

Подписанный календарь обновляется с задержкой, поэтому лента — экран, а не будильник.
"""

from datetime import timedelta

from icalendar import Calendar, Event, vRecur

from almanac.clock import utcnow
from almanac.models import Item
from almanac.timeline import occur


def render(items: list[Item], owner_tz: str) -> bytes:
    calendar = Calendar()
    calendar.add("prodid", "-//almanac//almanac//")
    calendar.add("version", "2.0")
    calendar.add("x-wr-calname", "almanac")
    stamp = utcnow()
    for item in items:
        if item.status != "open":
            continue
        event = Event()
        event.add("uid", f"{item.id}@almanac")
        event.add("dtstamp", stamp)
        if item.kind == "event":
            start = item.at.replace(tzinfo=occur.zone(item.tz or owner_tz))
            event.add("summary", item.title)
            event.add("dtstart", start)
            event.add("dtend", start + timedelta(hours=1))
            if item.rrule:
                event.add("rrule", vRecur.from_ical(item.rrule.removeprefix("RRULE:")))
        elif item.due is not None:
            event.add("summary", f"☐ {item.title}")
            event.add("dtstart", item.due)
            event.add("dtend", item.due + timedelta(days=1))
        else:
            continue
        if item.note:
            event.add("description", item.note)
        calendar.add_component(event)
    return calendar.to_ical()
