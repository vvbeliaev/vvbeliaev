"""Элементы: задачи и события — всё, что запрашивается или срабатывает."""

from collections.abc import Sequence
from datetime import date, datetime, time, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from almanac import checks
from almanac.clock import utcnow
from almanac.errors import Conflict, NotFound, Refused
from almanac.ids import new_id
from almanac.models import Item, ItemFact
from almanac.store import journal, pages
from almanac.store.source import Source, resolve
from almanac.timeline import occur

KINDS = ("task", "event")
STATUSES = {"task": ("open", "done", "cancelled"), "event": ("open", "cancelled")}
FIELDS = ("title", "note", "list", "page", "due", "at", "tz", "rrule", "remind", "status")
NOT_NULL = ("title", "status")


def _check(item: Item, owner_tz: str) -> None:
    """Поля элемента согласованы между собой. Отказ называет поле, которое не сходится."""
    if item.kind not in KINDS:
        raise Refused(f"unknown kind {item.kind!r}; one of: {', '.join(KINDS)}")
    item.title = checks.one_line(item.title, name="title", limit=200)
    checks.no_secret(item.title, item.note)
    if item.kind == "event" and item.at is None:
        raise Refused("an event needs `at`: local date and time like 2026-10-14T18:00")
    if item.rrule is not None and item.kind != "event":
        raise Refused("`rrule` is for events only; repeating tasks are not supported")
    if item.list_ is not None:
        if item.kind != "task":
            raise Refused("`list` is for tasks only")
        if not checks.LIST_SLUG.match(item.list_):
            raise Refused(f"bad list {item.list_!r}: lowercase a-z, 0-9 and single dashes, like shopping")
    if item.at is not None and item.at.tzinfo is not None:
        raise Refused("`at` is local time without an offset; put the zone name in `tz`")
    occur.zone(item.tz or owner_tz)
    if item.rrule is not None:
        occur.rule(item.rrule, item.at)
    if item.remind:
        if item.at is None and item.due is None:
            raise Refused("`remind` needs `at` or `due` to count from")
        for value in item.remind:
            checks.duration(value)
    if item.status not in STATUSES[item.kind]:
        raise Refused(
            f"unknown status {item.status!r} for a {item.kind}; one of: {', '.join(STATUSES[item.kind])}"
        )


async def add(
    session: AsyncSession,
    *,
    client: str,
    owner_tz: str,
    kind: str,
    title: str,
    note: str = "",
    list_: str | None = None,
    page: str | None = None,
    due: date | None = None,
    at: datetime | None = None,
    tz: str | None = None,
    rrule: str | None = None,
    remind: Sequence[str] = (),
    source: Source,
    reason: str,
) -> Item:
    why = checks.one_line(reason, name="reason", limit=200)
    now = utcnow()
    item = Item(
        id=new_id("i"), kind=kind, title=title, note=(note or "").strip(), list_=list_, page=page,
        due=due, at=at, tz=tz, rrule=rrule, remind=list(remind or ()),
        status="open", done_at=None, rev=1, created_at=now, updated_at=now,
    )
    _check(item, owner_tz)
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
    return item


async def update(
    session: AsyncSession, *, client: str, owner_tz: str, item_id: str, rev: int, changes: dict[str, Any], reason: str
) -> Item:
    """Изменить поля элемента. Источник не нужен: смена статуса или срока знания не добавляет."""
    item = await session.get(Item, item_id)
    if item is None:
        raise NotFound(f"item {item_id} does not exist")
    if rev != item.rev:
        raise Conflict(f"item changed: current rev is {item.rev}, read it again")
    why = checks.one_line(reason, name="reason", limit=200)
    unknown = sorted(set(changes) - set(FIELDS))
    if unknown:
        raise Refused(f"unknown fields: {', '.join(unknown)}; known: {', '.join(FIELDS)}")
    if not changes:
        raise Refused("nothing to change: name at least one field")

    for name, value in changes.items():
        if value is None and name in NOT_NULL:
            raise Refused(f"{name} cannot be null")
        if name == "note":
            value = (value or "").strip()
        if name == "remind":
            value = list(value or ())
        setattr(item, "list_" if name == "list" else name, value)
    _check(item, owner_tz)
    if changes.get("page") is not None:
        await pages.get(session, item.page)
    if "status" in changes:
        item.done_at = utcnow() if item.status == "done" else None
    item.rev += 1
    item.updated_at = utcnow()
    journal.record(
        session, client=client, op="item_update", target=item.id, reason=why, detail={"fields": sorted(changes)}
    )
    await session.flush()
    return item


def days(item: Item, start: date, end: date, owner_tz: str) -> list[date]:
    """Дни окна `[start, end]`, на которые приходится элемент: его срок и моменты события."""
    found: set[date] = set()
    if item.due is not None and start <= item.due <= end:
        found.add(item.due)
    if item.at is not None:
        name = item.tz or owner_tz
        local_zone = occur.zone(name)
        low = datetime.combine(start, time.min, tzinfo=local_zone)
        high = datetime.combine(end + timedelta(days=1), time.min, tzinfo=local_zone)
        found.update(moment.date() for moment in occur.occurrences(item.at, item.rrule, name, low, high))
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
