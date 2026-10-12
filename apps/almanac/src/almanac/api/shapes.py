"""Ответы ручек. Верх ответа — всегда объект с названными полями, никогда не список: так его
читает скрипт модели в Code Mode (`answer['entries']`), и так схема ответа попадает в `get_schema`.

Описания полей — подсказки для модели: английские, в одну строку, только там, где поле неочевидно.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from almanac.store.facts import ORIGINS
from almanac.store.items import ITEM_STATUSES, KINDS

# Закрытые наборы берутся из хранилища: одно место на значения, а схема инструмента их перечисляет.
Kind = Literal[*KINDS]
ItemStatus = Literal[*ITEM_STATUSES]
Origin = Literal[*ORIGINS]


class Shape(BaseModel):
    """Ответ ручки. Собирается из объектов ядра (`from_attributes`) и из словарей."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class GuideOut(Shape):
    text: str = Field(description="The guide in Markdown: what is stored, how to save, the formats.")
    types: dict[str, str] = Field(description="Page types: name -> what belongs on such a page.")
    now: str = Field(description="The owner's local time now, to the minute: 2026-10-12T15:21.")
    tz: str = Field(description="IANA name of the owner's zone, like Europe/Berlin.")


class EntryOut(Shape):
    path: str
    kind: Literal["dir", "file"]
    description: str | None = Field(description="One line about the entry; null when it has none.")


class LsOut(Shape):
    entries: list[EntryOut]


class MatchOut(Shape):
    path: str
    line: int = Field(description="Line number in the file, from 1.")
    text: str = Field(description="The matching line.")
    before: list[str] = Field(description="Lines before the match; empty unless `context` was passed.")
    after: list[str] = Field(description="Lines after the match; empty unless `context` was passed.")


class GrepOut(Shape):
    matches: list[MatchOut]


class FileOut(Shape):
    path: str
    text: str = Field(description="The file. A page starts with a header the server writes.")
    rev: int | None = Field(description="Revision of a page; null for the rest. Pass it back when you write.")
    backlinks: list[str] | None = Field(description="Pages that link here; null unless a current page is read.")
    writable: bool = Field(description="True only for the current revision of a page; the rest is read-only.")


class FactOut(Shape):
    id: str = Field(description="Pass it in `facts` of `write`, `edit` or `item_add`, or to `dismiss`.")
    at: str = Field(description="When it was recorded, UTC, ISO 8601.")
    client: str = Field(description="Who recorded it.")
    origin: Origin
    text: str
    url: str | None
    supersedes: str | None = Field(description="Id of the fact this one corrects.")
    dismissed: bool = Field(description="True when it was closed with `dismiss`.")


class WrittenOut(Shape):
    path: str
    rev: int = Field(description="The page's new revision: pass it to the next write, edit or remove.")
    facts: list[str] = Field(description="Ids of the facts this revision was built from.")
    warnings: list[str] = Field(description="Problems that did not stop the write: broken links, a checkbox.")


class RevisionOut(Shape):
    rev: int
    at: str = Field(description="When the revision was made, UTC, ISO 8601.")
    client: str
    reason: str
    deleted: bool = Field(description="True when this revision removed the page.")


class HistoryOut(Shape):
    revisions: list[RevisionOut] = Field(description="Newest first.")


class ItemOut(Shape):
    id: str = Field(description="Pass it as `item` to `item_update`.")
    kind: Kind
    title: str
    note: str
    list_: str | None = Field(alias="list", description="List slug, tasks only.")
    page: str | None = Field(description="Path of the page the item belongs to.")
    due: str | None = Field(description="Deadline: 2026-10-14.")
    at: str | None = Field(description="Local date and time without an offset: 2026-10-14T18:00.")
    tz: str | None = Field(description="IANA zone of `at` when it is not the owner's.")
    rrule: str | None
    remind: list[str]
    status: ItemStatus
    done_at: str | None = Field(description="When a task was closed, UTC, ISO 8601.")
    rev: int = Field(description="Changes with every update: pass the one you last saw to `item_update`.")


class ItemsOut(Shape):
    items: list[ItemOut]
