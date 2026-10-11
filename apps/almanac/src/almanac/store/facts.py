"""Факты: сырьё, которое только дописывается."""

from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from almanac import checks
from almanac.clock import utcnow
from almanac.errors import NotFound, Refused
from almanac.ids import new_id
from almanac.models import Fact, ItemFact, RevisionFact
from almanac.store import journal

ORIGINS = ("said", "web", "file", "forward")
MAX_TEXT = 200_000


async def add(
    session: AsyncSession,
    *,
    client: str,
    text: str,
    origin: str = "said",
    url: str | None = None,
    supersedes: str | None = None,
) -> Fact:
    # Сюда приходят и слова модели через API, и сообщения владельца из Telegram: бот до API не доходит.
    checks.no_nul(text, url, supersedes)
    body = (text or "").strip()
    if not body:
        raise Refused("fact text is empty")
    if len(body) > MAX_TEXT:
        raise Refused(f"fact text is longer than {MAX_TEXT} characters")
    if origin not in ORIGINS:
        raise Refused(f"unknown origin {origin!r}; one of: {', '.join(ORIGINS)}")
    if url is not None:
        checks.web_url(url)
    checks.no_secret(body, url)
    if supersedes is not None and await session.get(Fact, supersedes) is None:
        raise Refused(f"the fact to replace, {supersedes}, does not exist")
    fact = Fact(
        id=new_id("f"), at=utcnow(), client=client, origin=origin, text=body, url=url, supersedes_id=supersedes
    )
    session.add(fact)
    journal.record(session, client=client, op="note", target=fact.id, reason="fact recorded", detail={"origin": origin})
    await session.flush()
    return fact


async def dismiss(session: AsyncSession, *, client: str, fact_id: str, reason: str) -> Fact:
    """Факту проекция не нужна: он уходит из inbox, но остаётся в ленте дня."""
    fact = await session.get(Fact, fact_id)
    if fact is None:
        raise NotFound(f"fact {fact_id} does not exist")
    why = checks.reason(reason)
    fact.dismissed_at = utcnow()
    fact.dismiss_reason = why
    journal.record(session, client=client, op="dismiss", target=fact.id, reason=why)
    await session.flush()
    return fact


async def require(session: AsyncSession, ids: Sequence[str]) -> list[str]:
    """Те же id без повторов, если все факты существуют; иначе отказ с перечнем неизвестных."""
    unique = list(dict.fromkeys(ids))
    if not unique:
        return []
    found = set((await session.scalars(select(Fact.id).where(Fact.id.in_(unique)))).all())
    missing = [fact_id for fact_id in unique if fact_id not in found]
    if missing:
        raise Refused(f"unknown facts: {', '.join(missing)}")
    return unique


async def inbox(session: AsyncSession) -> list[Fact]:
    """Факты, из которых ничего не собрано: не процитированы, не заменены и не закрыты."""
    newer = aliased(Fact)
    statement = (
        select(Fact)
        .where(
            Fact.dismissed_at.is_(None),
            Fact.id.not_in(select(RevisionFact.fact_id)),
            Fact.id.not_in(select(ItemFact.fact_id)),
            Fact.id.not_in(select(newer.supersedes_id).where(newer.supersedes_id.is_not(None))),
        )
        .order_by(Fact.at, Fact.id)
    )
    return list((await session.scalars(statement)).all())


async def everything(session: AsyncSession) -> list[Fact]:
    return list((await session.scalars(select(Fact).order_by(Fact.at, Fact.id))).all())
