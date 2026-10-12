"""Страницы: проекция знания. Каждая запись — новая ревизия со ссылкой на факты."""

import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from almanac import checks
from almanac.clock import utcnow
from almanac.errors import Conflict, NotFound, Refused
from almanac.models import Item, Page, PageRevision, RevisionFact
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
REASON_MAX = 200  # длина колонки `reason`: причина, которую пишет сервер, в неё должна влезть


@dataclass(frozen=True)
class Written:
    path: str
    rev: int
    facts: list[str]
    warnings: list[str]


@dataclass(frozen=True)
class Moved:
    path: str
    rev: int
    relinked: list[str]


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


def _target(path: str) -> str:
    """Цель ссылки на страницу с этим путём: `pages/people/anna.md` -> `people/anna`."""
    return path.removeprefix("pages/").removesuffix(".md")


def retarget(body: str, old: str, new: str) -> str:
    """Тело, где ссылки на страницу `old` ведут на `new`; подпись после `|` остаётся как была."""
    old_target, new_target = _target(old), _target(new)

    def follow(found: re.Match[str]) -> str:
        text = found.group(0)
        return f"[[{new_target}{text[len(old_target) + 2:]}" if found.group(1) == old_target else text

    return LINK.sub(follow, body)


def _fits(path: str, body: str) -> None:
    if len(body) > MAX_BODY:
        raise Refused(
            f"{path} would be longer than {MAX_BODY} characters once its links follow the move; "
            "shorten it with `edit`, then move again"
        )


async def _free(session: AsyncSession, to: str) -> None:
    """Путь назначения свободен. Строка убранной страницы держит свои ревизии, на неё переезжать нельзя."""
    taken = await session.get(Page, to)
    if taken is None:
        return
    if taken.deleted_at is None:
        raise Conflict(f"{to} already exists: pick another slug, or merge the two pages by hand with `edit`")
    raise Refused(f"{to} was used by a removed page, its revisions stay under that path: pick another slug")


async def _followers(session: AsyncSession, path: str, to: str) -> list[tuple[Page, str]]:
    """Другие живые страницы, которые ссылаются на `path`, с телом, где ссылки уже ведут на `to`."""
    found = []
    for other in await live(session):
        if other.path == path:
            continue
        body = retarget(other.body, path, to)
        if body != other.body:
            _fits(other.path, body)
            found.append((other, body))
    return found


async def move(
    session: AsyncSession, *, client: str, types: Iterable[str], path: str, to: str, rev: int, reason: str
) -> Moved:
    """Переименовать страницу или сменить её тип. Ревизии, ссылки на неё и привязанные дела идут следом.

    Путь — ключ строки страницы, а на него смотрит внешний ключ ревизий: сначала появляется строка нового
    пути, потом ревизии переезжают на неё, и только после этого опустевшая старая строка уходит.
    """
    page = await get(session, path)
    _same_rev(page, rev)
    why = checks.reason(reason)
    checks.page_path(to, set(types))
    if to == path:
        raise Refused("`to` is the same as `path`: pass a new path, with another slug or another type")
    await _free(session, to)

    body = retarget(page.body, path, to)  # ссылки страницы на саму себя тоже переезжают
    _fits(to, body)
    followers = await _followers(session, path, to)
    now = utcnow()
    moved = Page(
        path=to, title=page.title, description=page.description, aliases=list(page.aliases), body=body,
        rev=page.rev + 1, created_at=page.created_at, updated_at=now,
    )
    session.add(moved)
    await session.flush()
    for table in (PageRevision, RevisionFact):
        await session.execute(
            update(table).where(table.path == path).values(path=to), execution_options={"synchronize_session": False}
        )
    await session.delete(page)
    await session.flush()
    await _snapshot(session, moved, client=client, reason=why, fact_ids=())

    for item in (await session.scalars(select(Item).where(Item.page == path))).all():
        item.page, item.updated_at, item.rev = to, now, item.rev + 1
    relinked = [other.path for other, _ in followers]
    journal.record(
        session, client=client, op="move", target=to, reason=why,
        detail={"from": path, "rev": moved.rev, "relinked": relinked},
    )
    follow = f"link follows move: {path} -> {to}"[:REASON_MAX]
    for other, text in followers:
        other.body, other.updated_at = text, now
        other.rev += 1
        await session.flush()
        await _snapshot(session, other, client=client, reason=follow, fact_ids=())
        journal.record(
            session, client=client, op="edit", target=other.path, reason=follow, detail={"rev": other.rev, "facts": []}
        )
    await session.flush()
    return Moved(to, moved.rev, relinked)
