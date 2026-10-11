"""Правило источника: проекция называет факты, из которых собрана."""

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from almanac.errors import Refused
from almanac.store import facts

NEED = (
    "name the source: pass `facts` (ids of facts already recorded) or `said` "
    "(the owner's words, verbatim — a fact is recorded for you)"
)


@dataclass(frozen=True)
class Source:
    facts: tuple[str, ...] = ()
    said: str | None = None
    restructure: bool = False


async def resolve(session: AsyncSession, *, client: str, source: Source, allow_restructure: bool) -> list[str]:
    """Id фактов-источников. `said` становится новым фактом в этой же транзакции.

    Пустой список возможен только при `restructure`, и только там, где он разрешён:
    создание проекции без источника не бывает.
    """
    ids = await facts.require(session, source.facts)
    if source.said and source.said.strip():
        ids.append((await facts.add(session, client=client, text=source.said)).id)
    if ids:
        return ids
    if source.restructure and allow_restructure:
        return []
    hint = "; for a change that adds no new knowledge pass `restructure: true`" if allow_restructure else ""
    raise Refused(NEED + hint)
