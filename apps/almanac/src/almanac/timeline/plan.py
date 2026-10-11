"""Когда напоминать. Чистые функции: без базы и без часов."""

from collections.abc import Iterator
from datetime import UTC, datetime, time, timedelta

from almanac import checks
from almanac.models import Item
from almanac.timeline import occur

# Сколько повторений просматривает `upcoming`: у любого смещения из `checks.duration` хватает с запасом.
MAX_OCCURRENCES = 60


def parse_day_start(text: str) -> time:
    hours, minutes = text.split(":")
    return time(int(hours), int(minutes))


def anchors(item: Item, owner_tz: str, day_start: str, after: datetime) -> Iterator[datetime]:
    """Опорные моменты элемента не раньше `after`, по возрастанию — в поясе элемента.

    Опорный момент — `at`, а без него `due` в начале дня. У неповторяющегося элемента он один.
    """
    local_zone = occur.zone(item.tz or owner_tz)
    if item.at is not None:
        local_after = after.astimezone(local_zone).replace(tzinfo=None)
        if item.rrule is None:
            if item.at >= local_after:
                yield item.at.replace(tzinfo=local_zone)
        else:
            rule = occur.rule(item.rrule, item.at)
            for moment in rule.xafter(local_after, count=MAX_OCCURRENCES, inc=True):
                yield moment.replace(tzinfo=local_zone)
    elif item.due is not None:
        moment = datetime.combine(item.due, parse_day_start(day_start), tzinfo=local_zone)
        if moment >= after:
            yield moment


def fire_time(anchor: datetime, offset: timedelta) -> datetime:
    """Момент напоминания в UTC для опорного момента `anchor` (в поясе элемента).

    Целые дни отсчитываются по местным часам: «за день» остаётся тем же часом и после перевода часов.
    Остаток меньше суток — настоящее время: полчаса — это полчаса.
    """
    whole_days = timedelta(days=offset.days)
    return (anchor - whole_days).astimezone(UTC) - (offset - whole_days)


def upcoming(item: Item, owner_tz: str, day_start: str, now: datetime) -> list[tuple[datetime, datetime]]:
    """Пары (опорный момент, момент напоминания) в UTC, по возрастанию напоминания.

    Берутся ближайшие повторения, у которых ещё есть будущие напоминания, и просмотр идёт
    настолько далеко вперёд, насколько нужно самому длинному смещению: пока следующее
    повторение может дать напоминание раньше уже найденных. Совпавшие моменты не удваиваются —
    за ними остаётся более раннее повторение.
    """
    if item.status != "open" or not item.remind:
        return []
    offsets = [checks.duration(value) for value in item.remind]
    found: dict[datetime, datetime] = {}
    for anchor in anchors(item, owner_tz, day_start, now):
        moments = [fire_time(anchor, offset) for offset in offsets]
        if found and min(moments) > min(found):
            break
        for moment in moments:
            if moment > now:
                found.setdefault(moment, anchor.astimezone(UTC))
    return sorted(((anchor, fire) for fire, anchor in found.items()), key=lambda pair: pair[1])
