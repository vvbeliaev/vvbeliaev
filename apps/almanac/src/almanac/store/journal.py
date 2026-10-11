from sqlalchemy.ext.asyncio import AsyncSession

from almanac.clock import utcnow
from almanac.models import Journal


def record(
    session: AsyncSession, *, client: str, op: str, target: str, reason: str, detail: dict | None = None
) -> None:
    """Строка журнала в ту же транзакцию, что и само изменение."""
    session.add(Journal(at=utcnow(), client=client, op=op, target=target, reason=reason, detail=detail or {}))
