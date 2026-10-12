from typing import Annotated

from fastapi import APIRouter, Query
from pydantic import Field

from almanac.api.deps import Ctx, Db, Sourced, Strict, Who
from almanac.api.shapes import HistoryOut, MovedOut, RevisionOut, WrittenOut
from almanac.store import pages as store

router = APIRouter()


class WriteIn(Sourced):
    path: str = Field(description="pages/<type>/<slug>.md")
    title: str = Field(description="The subject's name as the owner writes it.")
    description: str = Field(description="One line: what this page is about. Shown in the catalog.")
    body: str = Field(description="Markdown body, without frontmatter.")
    aliases: list[str] = Field(default_factory=list, description="Other names of the subject.")
    rev: int | None = Field(default=None, description="Omit to create; pass the `rev` you read to replace.")
    restructure: bool = Field(default=False, description="True when the change adds no new knowledge.")


class EditIn(Sourced):
    path: str
    old: str = Field(description="Fragment of the body to replace; must occur exactly once.")
    new: str
    rev: int = Field(description="The `rev` from your last read of this page.")
    restructure: bool = Field(default=False, description="True when the change adds no new knowledge.")


class MoveIn(Strict):
    path: str = Field(description="Path of the page to move, like `pages/ideas/garden.md`.")
    to: str = Field(
        description="New path, `pages/<type>/<slug>.md`: a new slug renames the page, "
        "another type moves it there, like `pages/projects/garden.md`. Must be free."
    )
    rev: int = Field(description="The `rev` from your last read of this page.")
    reason: str = Field(description="One line for the journal: why this change.")


class RemoveIn(Strict):
    path: str
    rev: int
    reason: str


@router.put("/pages", operation_id="write", summary="Create a page or replace it whole")
async def write(body: WriteIn, db: Db, ctx: Ctx, who: Who) -> WrittenOut:
    """One subject — one page: grep for the name first. Creating needs a source (`said` or
    `facts`). Replacing needs the current `rev`; prefer `edit` for a small change.
    The answer lists broken links and checkboxes as `warnings`."""
    async with db.write() as session:
        done = await store.write(
            session, client=who.client, types=ctx.schema.types, path=body.path, title=body.title,
            description=body.description, body=body.body, aliases=body.aliases, rev=body.rev,
            source=body.source(), reason=body.reason,
        )
    return WrittenOut.model_validate(done)


@router.post("/pages/edit", operation_id="edit", summary="Replace one fragment of a page body")
async def edit(body: EditIn, db: Db, who: Who) -> WrittenOut:
    """`old` must occur exactly once in the body — widen it until it does. Needs the current
    `rev` and a source, or `restructure: true` when no new knowledge is added."""
    async with db.write() as session:
        done = await store.edit(
            session, client=who.client, path=body.path, old=body.old, new=body.new, rev=body.rev,
            source=body.source(), reason=body.reason,
        )
    return WrittenOut.model_validate(done)


@router.post("/pages/move", operation_id="move", summary="Move or rename a page")
async def move(body: MoveIn, db: Db, ctx: Ctx, who: Who) -> MovedOut:
    """Moves the page with its history; links from other pages and items attached to it
    follow. Use it to rename, or when an idea becomes a project. Needs the current `rev`."""
    async with db.write() as session:
        done = await store.move(
            session, client=who.client, types=ctx.schema.types, path=body.path, to=body.to, rev=body.rev,
            reason=body.reason,
        )
    return MovedOut.model_validate(done)


@router.post("/pages/remove", operation_id="remove", summary="Remove a page")
async def remove(body: RemoveIn, db: Db, who: Who) -> WrittenOut:
    """The page disappears from the tree; its revisions stay and can be read by `rev`."""
    async with db.write() as session:
        done = await store.remove(session, client=who.client, path=body.path, rev=body.rev, reason=body.reason)
    return WrittenOut.model_validate(done)


@router.get("/pages/history", operation_id="history", summary="Revisions of a page")
async def history(
    path: Annotated[str, Query(description="Path of the page, like `pages/people/anna.md`.")], db: Db
) -> HistoryOut:
    """Newest first: who changed the page, when and why. Read an old one with `read(path, rev)`."""
    async with db.read() as session:
        rows = await store.history(session, path)
    return HistoryOut(
        revisions=[
            RevisionOut(rev=row.rev, at=row.at.isoformat(), client=row.client, reason=row.reason, deleted=row.deleted)
            for row in rows
        ]
    )
