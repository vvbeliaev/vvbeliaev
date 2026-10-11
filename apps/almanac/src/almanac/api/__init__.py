"""HTTP API. `operation_id` каждой ручки — имя инструмента, которое увидит модель."""

from fastapi import APIRouter

from almanac.api import facts, items, pages, reading

router = APIRouter()
for part in (reading, facts, pages, items):
    router.include_router(part.router)
