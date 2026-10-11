"""HTTP API. `operation_id` каждой ручки — имя инструмента, которое увидит модель."""

from fastapi import APIRouter, Depends

from almanac.api import facts, items, pages, reading
from almanac.identity import caller

# Закрыт весь API, в том числе ручки чтения: без личности ответ 401.
router = APIRouter(dependencies=[Depends(caller)])
for part in (reading, facts, pages, items):
    router.include_router(part.router)
