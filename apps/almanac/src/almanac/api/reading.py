from dataclasses import asdict

from fastapi import APIRouter

from almanac import tree
from almanac.api.deps import Ctx, Db

router = APIRouter()


@router.get("/guide", operation_id="guide", summary="Rules and schema")
async def guide(ctx: Ctx) -> dict:
    """Read this first in a session: what is stored here, how to save, the formats."""
    return {"text": ctx.schema.guide, "types": ctx.schema.types}


@router.get("/tree", operation_id="ls", summary="List a directory of the tree")
async def ls(db: Db, ctx: Ctx, path: str = "", depth: int = 1) -> list[dict]:
    """Top level: `guide.md`, `pages`, `facts`, `items`, `views`. Pages come with their
    description, so `ls("pages", depth=2)` is the catalog of everything known."""
    async with db.read() as session:
        return [asdict(entry) for entry in await tree.ls(session, ctx, path, depth)]


@router.get("/grep", operation_id="grep", summary="Search the tree by regular expression")
async def grep(db: Db, ctx: Ctx, pattern: str, path: str = "", context: int = 0, limit: int = 50) -> list[dict]:
    """Case-insensitive regular expression over pages, facts and items. `path` narrows the
    search to a directory or a file; `context` adds up to 5 lines around each match.
    `views/` and `guide.md` are searched only when `path` points at them."""
    async with db.read() as session:
        return [asdict(match) for match in await tree.grep(session, ctx, pattern, path, context, limit)]


@router.get("/file", operation_id="read", summary="Read a file of the tree")
async def read(db: Db, ctx: Ctx, path: str, rev: int | None = None) -> dict:
    """A page comes with its `rev` (pass it back when you write) and `backlinks`.
    `rev` in the request reads an old revision of a page. Everything outside `pages/`
    is a read-only projection."""
    async with db.read() as session:
        return asdict(await tree.read(session, ctx, path, rev))
