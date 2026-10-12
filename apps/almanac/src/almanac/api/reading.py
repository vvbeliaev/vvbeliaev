from typing import Annotated

from fastapi import APIRouter, Query

from almanac import tree
from almanac.api.deps import Ctx, Db
from almanac.api.shapes import FileOut, GrepOut, GuideOut, LsOut

router = APIRouter()

DIRECTORY = "Directory or file of the tree, like `pages` or `pages/people/anna.md`. Empty is the top level."
FILE = "Path of the file, like `pages/people/anna.md` or `views/today.md`."


@router.get("/guide", operation_id="guide", summary="Rules and schema")
async def guide(ctx: Ctx) -> GuideOut:
    """Read this first in a session: what is stored here, how to save, the formats.
    `now` is the owner's current local time: item times (`at`, `due`) are written in it."""
    moment = tree.local_now(ctx.owner_tz)
    now = f"{moment:%Y-%m-%dT%H:%M}"
    return GuideOut(
        text=ctx.schema.guide, types=ctx.schema.types, now=now, tz=ctx.owner_tz, day_start=ctx.day_start,
        quiet=ctx.quiet_hours,
    )


@router.get("/tree", operation_id="ls", summary="List a directory of the tree")
async def ls(
    db: Db,
    ctx: Ctx,
    path: Annotated[str, Query(description=DIRECTORY)] = "",
    depth: Annotated[int, Query(description="Levels to show, 1 to 5.")] = 1,
) -> LsOut:
    """Top level: `guide.md`, `pages`, `facts`, `items`, `views`. Pages come with their
    description, so `ls("pages", depth=2)` is the catalog of everything known."""
    async with db.read() as session:
        return LsOut(entries=await tree.ls(session, ctx, path, depth))


@router.get("/grep", operation_id="grep", summary="Search the tree by regular expression")
async def grep(
    db: Db,
    ctx: Ctx,
    pattern: Annotated[str, Query(description="Regular expression, case-insensitive; at most 200 characters.")],
    path: Annotated[str, Query(description="Directory or file to search in. Empty searches everything.")] = "",
    context: Annotated[int, Query(description="Lines to add before and after each match, 0 to 5.")] = 0,
    limit: Annotated[int, Query(description="Most matches to return, 1 to 200.")] = 50,
) -> GrepOut:
    """Case-insensitive regular expression over pages, facts and items. `path` narrows the
    search to a directory or a file; `context` adds up to 5 lines around each match.
    `views/` and `guide.md` are searched only when `path` points at them."""
    async with db.read() as session:
        return GrepOut(matches=await tree.grep(session, ctx, pattern, path, context, limit))


@router.get("/file", operation_id="read", summary="Read a file of the tree")
async def read(
    db: Db,
    ctx: Ctx,
    path: Annotated[str, Query(description=FILE)],
    rev: Annotated[int | None, Query(description="Revision of a page to read; omit for the current one.")] = None,
) -> FileOut:
    """A page comes with its `rev` (pass it back when you write), its `backlinks` and the open
    `items` attached to it. `rev` in the request reads an old revision of a page. Everything
    outside `pages/` is a read-only projection."""
    async with db.read() as session:
        return FileOut.model_validate(await tree.read(session, ctx, path, rev))
