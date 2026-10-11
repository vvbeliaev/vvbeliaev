"""Моменты события в окне. Чистые функции: без базы и без часов."""

import re
from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from dateutil.rrule import rrulestr

from almanac.errors import Refused


def zone(name: str) -> ZoneInfo:
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError) as error:
        raise Refused(f"unknown time zone {name!r}; use an IANA name like Europe/Berlin") from error


# Лишние строки и даты `rrulestr` принимает молча: второе правило, свой DTSTART, исключения.
EXTRA = re.compile(r"DTSTART|EXDATE|RDATE", re.IGNORECASE)
UTC_UNTIL = re.compile(r"UNTIL=[0-9T]*Z", re.IGNORECASE)
# `UNTIL=20261231` без времени dateutil читает как полночь: последний день выпал бы из повтора целиком.
DATE_UNTIL = re.compile(r"UNTIL=[0-9]{8}(?![0-9T])", re.IGNORECASE)


def rule(text: str, start: datetime):
    """Правило повтора RFC 5545 с отсчётом от местного времени `start`.

    Одно правило, одной строкой, без DTSTART, EXDATE и RDATE: начало берётся из `start`.
    """
    if "\n" in text or "\r" in text or EXTRA.search(text):
        raise Refused(f"bad rrule {text!r}: one rule only, no DTSTART, EXDATE or RDATE")
    if UTC_UNTIL.search(text):
        raise Refused(f"bad rrule {text!r}: write UNTIL as local time without Z")
    if DATE_UNTIL.search(text):
        raise Refused(f"bad rrule {text!r}: write UNTIL as local date-time like 20261231T235959")
    try:
        return rrulestr(text, dtstart=start)
    except (ValueError, TypeError, KeyError) as error:
        raise Refused(f"bad rrule {text!r}: {error}") from error


def occurrences(at: datetime, rrule: str | None, tz: str, start: datetime, end: datetime) -> list[datetime]:
    """Моменты события в окне `[start, end)` — осведомлённые, в поясе события.

    `at` — местное время без пояса. Правило разворачивается в местном времени,
    поэтому 18:00 остаётся 18:00 и после перевода часов.
    """
    local_zone = zone(tz)
    low = start.astimezone(local_zone).replace(tzinfo=None)
    high = end.astimezone(local_zone).replace(tzinfo=None)
    if rrule is None:
        local = [at] if low <= at < high else []
    else:
        local = [moment for moment in rule(rrule, at).between(low, high, inc=True) if moment < high]
    return [moment.replace(tzinfo=local_zone) for moment in local]
