"""Страницы: проекция знания. Каждая запись — новая ревизия со ссылкой на факты."""

import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from almanac import checks
from almanac.clock import utcnow
from almanac.errors import Conflict, NotFound, Refused
from almanac.models import Page, PageRevision, RevisionFact
from almanac.store import journal
from almanac.store.source import Source, resolve

MAX_BODY = 100_000
REV_MAX = 2**31 - 1  # номер ревизии лежит в int32; больший в запрос не отправить: ответом будет ошибка базы
# Подпись ограничена по длине и строке: без предела выражение на чужом теле квадратично.
LINK = re.compile(r"\[\[([a-z0-9-]+/[a-z0-9-]+)(?:\|[^\]\n]{0,120})?\]\]")
# Строка-флажок Markdown: `- [ ]`, `* [x]`, возможно с отступом. Задача в тексте страницы — это ошибка места:
# у задач есть элементы со сроком и напоминанием, а флажок в тексте никто не увидит и не напомнит о нём.
CHECKBOX = re.compile(r"^[ \t]*[-*+][ \t]+\[[ xX]\](?:[ \t]|$)", re.MULTILINE)
CHECKBOX_WARNING = "checkbox in a page: tasks are items — use item_add and set its page"


@dataclass(frozen=True)
class Written:
    path: str
    rev: int
    facts: list[str]
    warnings: list[str]


def links(body: str) -> list[str]:
    """Пути страниц, на которые ссылается текст: `[[people/anna]]` или `[[people/anna|Аня]]`."""
    return list(dict.fromkeys(f"pages/{target}.md" for target in LINK.findall(body)))


async def live(session: AsyncSession) -> list[Page]:
    statement = select(Page).where(Page.deleted_at.is_(None)).order_by(Page.path)
    return list((await session.scalars(statement)).all())


async def get(session: AsyncSession, path: str) -> Page:
    page = await session.get(Page, path)
    if page is None or page.deleted_at is not None:
        raise NotFound(f"{path} does not exist")
    return page


async def revision(session: AsyncSession, path: str, rev: int) -> PageRevision:
    row = await session.get(PageRevision, (path, rev)) if 0 < rev <= REV_MAX else None
    if row is None:
        raise NotFound(f"{path} has no rev {rev}")
    return row


async def history(session: AsyncSession, path: str) -> list[PageRevision]:
    statement = select(PageRevision).where(PageRevision.path == path).order_by(PageRevision.rev.desc())
    rows = list((await session.scalars(statement)).all())
    if not rows:
        raise NotFound(f"{path} does not exist")
    return rows


async def backlinks(session: AsyncSession, path: str) -> list[str]:
    return [page.path for page in await live(session) if page.path != path and path in links(page.body)]


def _same_rev(page: Page, rev: int | None) -> None:
    if rev is None:
        raise Conflict(f"{page.path} exists (rev {page.rev}): read it and pass its `rev`")
    if rev != page.rev:
        raise Conflict(f"page changed: current rev is {page.rev}, read it again")


async def _no_duplicate(session: AsyncSession, path: str, title: str, aliases: Sequence[str]) -> None:
    """Один субъект — одна страница: имя или алиас не должны совпасть с чужими."""
    mine = {checks.norm_name(name) for name in (title, *aliases)}
    for other in await live(session):
        if other.path == path:
            continue
        for kind, name in (("title", other.title), *(("alias", alias) for alias in other.aliases)):
            if checks.norm_name(name) in mine:
                raise Refused(f'{other.path} already has {kind} "{name}" — edit it')


async def _warnings(session: AsyncSession, body: str) -> list[str]:
    """Что не помешало записи, но модели стоит прочесть: битые ссылки и флажок (один раз на вызов)."""
    existing = {page.path for page in await live(session)}
    found = [f"broken link: {target}" for target in links(body) if target not in existing]
    return [*found, CHECKBOX_WARNING] if CHECKBOX.search(body) else found


async def _snapshot(
    session: AsyncSession, page: Page, *, client: str, reason: str, fact_ids: Iterable[str], deleted: bool = False
) -> None:
    """Ревизия текущего состояния. Страница к этому моменту уже в базе: у ревизии на неё внешний ключ."""
    session.add(
        PageRevision(
            path=page.path, rev=page.rev, title=page.title, description=page.description,
            aliases=list(page.aliases), body=page.body, deleted=deleted,
            at=page.updated_at, client=client, reason=reason,
        )
    )
    await session.flush()
    for fact_id in fact_ids:
        session.add(RevisionFact(path=page.path, rev=page.rev, fact_id=fact_id))
    await session.flush()


async def write(
    session: AsyncSession,
    *,
    client: str,
    types: Iterable[str],
    path: str,
    title: str,
    description: str,
    body: str,
    aliases: Sequence[str] = (),
    rev: int | None = None,
    source: Source,
    reason: str,
) -> Written:
    """Создать страницу или заменить её целиком. При замене `rev` обязателен."""
    checks.page_path(path, set(types))
    title = checks.one_line(title, name="title", limit=120)
    description = checks.one_line(description, name="description", limit=200)
    why = checks.reason(reason)
    names = [checks.one_line(alias, name="alias", limit=120) for alias in aliases]
    if len(body) > MAX_BODY:
        raise Refused(f"body is longer than {MAX_BODY} characters; split the page")
    checks.no_secret(title, description, body, *names)

    page = await session.get(Page, path)
    exists = page is not None and page.deleted_at is None
    if exists:
        _same_rev(page, rev)
    elif rev is not None:
        raise Refused(f"{path} does not exist: omit `rev` to create it")
    await _no_duplicate(session, path, title, names)
    fact_ids = await resolve(session, client=client, source=source, allow_restructure=exists)

    now = utcnow()
    if page is None:
        page = Page(
            path=path, title=title, description=description, aliases=names, body=body,
            rev=1, created_at=now, updated_at=now,
        )
        session.add(page)
    else:
        page.title, page.description, page.aliases, page.body = title, description, names, body
        page.rev += 1
        page.updated_at = now
        page.deleted_at = None
    await session.flush()
    await _snapshot(session, page, client=client, reason=why, fact_ids=fact_ids)
    journal.record(session, client=client, op="write", target=path, reason=why, detail={"rev": page.rev, "facts": fact_ids})
    await session.flush()
    return Written(path, page.rev, fact_ids, await _warnings(session, body))


async def edit(
    session: AsyncSession, *, client: str, path: str, old: str, new: str, rev: int, source: Source, reason: str
) -> Written:
    """Заменить один фрагмент тела. Фрагмент должен встречаться ровно один раз."""
    page = await get(session, path)
    _same_rev(page, rev)
    why = checks.reason(reason)
    checks.fragment(page.body, old)
    body = page.body.replace(old, new, 1)
    if len(body) > MAX_BODY:
        raise Refused(f"body is longer than {MAX_BODY} characters; split the page")
    checks.no_secret(new)
    fact_ids = await resolve(session, client=client, source=source, allow_restructure=True)

    page.body = body
    page.rev += 1
    page.updated_at = utcnow()
    await session.flush()
    await _snapshot(session, page, client=client, reason=why, fact_ids=fact_ids)
    journal.record(session, client=client, op="edit", target=path, reason=why, detail={"rev": page.rev, "facts": fact_ids})
    await session.flush()
    return Written(path, page.rev, fact_ids, await _warnings(session, body))


async def remove(session: AsyncSession, *, client: str, path: str, rev: int, reason: str) -> Written:
    """Убрать страницу. Строка и ревизии остаются; путь можно занять снова."""
    page = await get(session, path)
    _same_rev(page, rev)
    why = checks.reason(reason)
    now = utcnow()
    page.rev += 1
    page.updated_at = now
    page.deleted_at = now
    await session.flush()
    await _snapshot(session, page, client=client, reason=why, fact_ids=(), deleted=True)
    journal.record(session, client=client, op="remove", target=path, reason=why, detail={"rev": page.rev})
    await session.flush()
    return Written(path, page.rev, [], [])
