"""Срабатывания: что и когда отправить. Состояние доставки живёт здесь, а не в тексте."""

import logging
from datetime import datetime

from sqlalchemy import delete, exists, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from almanac.clock import utcnow
from almanac.ids import new_id
from almanac.models import Firing, Item
from almanac.timeline import plan

log = logging.getLogger(__name__)


async def replan(session: AsyncSession, item: Item, *, owner_tz: str, day_start: str) -> None:
    """Пересчитать ожидающие срабатывания элемента.

    Отправленные остаются как были, отложенные вручную тоже, и созревшие ожидающие — тоже:
    их время пришло, их отправит цикл. Заново считаются только те, что ещё впереди.
    У закрытого элемента всё ожидающее помечается пропущенным.
    """
    await session.flush()
    now = utcnow()
    pending = (Firing.item_id == item.id, Firing.state == "pending")
    if item.status != "open":
        await session.execute(update(Firing).where(*pending).values(state="skipped"))
        return
    await session.execute(delete(Firing).where(*pending, Firing.manual.is_(False), Firing.fire_at > now))
    # Пропущенное не занимает момент: после повторного открытия элемент снова напомнит в тот же срок.
    live = (Firing.item_id == item.id, Firing.state != "skipped")
    taken = set((await session.scalars(select(Firing.fire_at).where(*live))).all())
    for occurrence, fire_at in plan.upcoming(item, owner_tz, day_start, now):
        if fire_at not in taken:
            session.add(
                Firing(
                    id=new_id("r"), item_id=item.id, occurrence=occurrence, fire_at=fire_at,
                    state="pending", attempts=0, manual=False,
                )
            )
    await session.flush()


async def skip_through(session: AsyncSession, item_id: str, occurrence: datetime) -> None:
    """Закрыто повторение `occurrence` (UTC): всё ожидающее до него включительно пропущено.

    Сюда входят и отложенные вручную, с повторением в той же отметке: закрытое дело не должно напомнить о себе.
    Отправленные и обработанные остаются как были. Следом нужен `replan`: он спланирует следующее повторение.
    """
    await session.flush()
    await session.execute(
        update(Firing)
        .where(Firing.item_id == item_id, Firing.state == "pending", Firing.occurrence <= occurrence)
        .values(state="skipped")
    )


async def unplanned(session: AsyncSession, *, owner_tz: str, day_start: str, now: datetime) -> list[str]:
    """Открытые элементы с напоминаниями, у которых нет ожидающего срабатывания, хотя по плану оно есть.

    Такое бывает, когда цепочка повторов оборвалась: срабатывание пропущено, а новое не спланировано.
    Выборка идёт запросом, а не обходом всех элементов; в плане смотрим только отобранных.
    """
    waiting = exists().where(Firing.item_id == Item.id, Firing.state == "pending", Firing.manual.is_(False))
    statement = select(Item).where(
        Item.status == "open", func.jsonb_array_length(Item.remind) > 0, ~waiting
    )
    lost = []
    for item in (await session.scalars(statement)).all():
        try:
            if plan.upcoming(item, owner_tz, day_start, now):
                lost.append(item.id)
        except Exception:
            log.exception("item %s cannot be planned", item.id)
    return lost


async def due(session: AsyncSession, now: datetime) -> list[Firing]:
    statement = select(Firing).where(Firing.state == "pending", Firing.fire_at <= now).order_by(Firing.fire_at)
    return list((await session.scalars(statement)).all())
