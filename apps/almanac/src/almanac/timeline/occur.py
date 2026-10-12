"""Моменты события в окне. Чистые функции: без базы и без часов."""

import re
from datetime import UTC, date, datetime, time, timedelta
from itertools import islice
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from dateutil.rrule import rrulebase, rrulestr

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
COUNT = re.compile(r"\bCOUNT\s*=", re.IGNORECASE)
# Секундная и минутная частота отказываются по имени, без перебора: с условием, которое не выполняется ни разу,
# он шёл бы секундными шагами годами.
FINE = re.compile(r"\bFREQ\s*=\s*(?:SECONDLY|MINUTELY)\b", re.IGNORECASE)
# Плотность смотрим по первым повторениям: если 25-е приходится меньше чем на сутки позже первого, в сутки их больше 24.
DENSITY_SAMPLE = 25
DENSITY_SPAN = timedelta(hours=24)


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


def check_density(parsed: rrulebase, text: str) -> None:
    """Правило повторяется не чаще раза в час, иначе отказ.

    Плотный ряд заставлял бы каждое чтение повестки и каждый тик перебирать сотни тысяч моментов,
    а единственный воркер всё это время молчал бы. Решает само правило, без окна и без часов:
    берутся первые `DENSITY_SAMPLE` повторений, перебор на них и кончается.
    """
    refusal = f"rrule {text!r} repeats more often than once an hour; the densest allowed is FREQ=HOURLY"
    if FINE.search(text):
        raise Refused(refusal)
    sample = list(islice(parsed, DENSITY_SAMPLE))
    if len(sample) == DENSITY_SAMPLE and sample[-1] - sample[0] < DENSITY_SPAN:
        raise Refused(refusal)


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


def next_after(start: datetime, rrule: str, after: datetime) -> datetime | None:
    """Первое повторение правила строго позже `after` — местное время без пояса; `None`, когда правило кончилось.

    Правило разворачивается от `start`. У задачи это её текущий срок: с каждым закрытием он сдвигается
    на повторение, а значит, остаётся членом прежнего ряда.
    """
    return rule(rrule, start).after(after, inc=False)


def days(due: date, rrule: str, low: date, high: date) -> list[date]:
    """Дни повторения задачи, у которой есть срок, но нет времени, в окне `[low, high]` — по возрастанию.

    Правило разворачивается от полуночи `due`; время суток в ответ не идёт, а дни не повторяются.
    """
    found = rule(rrule, datetime.combine(due, time.min)).between(
        datetime.combine(low, time.min), datetime.combine(high, time.max), inc=True
    )
    return sorted({moment.date() for moment in found})


def from_now(now: datetime, offset: timedelta, tz: str) -> datetime:
    """Местное время через `offset` от `now`, до целой минуты вверх — без пояса, как хранится `at`.

    Целые дни отсчитываются по местным часам («через день» — тот же час), остаток — настоящее время.
    """
    local_zone = zone(tz)
    whole_days = timedelta(days=offset.days)
    shifted = (now.astimezone(local_zone).replace(tzinfo=None) + whole_days).replace(tzinfo=local_zone)
    moment = (shifted.astimezone(UTC) + (offset - whole_days)).astimezone(local_zone).replace(tzinfo=None)
    if moment.second or moment.microsecond:
        moment = moment.replace(second=0, microsecond=0) + timedelta(minutes=1)
    return moment
