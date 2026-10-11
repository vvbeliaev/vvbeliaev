from datetime import date, datetime
from typing import Annotated

from fastapi import APIRouter, Query
from pydantic import Field

from almanac.api.deps import Ctx, Db, Sourced, Strict, Who
from almanac.models import Item
from almanac.store import items as store

router = APIRouter()

LIST = "List slug, tasks only: `shopping`."
AT = "Local date and time without an offset: 2026-10-14T18:00."
TZ = "IANA zone of `at`, only when it is not the owner's."
RRULE = "RFC 5545 rule, events only: FREQ=YEARLY, FREQ=WEEKLY;BYDAY=MO."
REMIND = "ISO 8601 offsets before the moment: PT0M, PT1H, P1D."


class ItemAddIn(Sourced):
    kind: str = Field(description="`task` — something to do; `event` — something that happens at a time.")
    title: str
    note: str = ""
    list_: str | None = Field(default=None, alias="list", description=LIST)
    page: str | None = Field(default=None, description="Path of the page this item belongs to.")
    due: date | None = Field(default=None, description="Deadline, a date.")
    at: datetime | None = Field(default=None, description=AT)
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
    at: datetime | None = Field(default=None, description=AT)
    tz: str | None = Field(default=None, description=TZ)
    rrule: str | None = Field(default=None, description=RRULE)
    remind: list[str] | None = Field(default=None, description=REMIND)
    status: str | None = Field(default=None, description="`open`, `done` (tasks only) or `cancelled`.")


def item_out(item: Item) -> dict:
    return {
        "id": item.id,
        "kind": item.kind,
        "title": item.title,
        "note": item.note,
        "list": item.list_,
        "page": item.page,
        "due": item.due.isoformat() if item.due else None,
        "at": item.at.isoformat(timespec="minutes") if item.at else None,
        "tz": item.tz,
        "rrule": item.rrule,
        "remind": item.remind,
        "status": item.status,
        "done_at": item.done_at.isoformat() if item.done_at else None,
        "rev": item.rev,
    }


@router.post("/items", operation_id="item_add", summary="Create a task or an event")
async def item_add(body: ItemAddIn, db: Db, ctx: Ctx, who: Who) -> dict:
    """Anything with a date, a time or a checkbox. A purchase is a task with
    `list: "shopping"`. An event needs `at`. Needs a source: `said` or `facts`."""
    async with db.write() as session:
        item = await store.add(
            session, client=who.client, owner_tz=ctx.owner_tz, day_start=ctx.day_start, kind=body.kind,
            title=body.title, note=body.note, list_=body.list_, page=body.page, due=body.due, at=body.at,
            tz=body.tz, rrule=body.rrule, remind=body.remind, source=body.source(), reason=body.reason,
        )
    return item_out(item)


@router.patch("/items/{item}", operation_id="item_update", summary="Change an item or its status")
async def item_update(item: str, body: ItemUpdateIn, db: Db, ctx: Ctx, who: Who) -> dict:
    """Send only the fields that change, plus the item's current `rev`. Closing a task is
    `status: "done"`. A field sent as null is cleared."""
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
    kind: str | None = None,
    status: str = "open",
    list_: Annotated[str | None, Query(alias="list")] = None,
    page: str | None = None,
    start: Annotated[date | None, Query(alias="from", description="First day of the window.")] = None,
    end: Annotated[date | None, Query(alias="to", description="Last day of the window, inclusive.")] = None,
) -> list[dict]:
    """Open items by default; `status=any` lifts the filter. A window `from`..`to` keeps
    what falls on those days: deadlines and event moments, repeats included."""
    async with db.read() as session:
        rows = await store.query(
            session, owner_tz=ctx.owner_tz, kind=kind, status=status, list_=list_, page=page, start=start, end=end
        )
    return [item_out(row) for row in rows]
