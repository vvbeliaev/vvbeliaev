import re
from datetime import date, datetime
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Path, Query
from pydantic import BeforeValidator, Field, TypeAdapter, ValidationError

from almanac.api.deps import Ctx, Db, Sourced, Strict, Who
from almanac.api.shapes import ItemOut, ItemsOut, ItemStatus, Kind
from almanac.models import Item
from almanac.store import items as store

router = APIRouter()

LIST = "List slug, tasks only: `shopping` for purchases, or any slug of your own, like `reading`."
AT = "`2026-10-14T18:00` is a moment (local, no offset); `2026-10-14` alone is a whole day."
ENDS = "When it ends, same form as `at`; for whole days the last day, inclusive. Events only."
IN = (
    "Instead of `at`: this far from now, ISO 8601: PT20M, P2D. The server computes the moment. "
    "Like `at`, it only sets the moment: a reminder needs `remind`."
)
TZ = "IANA zone of `at`, only when it is not the owner's."
RRULE = "RFC 5545 rule: FREQ=YEARLY, FREQ=WEEKLY;BYDAY=MO. On a task: needs `due` or `at`, UNTIL not COUNT."
REMIND = (
    "When to notify the owner: ISO 8601 offsets before the moment: PT0M (at the moment), PT1H, P1D. "
    "Empty: nothing is sent."
)
ITEM = "Id of the item, like i_ab12cd34."
START = "First day of the window: 2026-10-12."
END = "Last day of the window, inclusive: 2026-10-18."
# Фильтр статуса шире статуса элемента: `any` снимает отбор.
StatusFilter = Literal[*store.STATUS_FILTERS]

DATE_ONLY = re.compile(r"\d{4}-\d{2}-\d{2}")
MOMENT = TypeAdapter(datetime)


def _day_or_moment(value: Any) -> Any:
    """Форму `at` и `end` различает текст: `2026-10-14` — день, `2026-10-14T00:00` — момент в полночь.

    Сам pydantic из объединения `date | datetime` для строки берёт первое, что разобралось, и полночь стала бы днём.
    Что не разобралось здесь, уходит дальше как есть: отказ напишет pydantic.
    """
    if isinstance(value, (date, datetime)):
        return value
    if not isinstance(value, str):
        # ValueError, а не TypeError: из проверки поля pydantic превращает в отказ 422 только первый.
        raise ValueError("pass a date like 2026-10-14 or a local date and time like 2026-10-14T18:00")  # noqa: TRY004
    text = value.strip()
    try:
        return date.fromisoformat(text) if DATE_ONLY.fullmatch(text) else MOMENT.validate_python(text)
    except (ValueError, ValidationError):
        return value


# День (целый день) или момент (местные дата и время); в схеме инструмента — `date | date-time`.
When = Annotated[date | datetime, BeforeValidator(_day_or_moment)]


class ItemAddIn(Sourced):
    kind: Kind = Field(
        description=(
            "`task` — something the owner does, with or without a time: it is ticked off when done. "
            "`event` — something that happens whether or not the owner acts: a meeting, a flight."
        )
    )
    title: str
    note: str = ""
    list_: str | None = Field(default=None, alias="list", description=LIST)
    page: str | None = Field(default=None, description="Path of the page this item belongs to.")
    due: date | None = Field(default=None, description="Deadline, a date.")
    at: When | None = Field(default=None, description=AT)
    end: When | None = Field(default=None, description=ENDS)
    in_: str | None = Field(default=None, alias="in", description=IN)
    tz: str | None = Field(default=None, description=TZ)
    rrule: str | None = Field(default=None, description=RRULE)
    remind: list[str] = Field(default_factory=list, description=REMIND)


class ItemUpdateIn(Strict):
    rev: int = Field(description="The `rev` you last saw on this item.")
    reason: str = Field(description="One line for the journal: why this change.")
    title: str | None = None
    note: str | None = None
    list_: str | None = Field(default=None, alias="list", description=LIST)
    page: str | None = None
    due: date | None = None
    at: When | None = Field(default=None, description=AT)
    end: When | None = Field(default=None, description=ENDS)
    in_: str | None = Field(default=None, alias="in", description=IN)
    tz: str | None = Field(default=None, description=TZ)
    rrule: str | None = Field(default=None, description=RRULE)
    remind: list[str] | None = Field(default=None, description=REMIND)
    status: ItemStatus | None = Field(default=None, description="`open`, `done` (tasks only) or `cancelled`.")


def item_out(item: Item) -> ItemOut:
    return ItemOut(
        id=item.id,
        kind=item.kind,
        title=item.title,
        note=item.note,
        list_=item.list_,
        page=item.page,
        due=item.due.isoformat() if item.due else None,
        at=store.moment_text(item.at, item.all_day),
        end=store.moment_text(item.end_at, item.all_day),
        tz=item.tz,
        rrule=item.rrule,
        remind=item.remind,
        status=item.status,
        done_at=item.done_at.isoformat() if item.done_at else None,
        rev=item.rev,
    )


@router.post("/items", operation_id="item_add", summary="Create a task or an event")
async def item_add(body: ItemAddIn, db: Db, ctx: Ctx, who: Who) -> ItemOut:
    """Anything with a date, a time or a checkbox. A purchase is a task with
    `list: "shopping"`; any other slug is a list of its own. An event needs `at` or `in`;
    a date alone makes it whole-day; `end` gives it a length. `rrule` repeats an event,
    or makes a task a habit. Needs a source: `said` or `facts`."""
    async with db.write() as session:
        item = await store.add(
            session, client=who.client, owner_tz=ctx.owner_tz, day_start=ctx.day_start, kind=body.kind,
            title=body.title, note=body.note, list_=body.list_, page=body.page, due=body.due, at=body.at,
            end=body.end, in_=body.in_, tz=body.tz, rrule=body.rrule, remind=body.remind, source=body.source(),
            reason=body.reason,
        )
    return item_out(item)


@router.patch("/items/{item}", operation_id="item_update", summary="Change an item or its status")
async def item_update(
    item: Annotated[str, Path(description=ITEM)], body: ItemUpdateIn, db: Db, ctx: Ctx, who: Who
) -> ItemOut:
    """Send only the fields that change, plus the current `rev`. `status: "done"` closes a
    task; a repeating task then moves to its next occurrence and stays open, and `cancelled`
    ends the series. A field sent as null is cleared."""
    changes = body.model_dump(exclude_unset=True, by_alias=True, exclude={"rev", "reason"})
    async with db.write() as session:
        changed = await store.update(
            session, client=who.client, owner_tz=ctx.owner_tz, day_start=ctx.day_start, item_id=item, rev=body.rev,
            changes=changes, reason=body.reason,
        )
    return item_out(changed)


@router.get("/items", operation_id="items", summary="Query tasks and events")
async def items(
    db: Db,
    ctx: Ctx,
    kind: Annotated[Kind | None, Query(description="Only tasks or only events; omit for both.")] = None,
    status: Annotated[StatusFilter, Query(description="`any` lifts the filter.")] = "open",
    list_: Annotated[str | None, Query(alias="list", description="Only tasks of this list slug.")] = None,
    page: Annotated[str | None, Query(description="Only items of this page path.")] = None,
    start: Annotated[date | None, Query(alias="from", description=START)] = None,
    end: Annotated[date | None, Query(alias="to", description=END)] = None,
) -> ItemsOut:
    """Open items by default; `status=any` lifts the filter. A window `from`..`to` keeps
    what falls on those days: deadlines and event moments, repeats included."""
    async with db.read() as session:
        rows = await store.query(
            session, owner_tz=ctx.owner_tz, kind=kind, status=status, list_=list_, page=page, start=start, end=end
        )
    return ItemsOut(items=[item_out(row) for row in rows])
