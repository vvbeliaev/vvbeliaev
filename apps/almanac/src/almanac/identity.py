"""Кто за вызовом. На этом этапе личности нет: любой вызов — `local`.

План 2 заменит тело `caller`: клиент OAuth или сессия владельца, а без них — 401.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Caller:
    client: str


def caller() -> Caller:
    return Caller(client="local")
