"""Цикл напоминаний и приём из Telegram. Живёт в процессе сервера.

Доставка at-least-once: отметка «отправлено» ставится после успешной отправки.
Пропущенное напоминание хуже дубля: сбой отправки не отменяет срабатывание, а цепочка
повторов не рвётся — ни после пропуска, ни после простоя.
"""

import asyncio
import logging
from datetime import UTC, datetime, timedelta
from typing import Protocol

from almanac.clock import utcnow
from almanac.db import Database
from almanac.errors import Refused
from almanac.ids import new_id
from almanac.models import Firing, Item
from almanac.store import facts, firings, items, journal
from almanac.timeline import occur, plan

log = logging.getLogger(__name__)

LATE_AFTER = timedelta(minutes=5)
STALE_AFTER = timedelta(hours=24)
ALERT_AFTER = 10  # неудачных отправок подряд: в журнал идёт одна запись, а попытки продолжаются
RETRY_PAUSE = 5  # секунд до новой попытки опроса после сбоя
BUTTONS = (("Готово", "done"), ("+1 час", "hour"), ("Завтра", "tomorrow"))
# Признаки пересланного сообщения: новый `forward_origin` и старые поля Bot API.
FORWARD_KEYS = ("forward_origin", "forward_date", "forward_from", "forward_from_chat")


class Messenger(Protocol):
    async def send(self, text: str, buttons: list[tuple[str, str]] | None = None) -> int: ...
    async def answer(self, callback_id: str, text: str = "") -> None: ...
    async def clear_buttons(self, message_id: int) -> None: ...
    async def updates(self, offset: int | None = None, timeout: int = 25) -> list[dict]: ...


class Scheduler:
    def __init__(
        self, db: Database, messenger: Messenger, *, owner_tz: str, day_start: str, owner_chat_id: int
    ) -> None:
        self.db = db
        self.messenger = messenger
        self.owner_tz = owner_tz
        self.day_start = day_start
        self.owner_chat_id = owner_chat_id

    # --- отправка ---

    async def tick(self) -> int:
        """Починить план, затем отправить всё созревшее. Возвращает число отправленных."""
        now = utcnow()
        await self._heal(now)
        async with self.db.read() as session:
            ready = [firing.id for firing in await firings.due(session, now)]
        sent = 0
        for firing_id in ready:
            try:
                sent += await self._fire(firing_id, now)
            except Exception:
                log.exception("reminder %s failed", firing_id)
        return sent

    async def _heal(self, now: datetime) -> None:
        """Вернуть план элементам, у которых цепочка напоминаний оборвалась.

        Обычно искать нечего: запрос отбирает только открытые элементы с напоминаниями и без
        ожидающего срабатывания, а замок записи берётся, лишь когда по плану что-то есть.
        """
        try:
            async with self.db.read() as session:
                lost = await firings.unplanned(session, owner_tz=self.owner_tz, day_start=self.day_start, now=now)
            if not lost:
                return
            async with self.db.write() as session:
                for item_id in lost:
                    item = await session.get(Item, item_id)
                    if item is not None:
                        await firings.replan(session, item, owner_tz=self.owner_tz, day_start=self.day_start)
        except Exception:
            log.exception("reminder plan repair failed")

    async def _fire(self, firing_id: str, now: datetime) -> int:
        async with self.db.read() as session:
            firing = await session.get(Firing, firing_id)
            item = await session.get(Item, firing.item_id) if firing is not None else None
        if firing is None or firing.state != "pending":
            return 0  # срабатывание убрали или обработали, пока цикл шёл по списку
        stale = not firing.manual and now - firing.occurrence > STALE_AFTER
        if item is None or item.status != "open" or stale:
            await self._settle(firing_id, "skipped")
            return 0
        buttons = [(label, f"{action}:{firing.id}") for label, action in BUTTONS]
        try:
            message_id = await self.messenger.send(self._text(item, firing, now), buttons)
        except Exception as error:  # noqa: BLE001 — сеть или сам Telegram: попробуем на следующем тике
            log.warning("reminder %s not sent: %s", firing_id, error)
            await self._failed(firing_id, str(error))
            return 0
        async with self.db.write() as session:
            row = await session.get(Firing, firing_id)
            if row is not None and row.state == "pending":
                row.state, row.sent_at, row.message_id = "sent", utcnow(), message_id
                current = await session.get(Item, row.item_id)
                await firings.replan(session, current, owner_tz=self.owner_tz, day_start=self.day_start)
        return 1

    def _text(self, item: Item, firing: Firing, now: datetime) -> str:
        local = firing.occurrence.astimezone(occur.zone(item.tz or self.owner_tz))
        when = f"{local:%d.%m %H:%M}" if item.at is not None else f"срок {local:%d.%m}"
        late = now - firing.fire_at
        suffix = f"\nопоздало на {int(late.total_seconds() // 60)} мин" if late > LATE_AFTER else ""
        return f"⏰ {when} · {item.title}{suffix}"

    async def _settle(self, firing_id: str, state: str) -> None:
        """Закрыть ожидающее срабатывание. Пропущенное плановое тянет за собой пересчёт:
        иначе цепочка следующих повторений оборвалась бы здесь."""
        async with self.db.write() as session:
            row = await session.get(Firing, firing_id)
            if row is None or row.state != "pending":
                return
            row.state = state
            if state == "skipped" and not row.manual:
                item = await session.get(Item, row.item_id)
                if item is not None:
                    await firings.replan(session, item, owner_tz=self.owner_tz, day_start=self.day_start)

    async def _failed(self, firing_id: str, reason: str) -> None:
        """Записать неудачную отправку. Срабатывание остаётся ожидающим: его снимет только срок давности."""
        async with self.db.write() as session:
            row = await session.get(Firing, firing_id)
            if row is None or row.state != "pending":
                return
            row.attempts += 1
            if row.attempts == ALERT_AFTER:
                journal.record(
                    session, client="scheduler", op="delivery_failed", target=row.item_id,
                    reason=reason[:200], detail={"firing": row.id, "attempts": row.attempts},
                )

    # --- приём ---

    async def handle(self, update: dict) -> None:
        """Одно обновление Telegram: нажатие кнопки или сообщение. Чужих не слушаем."""
        callback = update.get("callback_query")
        if callback is not None:
            if (callback.get("from") or {}).get("id") == self.owner_chat_id:
                await self._button(callback)
            return
        message = update.get("message") or {}
        if (message.get("chat") or {}).get("id") != self.owner_chat_id:
            return
        text = (message.get("text") or "").strip()
        if not text or text.startswith("/"):
            return
        # Пересланное — чужие слова, а не слова владельца: «said» им не бывает.
        origin = "forward" if any(key in message for key in FORWARD_KEYS) else "said"
        try:
            async with self.db.write() as session:
                await facts.add(session, client="telegram", text=text, origin=origin)
        except Refused as refusal:
            await self.messenger.send(f"Не записал: {refusal}")
            return
        await self.messenger.send("Записал.")

    async def _button(self, callback: dict) -> None:
        action, _, firing_id = (callback.get("data") or "").partition(":")
        now = utcnow()
        reply, message_id = "Уже обработано", None
        async with self.db.write() as session:
            firing = await session.get(Firing, firing_id)
            if firing is not None and firing.state == "sent" and action in ("done", "hour", "tomorrow"):
                item = await session.get(Item, firing.item_id)
                message_id = firing.message_id
                if action == "done":
                    firing.state = "done"
                    if item.kind == "task" and item.status == "open":
                        await items.update(
                            session, client="telegram", owner_tz=self.owner_tz, day_start=self.day_start,
                            item_id=item.id, rev=item.rev, changes={"status": "done"}, reason="кнопка «Готово»",
                        )
                    reply = "Готово"
                else:
                    firing.state = "snoozed"
                    until = now + timedelta(hours=1) if action == "hour" else self._tomorrow(now)
                    session.add(
                        Firing(
                            id=new_id("r"), item_id=item.id, occurrence=firing.occurrence, fire_at=until,
                            state="pending", attempts=0, manual=True,
                        )
                    )
                    reply = "Напомню через час" if action == "hour" else "Напомню завтра"
        await self.messenger.answer(callback["id"], reply)
        if message_id is not None:
            await self.messenger.clear_buttons(message_id)

    def _tomorrow(self, now: datetime) -> datetime:
        local_zone = occur.zone(self.owner_tz)
        day = now.astimezone(local_zone).date() + timedelta(days=1)
        return datetime.combine(day, plan.parse_day_start(self.day_start), tzinfo=local_zone).astimezone(UTC)

    # --- циклы ---

    async def run(self, seconds: float = 30) -> None:
        while True:
            try:
                await self.tick()
            except Exception:
                log.exception("reminder tick failed")
            await asyncio.sleep(seconds)

    async def poll(self) -> None:
        offset = None
        while True:
            try:
                for update in await self.messenger.updates(offset):
                    offset = update["update_id"] + 1
                    await self.handle(update)
            except Exception:
                log.exception("telegram poll failed")
                await asyncio.sleep(RETRY_PAUSE)
