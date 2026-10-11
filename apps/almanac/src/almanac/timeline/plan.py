"""Когда напоминать. Чистые функции: без базы и без часов."""

from datetime import UTC, datetime, time, timedelta

from almanac import checks
from almanac.models import Item
from almanac.timeline import occur


def parse_day_start(text: str) -> time:
    hours, minutes = text.split(":")
    return time(int(hours), int(minutes))


def next_anchor(item: Item, owner_tz: str, day_start: str, after: datetime) -> datetime | None:
    """Ближайший опорный момент элемента не раньше `after` — в поясе элемента.

    Опорный момент — `at`, а без него `due` в начале дня.
    """
    local_zone = occur.zone(item.tz or owner_tz)
    if item.at is not None:
        local_after = after.astimezone(local_zone).replace(tzinfo=None)
        if item.rrule is None:
            moment = item.at if item.at >= local_after else None
        else:
            moment = occur.rule(item.rrule, item.at).after(local_after, inc=True)
        return moment.replace(tzinfo=local_zone) if moment else None
    if item.due is not None:
        moment = datetime.combine(item.due, parse_day_start(day_start), tzinfo=local_zone)
        return moment if moment >= after else None
    return None


def upcoming(item: Item, owner_tz: str, day_start: str, now: datetime) -> list[tuple[datetime, datetime]]:
    """Пары (опорный момент, момент напоминания) в UTC для ближайшего повторения,
    у которого ещё есть будущие напоминания."""
    if item.status != "open" or not item.remind:
        return []
    offsets = [checks.duration(value) for value in item.remind]
    after = now
    for _ in range(2):
        anchor = next_anchor(item, owner_tz, day_start, after)
        if anchor is None:
            return []
        fires = sorted({anchor - offset for offset in offsets if anchor - offset > now})
        if fires:
            return [(anchor.astimezone(UTC), fire.astimezone(UTC)) for fire in fires]
        if item.rrule is None:
            return []
        # У этого повторения всё уже отправлено или прошло — смотрим следующее.
        after = anchor + timedelta(seconds=1)
    return []
