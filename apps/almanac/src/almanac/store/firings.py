"""Срабатывания: что и когда отправить. Состояние доставки живёт здесь, а не в тексте."""

from datetime import datetime

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from almanac.clock import utcnow
from almanac.ids import new_id
from almanac.models import Firing, Item
from almanac.timeline import plan


async def replan(session: AsyncSession, item: Item, *, owner_tz: str, day_start: str) -> None:
    """Пересчитать ожидающие срабатывания элемента.

    Отправленные остаются как были, отложенные вручную тоже. У закрытого
    элемента всё ожидающее помечается пропущенным.
    """
    await session.flush()
    pending = (Firing.item_id == item.id, Firing.state == "pending")
    if item.status != "open":
        await session.execute(update(Firing).where(*pending).values(state="skipped"))
        return
    await session.execute(delete(Firing).where(*pending, Firing.manual.is_(False)))
    taken = set((await session.scalars(select(Firing.fire_at).where(Firing.item_id == item.id))).all())
    for occurrence, fire_at in plan.upcoming(item, owner_tz, day_start, utcnow()):
        if fire_at not in taken:
            session.add(
                Firing(
                    id=new_id("r"), item_id=item.id, occurrence=occurrence, fire_at=fire_at,
                    state="pending", attempts=0, manual=False,
                )
            )
    await session.flush()


async def due(session: AsyncSession, now: datetime) -> list[Firing]:
    statement = select(Firing).where(Firing.state == "pending", Firing.fire_at <= now).order_by(Firing.fire_at)
    return list((await session.scalars(statement)).all())
