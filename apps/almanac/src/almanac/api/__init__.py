"""HTTP API. `operation_id` каждой ручки — имя инструмента, которое увидит модель."""

from fastapi import APIRouter, Depends

from almanac.api import facts, items, pages, reading
from almanac.api.deps import clean_input
from almanac.identity import caller

# Закрыт весь API, в том числе ручки чтения: без личности ответ 401. Дальше запрос чистят от NUL.
router = APIRouter(dependencies=[Depends(caller), Depends(clean_input)])
for part in (reading, facts, pages, items):
    router.include_router(part.router)
