from fastapi import APIRouter
from pydantic import Field

from almanac.api.deps import Db, Strict, Who
from almanac.models import Fact
from almanac.store import facts as store

router = APIRouter()


class NoteIn(Strict):
    text: str = Field(description="What was said or found, verbatim.")
    origin: str = Field(
        default="said",
        description=(
            "`said` — the owner's words; `web` — text from the web; `file` — text from a document; "
            "`forward` — someone else's message the owner forwarded."
        ),
    )
    url: str | None = Field(default=None, description="Where third-party text came from.")
    supersedes: str | None = Field(default=None, description="Id of the fact this one corrects.")


class DismissIn(Strict):
    reason: str = Field(description="One line: why nothing needs to be built from this fact.")


def fact_out(fact: Fact) -> dict:
    return {
        "id": fact.id,
        "at": fact.at.isoformat(),
        "client": fact.client,
        "origin": fact.origin,
        "text": fact.text,
        "url": fact.url,
        "supersedes": fact.supersedes_id,
        "dismissed": fact.dismissed_at is not None,
    }


@router.post("/facts", operation_id="note", summary="Record a fact")
async def note(body: NoteIn, db: Db, who: Who) -> dict:
    """Append raw material: what was said or found. Facts are never edited — to correct one,
    record a new fact with `supersedes`. A fact stays in `views/inbox.md` until a page or
    an item is built from it, or it is dismissed."""
    async with db.write() as session:
        fact = await store.add(
            session, client=who.client, text=body.text, origin=body.origin, url=body.url, supersedes=body.supersedes
        )
    return fact_out(fact)


@router.post("/facts/{fact}/dismiss", operation_id="dismiss", summary="Close a fact that needs no projection")
async def dismiss(fact: str, body: DismissIn, db: Db, who: Who) -> dict:
    """Remove a fact from the inbox without building anything from it. The fact itself stays."""
    async with db.write() as session:
        closed = await store.dismiss(session, client=who.client, fact_id=fact, reason=body.reason)
    return fact_out(closed)
