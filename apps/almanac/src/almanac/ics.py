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


def _recur(rule: str, zone: ZoneInfo, *, dated: bool = False) -> vRecur:
    """Правило повтора для ленты. `UNTIL` хранится в местном времени, а RFC 5545 при `DTSTART` с поясом
    требует UTC: переводим из пояса элемента и пишем с `Z`. При `DTSTART`-дате `UNTIL` тоже дата."""
    recur = vRecur.from_ical(rule.removeprefix("RRULE:"))
    if "UNTIL" in recur:
        if dated:
            recur["UNTIL"] = [moment.date() for moment in recur["UNTIL"]]
        else:
            recur["UNTIL"] = [moment.replace(tzinfo=zone).astimezone(UTC) for moment in recur["UNTIL"]]
    return recur


def _event(item: Item, zone: ZoneInfo) -> Event | None:
    """Строка ленты для элемента или `None`, если показывать нечего: нет ни времени, ни срока."""
    event = Event()
    task = item.kind == "task"
    event.add("summary", f"☐ {item.title}" if task else item.title)
    if item.at is not None and item.all_day:
        # Конец в ленте не включает последний день: целый день `20` — это `DTSTART:20`, `DTEND:21`.
        event.add("dtstart", item.at.date())
        event.add("dtend", (item.end_at or item.at).date() + timedelta(days=1))
    elif item.at is not None:
        start = item.at.replace(tzinfo=zone)
        event.add("dtstart", start)
        # Задача со временем — короткое событие; у события без конца длина по умолчанию — час.
        length = TASK_LENGTH if task else EVENT_LENGTH
        event.add("dtend", item.end_at.replace(tzinfo=zone) if item.end_at else start + length)
    elif item.due is not None:
        event.add("dtstart", item.due)
        event.add("dtend", item.due + timedelta(days=1))
    else:
        return None
    if item.rrule:
        event.add("rrule", _recur(item.rrule, zone, dated=item.at is None or item.all_day))
    return event


def render(items: list[Item], owner_tz: str) -> bytes:
    calendar = Calendar()
    calendar.add("prodid", "-//almanac//almanac//")
    calendar.add("version", "2.0")
    calendar.add("x-wr-calname", "almanac")
    stamp = utcnow()
    for item in items:
        if item.status != "open":
            continue
        event = _event(item, occur.zone(item.tz or owner_tz))
        if event is None:
            continue
        event.add("uid", f"{item.id}@almanac")
        event.add("dtstamp", stamp)
        if item.note:
            event.add("description", item.note)
        calendar.add_component(event)
    # `TZID=…` без VTIMEZONE клиенты читают по-разному: описание пояса едет в самой ленте.
    calendar.add_missing_timezones()
    return calendar.to_ical()
