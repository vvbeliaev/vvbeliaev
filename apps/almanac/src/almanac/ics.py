"""Календарная лента: события и задачи со сроком в iCalendar. Только чтение.

Подписанный календарь обновляется с задержкой, поэтому лента — экран, а не будильник.
"""

from datetime import UTC, timedelta
from zoneinfo import ZoneInfo

from icalendar import Calendar, Event, vRecur

from almanac.clock import utcnow
from almanac.models import Item
from almanac.timeline import occur

EVENT_LENGTH = timedelta(hours=1)
TASK_LENGTH = timedelta(minutes=30)


def _recur(rule: str, zone: ZoneInfo) -> vRecur:
    """Правило повтора для ленты. `UNTIL` хранится в местном времени, а RFC 5545 при `DTSTART` с поясом
    требует UTC: переводим из пояса элемента и пишем с `Z`."""
    recur = vRecur.from_ical(rule.removeprefix("RRULE:"))
    if "UNTIL" in recur:
        recur["UNTIL"] = [moment.replace(tzinfo=zone).astimezone(UTC) for moment in recur["UNTIL"]]
    return recur


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
        zone = occur.zone(item.tz or owner_tz)
        if item.kind == "event":
            start = item.at.replace(tzinfo=zone)
            event.add("summary", item.title)
            event.add("dtstart", start)
            event.add("dtend", start + EVENT_LENGTH)
            if item.rrule:
                event.add("rrule", _recur(item.rrule, zone))
        elif item.at is not None:
            # Задача со временем — короткое событие; если есть и срок, время точнее.
            start = item.at.replace(tzinfo=zone)
            event.add("summary", f"☐ {item.title}")
            event.add("dtstart", start)
            event.add("dtend", start + TASK_LENGTH)
        elif item.due is not None:
            event.add("summary", f"☐ {item.title}")
            event.add("dtstart", item.due)
            event.add("dtend", item.due + timedelta(days=1))
        else:
            continue
        if item.note:
            event.add("description", item.note)
        calendar.add_component(event)
    # `TZID=…` без VTIMEZONE клиенты читают по-разному: описание пояса едет в самой ленте.
    calendar.add_missing_timezones()
    return calendar.to_ical()
