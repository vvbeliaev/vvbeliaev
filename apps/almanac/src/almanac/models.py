"""Таблицы ядра: факты, страницы с ревизиями, элементы, журнал."""

from datetime import UTC, date, datetime

from sqlalchemy import JSON, Boolean, Date, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.types import TypeDecorator


class UtcDateTime(TypeDecorator):
    """Момент в UTC. SQLite пояс не хранит: на входе нужно осведомлённое время, на выходе оно с UTC."""

    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if value.tzinfo is None:
            raise ValueError("naive datetime: pass an aware one")
        return value.astimezone(UTC).replace(tzinfo=None)

    def process_result_value(self, value, dialect):
        return None if value is None else value.replace(tzinfo=UTC)


class Base(DeclarativeBase):
    pass


class Fact(Base):
    """Сырьё. Строка не правится: меняются только поля закрытия."""

    __tablename__ = "facts"

    id: Mapped[str] = mapped_column(String(16), primary_key=True)
    at: Mapped[datetime] = mapped_column(UtcDateTime)
    client: Mapped[str] = mapped_column(String(100))
    origin: Mapped[str] = mapped_column(String(8))
    text: Mapped[str] = mapped_column(Text)
    url: Mapped[str | None] = mapped_column(String(2000))
    supersedes_id: Mapped[str | None] = mapped_column(ForeignKey("facts.id"))
    dismissed_at: Mapped[datetime | None] = mapped_column(UtcDateTime)
    dismiss_reason: Mapped[str | None] = mapped_column(String(200))


class Page(Base):
    """Текущее состояние страницы. История — в `PageRevision`."""

    __tablename__ = "pages"

    path: Mapped[str] = mapped_column(String(120), primary_key=True)
    title: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(String(200))
    aliases: Mapped[list[str]] = mapped_column(JSON)
    body: Mapped[str] = mapped_column(Text)
    rev: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime)
    updated_at: Mapped[datetime] = mapped_column(UtcDateTime)
    deleted_at: Mapped[datetime | None] = mapped_column(UtcDateTime)


class PageRevision(Base):
    """Полная копия страницы на каждый `rev`."""

    __tablename__ = "page_revisions"

    path: Mapped[str] = mapped_column(ForeignKey("pages.path"), primary_key=True)
    rev: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(String(200))
    aliases: Mapped[list[str]] = mapped_column(JSON)
    body: Mapped[str] = mapped_column(Text)
    deleted: Mapped[bool] = mapped_column(Boolean, default=False)
    at: Mapped[datetime] = mapped_column(UtcDateTime)
    client: Mapped[str] = mapped_column(String(100))
    reason: Mapped[str] = mapped_column(String(200))


class RevisionFact(Base):
    __tablename__ = "revision_facts"

    path: Mapped[str] = mapped_column(String(120), primary_key=True)
    rev: Mapped[int] = mapped_column(Integer, primary_key=True)
    fact_id: Mapped[str] = mapped_column(ForeignKey("facts.id"), primary_key=True)


class Item(Base):
    """Задача или событие. `at` — местное время без пояса, пояс лежит в `tz`."""

    __tablename__ = "items"

    id: Mapped[str] = mapped_column(String(16), primary_key=True)
    kind: Mapped[str] = mapped_column(String(8))
    title: Mapped[str] = mapped_column(String(200))
    note: Mapped[str] = mapped_column(Text, default="")
    # `list` — имя встроенного типа: в Python поле зовётся `list_`, в базе и в API — `list`.
    list_: Mapped[str | None] = mapped_column("list", String(60))
    page: Mapped[str | None] = mapped_column(String(120))
    due: Mapped[date | None] = mapped_column(Date)
    at: Mapped[datetime | None] = mapped_column(DateTime)
    tz: Mapped[str | None] = mapped_column(String(60))
    rrule: Mapped[str | None] = mapped_column(String(300))
    remind: Mapped[list[str]] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(10))
    done_at: Mapped[datetime | None] = mapped_column(UtcDateTime)
    rev: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime)
    updated_at: Mapped[datetime] = mapped_column(UtcDateTime)


class ItemFact(Base):
    __tablename__ = "item_facts"

    item_id: Mapped[str] = mapped_column(ForeignKey("items.id"), primary_key=True)
    fact_id: Mapped[str] = mapped_column(ForeignKey("facts.id"), primary_key=True)


class Journal(Base):
    """Журнал записей. Пишет сервер, в той же транзакции, что и изменение."""

    __tablename__ = "journal"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    at: Mapped[datetime] = mapped_column(UtcDateTime)
    client: Mapped[str] = mapped_column(String(100))
    op: Mapped[str] = mapped_column(String(20))
    target: Mapped[str] = mapped_column(String(120))
    reason: Mapped[str] = mapped_column(String(200))
    detail: Mapped[dict] = mapped_column(JSON)


class Session(Base):
    """Сессия владельца: в базе хэш токена, сам токен — только в cookie."""

    __tablename__ = "sessions"

    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime)
    expires_at: Mapped[datetime] = mapped_column(UtcDateTime)


class OAuthClient(Base):
    __tablename__ = "oauth_clients"

    client_id: Mapped[str] = mapped_column(String(200), primary_key=True)
    info: Mapped[dict] = mapped_column(JSON)


class AuthPending(Base):
    """Отложенный шаг согласия: живёт, пока владелец не ответил."""

    __tablename__ = "auth_pending"

    state_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    kind: Mapped[str] = mapped_column(String(20))
    expires_at: Mapped[datetime] = mapped_column(UtcDateTime)
    data: Mapped[dict] = mapped_column(JSON)


class OAuthCode(Base):
    __tablename__ = "oauth_codes"

    code_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    client_id: Mapped[str] = mapped_column(String(200))
    expires_at: Mapped[datetime] = mapped_column(UtcDateTime)
    data: Mapped[dict] = mapped_column(JSON)


class OAuthToken(Base):
    """Токен доступа или обновления. Пара живёт и умирает вместе (`pair_id`)."""

    __tablename__ = "oauth_tokens"

    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    kind: Mapped[str] = mapped_column(String(10))
    pair_id: Mapped[str] = mapped_column(String(64))
    client_id: Mapped[str] = mapped_column(String(200))
    scopes: Mapped[list[str]] = mapped_column(JSON)
    resource: Mapped[str | None] = mapped_column(String(500))
    expires_at: Mapped[datetime] = mapped_column(UtcDateTime)
