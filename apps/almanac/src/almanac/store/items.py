"""Элементы: задачи и события — всё, что запрашивается или срабатывает."""

from collections.abc import Sequence
from datetime import UTC, date, datetime, time, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from almanac import checks
from almanac.clock import utcnow
from almanac.errors import Conflict, NotFound, Refused
from almanac.ids import new_id
from almanac.models import Item, ItemFact
from almanac.store import firings, journal, pages
from almanac.store.source import Source, resolve
from almanac.timeline import occur, plan

KINDS = ("task", "event")
ITEM_STATUSES = ("open", "done", "cancelled")
STATUSES = {"task": ITEM_STATUSES, "event": ("open", "cancelled")}
FIELDS = ("title", "note", "list", "page", "due", "at", "end", "in", "tz", "rrule", "remind", "status")
NOT_NULL = ("title", "status")
STATUS_FILTERS = ("open", "done", "cancelled", "any")
# Имя поля в запросе и в API -> имя атрибута: `list` и `end` занимают чужие слова, `in` — не поле вовсе.
ATTRIBUTES = {"list": "list_", "end": "end_at"}
AT_OR_IN = (
    "pass `at` or `in`, not both: `at` is a date or a local date and time, `in` is how far from now (PT20M, P2D)"
)
DAY = timedelta(days=1)
# Событие длиннее года — почти наверняка опечатка в дате, а гигантская длина ломала бы расчёт дней при каждом чтении повестки.
MAX_SPAN = timedelta(days=366)
# Годы, между которыми лежат `at`, `end` и `due`: дата 9999-12-31 не терпит прибавленных суток, и лента календаря падала бы целиком.
# Нижняя граница — год рождения: день рождения начинается в нём.
MIN_YEAR, MAX_YEAR = 1900, 2200
# Окно `items` шире года перебирало бы повторения каждого элемента за все эти дни: просят сузить.
MAX_WINDOW_DAYS = 366


def _attr(field: str) -> str:
    return ATTRIBUTES.get(field, field)


def _plain(value: Any) -> Any:
    """Значение поля для журнала: даты и время строкой, список копией."""
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, list):
        return list(value)
    return value


def moment_text(value: datetime | None, all_day: bool) -> str | None:
    """`at` и `end` для ответа и строки элемента: целый день — датой, остальное — с точностью до минуты."""
    if value is None:
        return None
    return value.date().isoformat() if all_day else value.isoformat(timespec="minutes")


def _shown(item: Item, field: str) -> Any:
    """Значение поля для журнала; `at` и `end` целого дня — датой, как их видит владелец."""
    value = getattr(item, _attr(field))
    if field in ("at", "end") and item.all_day and value is not None:
        return value.date().isoformat()
    return _plain(value)


def _moment(value: date | datetime | None) -> tuple[datetime | None, bool]:
    """(время для хранения, дата ли это). Дата без часа — целый день, а полночь с часом — момент."""
    if value is None:
        return None, False
    if isinstance(value, datetime):
        return value, False
    return datetime.combine(value, time.min), True


def _form(is_date: bool) -> str:
    return "a date" if is_date else "a date and time"


def _check_years(item: Item) -> None:
    """`at`, `end` и `due` лежат между `MIN_YEAR` и `MAX_YEAR` включительно; отказ называет поле."""
    for name, value in (("at", item.at), ("end", item.end_at), ("due", item.due)):
        if value is not None and not MIN_YEAR <= value.year <= MAX_YEAR:
            raise Refused(f"`{name}` must fall between the years {MIN_YEAR} and {MAX_YEAR}: check the date")


def _check_end(item: Item, end_is_date: bool) -> None:
    """Конец события согласован с началом: той же формы и позже. Отказ просит прислать оба поля."""
    if item.kind != "event":
        raise Refused("`end` is for events only; a task has `due` for its deadline")
    if item.end_at.tzinfo is not None:
        raise Refused("`end` is local time without an offset; put the zone name in `tz`")
    if end_is_date != item.all_day:
        raise Refused(
            f"`end` is {_form(end_is_date)} but `at` is {_form(item.all_day)}: use the same form for both, "
            "and send both `at` and `end` together when you change one"
        )
    if item.all_day and item.end_at < item.at:
        raise Refused(
            "`end` must not be before `at`: for a whole day it is the last day, inclusive; "
            "send both `at` and `end` together when you move one"
        )
    if not item.all_day and item.end_at <= item.at:
        raise Refused("`end` must be after `at`; send both `at` and `end` together when you move one")
    if item.end_at - item.at > MAX_SPAN:
        raise Refused(f"an event cannot run longer than {MAX_SPAN.days} days: check `end`, or split it")


def _check_rule(item: Item) -> None:
    """Правило повтора: событию нужен `at`, задаче — `due` или `at`; у задачи нет `COUNT`."""
    if len(item.rrule) > checks.RRULE_LIMIT:
        raise Refused(f"rrule is longer than {checks.RRULE_LIMIT} characters")
    if item.kind == "task" and item.at is None and item.due is None:
        raise Refused("`rrule` on a task needs `due` or `at` to repeat from")
    start = item.at if item.at is not None else datetime.combine(item.due, time.min)
    occur.check_density(occur.rule(item.rrule, start), item.rrule)
    if item.kind == "task" and occur.COUNT.search(item.rrule):
        raise Refused(
            "COUNT is not allowed on a task: its start moves with every completion, so a count would never run "
            "out; use UNTIL, like FREQ=DAILY;UNTIL=20261231T235959"
        )


def _check(item: Item, owner_tz: str, *, end_is_date: bool = False) -> None:
    """Поля элемента согласованы между собой. Отказ называет поле, которое не сходится."""
    if item.kind not in KINDS:
        raise Refused(f"unknown kind {item.kind!r}; one of: {', '.join(KINDS)}")
    item.title = checks.one_line(item.title, name="title", limit=200)
    checks.no_secret(item.title, item.note)
    if item.kind == "event" and item.at is None:
        raise Refused(
            "an event needs `at` (a date, or a local date and time like 2026-10-14T18:00) or `in` (like PT20M)"
        )
    if item.at is not None and item.at.tzinfo is not None:
        raise Refused("`at` is local time without an offset; put the zone name in `tz`")
    _check_years(item)
    if item.all_day and item.kind != "event":
        raise Refused("a task takes `due` for a date, `at` for a date and time; a date alone in `at` is for events")
    if item.end_at is not None:
        _check_end(item, end_is_date)
    if item.list_ is not None:
        if item.kind != "task":
            raise Refused("`list` is for tasks only")
        if len(item.list_) > checks.LIST_LIMIT:
            raise Refused(f"list is longer than {checks.LIST_LIMIT} characters")
        if not checks.LIST_SLUG.fullmatch(item.list_):
            raise Refused(f"bad list {item.list_!r}: lowercase a-z, 0-9 and single dashes, like shopping")
    occur.zone(item.tz or owner_tz)
    if item.rrule is not None:
        _check_rule(item)
    if item.remind:
        if item.at is None and item.due is None:
            raise Refused("`remind` needs `at` or `due` to count from")
        for value in item.remind:
            checks.duration(value)
    if item.status not in STATUSES[item.kind]:
        raise Refused(
            f"unknown status {item.status!r} for a {item.kind}; one of: {', '.join(STATUSES[item.kind])}"
        )


def _from_now(offset: str, tz: str, now: datetime) -> datetime:
    """`at` по смещению `in`: сколько от «сейчас» в поясе элемента."""
    return occur.from_now(now, checks.duration(offset), tz)


async def add(
    session: AsyncSession,
    *,
    client: str,
    owner_tz: str,
    day_start: str = "09:00",
    kind: str,
    title: str,
    note: str = "",
    list_: str | None = None,
    page: str | None = None,
    due: date | None = None,
    at: date | datetime | None = None,
    end: date | datetime | None = None,
    in_: str | None = None,
    tz: str | None = None,
    rrule: str | None = None,
    remind: Sequence[str] = (),
    source: Source,
    reason: str,
) -> Item:
    """Создать элемент. `at` и `end` — дата (целый день) или местные дата и время; `in_` вместо `at`."""
    why = checks.reason(reason)
    now = utcnow()
    if in_ is not None:
        if at is not None:
            raise Refused(AT_OR_IN)
        at = _from_now(in_, tz or owner_tz, now)
    moment, all_day = _moment(at)
    finish, end_is_date = _moment(end)
    item = Item(
        id=new_id("i"), kind=kind, title=title, note=(note or "").strip(), list_=list_, page=page,
        due=due, at=moment, end_at=finish, all_day=all_day, tz=tz, rrule=rrule, remind=list(remind or ()),
        status="open", done_at=None, rev=1, created_at=now, updated_at=now,
    )
    _check(item, owner_tz, end_is_date=end_is_date)
    if page is not None:
        await pages.get(session, page)
    fact_ids = await resolve(session, client=client, source=source, allow_restructure=False)

    session.add(item)
    await session.flush()
    for fact_id in fact_ids:
        session.add(ItemFact(item_id=item.id, fact_id=fact_id))
    journal.record(
        session, client=client, op="item_add", target=item.id, reason=why, detail={"kind": kind, "facts": fact_ids}
    )
    await session.flush()
    await firings.replan(session, item, owner_tz=owner_tz, day_start=day_start)
    return item


def _fold_in(changes: dict[str, Any], item: Item, owner_tz: str, now: datetime) -> dict[str, Any]:
    """`in` — другой способ назвать `at`: момент считается сразу, дальше это обычная правка `at`."""
    folded = dict(changes)
    offset = folded.pop("in", None)
    if offset is not None:
        if "at" in folded:
            raise Refused(AT_OR_IN)
        folded["at"] = _from_now(offset, folded.get("tz", item.tz) or owner_tz, now)
    return folded


def _apply(item: Item, changes: dict[str, Any]) -> bool:
    """Записать правку в элемент. Возвращает, записан ли конец датой (иначе — датой и временем).

    Конец, которого правка не касается, остаётся в той форме, в какой был: в форме прежнего `at`.
    """
    end_is_date = item.all_day
    for name, value in changes.items():
        if value is None and name in NOT_NULL:
            raise Refused(f"{name} cannot be null")
        if name == "at":
            item.at, item.all_day = _moment(value)
        elif name == "end":
            item.end_at, end_is_date = _moment(value)
        else:
            if name == "note":
                value = (value or "").strip()
            if name == "remind":
                value = list(value or ())
            setattr(item, _attr(name), value)
    return end_is_date


def _advance(item: Item, owner_tz: str, now: datetime) -> tuple[Any, Any] | None:
    """Закрыто повторение задачи: срок переезжает на следующее. Возвращает (закрытое, следующее) или `None`.

    Следующее — первое повторение правила строго позже и закрытого, и «сейчас»: пропущенные дни
    в очередь не встают. У задачи только со сроком сравниваются даты. Если `at` и `due` оба есть,
    `due` сдвигается на столько же дней, на сколько ушло `at`.
    """
    local_now = now.astimezone(occur.zone(item.tz or owner_tz)).replace(tzinfo=None)
    if item.at is not None:
        closed = item.at
        following = occur.next_after(closed, item.rrule, max(closed, local_now))
        if following is None:
            return None
        if item.due is not None:
            item.due += following.date() - closed.date()
        item.at = following
        return _plain(closed), _plain(following)
    closed = item.due
    start = datetime.combine(closed, time.min)
    following = occur.next_after(start, item.rrule, datetime.combine(max(closed, local_now.date()), time.max))
    if following is None:
        return None
    item.due = following.date()
    return closed.isoformat(), item.due.isoformat()


def _done_detail(item: Item, advanced: tuple[Any, Any], changes: dict[str, Any], before: dict, due: Any) -> dict:
    """Запись журнала о закрытом повторении: что закрыто, куда ушло, и прочие поля той же правки."""
    detail: dict[str, Any] = {"occurrence": advanced[0], "next": advanced[1]}
    names = [name for name in changes if name != "status"]
    old = {name: before[name] for name in names}
    new = {name: _shown(item, name) for name in names}
    if item.at is not None and _plain(item.due) != due:  # `due` ушёл следом за `at`
        old["due"], new["due"] = due, _plain(item.due)
    if old:
        detail.update(before=old, after=new)
    return detail


async def update(
    session: AsyncSession,
    *,
    client: str,
    owner_tz: str,
    day_start: str = "09:00",
    item_id: str,
    rev: int,
    changes: dict[str, Any],
    reason: str,
) -> Item:
    """Изменить поля элемента. Источник не нужен: смена статуса или срока знания не добавляет.

    Закрытие повторяющейся задачи не закрывает её, а переносит срок на следующее повторение.
    """
    item = await session.get(Item, item_id)
    if item is None:
        raise NotFound(f"item {item_id} does not exist")
    if rev != item.rev:
        raise Conflict(f"item changed: current rev is {item.rev}, read it again")
    why = checks.reason(reason)
    unknown = sorted(set(changes) - set(FIELDS))
    if unknown:
        raise Refused(f"unknown fields: {', '.join(unknown)}; known: {', '.join(FIELDS)}")
    now = utcnow()
    changes = _fold_in(changes, item, owner_tz, now)
    if not changes:
        raise Refused("nothing to change: name at least one field")

    if changes.get("page") is not None:
        # До правки полей: поиск сбрасывает правки в базу, а имя длиннее колонки она не примет.
        await pages.get(session, changes["page"])
    before = {name: _shown(item, name) for name in changes}
    prior, due = item.status, _plain(item.due)
    end_is_date = _apply(item, changes)
    closing = prior == "open" and item.status == "done" and item.kind == "task" and item.rrule is not None
    if closing and ("at" in changes or "due" in changes):
        raise Refused(
            "a repeating task moves to its next occurrence by itself when it is closed: "
            "change `at` or `due` in a separate call"
        )
    _check(item, owner_tz, end_is_date=end_is_date)

    closed_anchor = plan.current_anchor(item, owner_tz, day_start) if closing else None
    advanced = _advance(item, owner_tz, now) if closing else None
    if advanced is not None:
        item.status, item.done_at = "open", now
    elif "status" in changes:
        if item.status == "done":
            item.done_at = now
        elif not (prior == "open" and item.status == "open"):
            item.done_at = None
    item.rev += 1
    item.updated_at = now
    if advanced is None:
        after = {name: _shown(item, name) for name in changes}
        journal.record(
            session, client=client, op="item_update", target=item.id, reason=why,
            detail={"before": before, "after": after},
        )
    else:
        journal.record(
            session, client=client, op="item_done", target=item.id, reason=why,
            detail=_done_detail(item, advanced, changes, before, due),
        )
    await session.flush()
    if advanced is not None:
        await firings.skip_through(session, item.id, closed_anchor.astimezone(UTC))
    await firings.replan(session, item, owner_tz=owner_tz, day_start=day_start)
    return item


def _covers(start: datetime, span: timedelta, all_day: bool) -> list[date]:
    """Дни одного повторения, начавшегося в `start` и длящегося `span`.

    Целый день включает последний день. У события со временем конец ровно в полночь следующий день не занимает.
    """
    last_moment = start + span
    last = last_moment.date()
    if not all_day and span > timedelta(0) and last_moment.time() == time.min:
        last -= DAY
    return [start.date() + n * DAY for n in range((last - start.date()).days + 1)]


def days(item: Item, start: date, end: date, owner_tz: str) -> list[date]:
    """Дни окна `[start, end]`, на которые приходится элемент: срок, дни события и повторения.

    Событие с `end` занимает каждый день от начала до конца; у повторения та же длина.
    Повторяющаяся задача со сроком без времени — каждый ближайший день повтора.
    """
    found: set[date] = set()
    if item.due is not None and start <= item.due <= end:
        found.add(item.due)
    if item.at is not None:
        name = item.tz or owner_tz
        local_zone = occur.zone(name)
        span = item.end_at - item.at if item.end_at is not None else timedelta(0)
        low = datetime.combine(start, time.min, tzinfo=local_zone)
        high = datetime.combine(end + DAY, time.min, tzinfo=local_zone)
        # Повторение, начавшееся раньше окна, но дошедшее до него, тоже считается: начала ищем от `low - span`.
        for moment in occur.occurrences(item.at, item.rrule, name, low - span, high):
            covered = _covers(moment.replace(tzinfo=None), span, item.all_day)
            found.update(day for day in covered if start <= day <= end)
    elif item.due is not None and item.rrule is not None:
        found.update(occur.days(item.due, item.rrule, start, end))
    return sorted(found)


async def query(
    session: AsyncSession,
    *,
    owner_tz: str,
    kind: str | None = None,
    status: str | None = "open",
    list_: str | None = None,
    page: str | None = None,
    start: date | None = None,
    end: date | None = None,
) -> list[Item]:
    """Выборка элементов. Окно `start..end` (оба конца включены) оставляет то, что приходится на эти дни."""
    if (start is None) != (end is None):
        raise Refused("a window needs both ends: pass `from` and `to` together")
    # Оба конца входят в окно, поэтому дней в нём на один больше, чем разница дат.
    if start is not None and (end - start).days + 1 > MAX_WINDOW_DAYS:
        raise Refused(f"a window cannot be longer than {MAX_WINDOW_DAYS} days: narrow `from`..`to`")
    if kind is not None and kind not in KINDS:
        raise Refused(f"unknown kind {kind!r}; one of: {', '.join(KINDS)}")
    if status is not None and status not in STATUS_FILTERS:
        raise Refused(f"unknown status {status!r}; one of: {', '.join(STATUS_FILTERS)}")
    statement = select(Item).order_by(Item.created_at, Item.id)
    if kind is not None:
        statement = statement.where(Item.kind == kind)
    if status not in (None, "any"):
        statement = statement.where(Item.status == status)
    if list_ is not None:
        statement = statement.where(Item.list_ == list_)
    if page is not None:
        statement = statement.where(Item.page == page)
    rows = list((await session.scalars(statement)).all())
    if start is None:
        return rows
    return [item for item in rows if days(item, start, end, owner_tz)]


async def everything(session: AsyncSession) -> list[Item]:
    return list((await session.scalars(select(Item).order_by(Item.created_at, Item.id))).all())
