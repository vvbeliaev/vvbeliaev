"""Кто за вызовом API.

Дверей две. Владелец в браузере приходит с cookie сессии — клиент `site`. Код
за MCP зовёт API внутри процесса и несёт внутренний заголовок с именем своего
клиента. Заголовок подписан ключом, который родился вместе с процессом:
снаружи его не подделать.
"""

import hashlib
import hmac
import secrets
from contextvars import ContextVar
from dataclasses import dataclass

from fastapi import HTTPException, Request

from almanac.auth import owner

INTERNAL_HEADER = "x-almanac-client"
_KEY = secrets.token_bytes(32)

# Имя клиента для вызовов MCP в памяти процесса, без HTTP и токена: тесты и бот.
acting: ContextVar[str | None] = ContextVar("almanac_acting", default=None)


@dataclass(frozen=True)
class Caller:
    client: str


def _sign(client: str) -> str:
    return hmac.new(_KEY, client.encode(), hashlib.sha256).hexdigest()


def sign_internal(client: str) -> str:
    return f"{client}.{_sign(client)}"


def read_internal(value: str | None) -> str | None:
    """Имя клиента из внутреннего заголовка — или `None`, если подпись не наша."""
    if not value:
        return None
    client, _, signature = value.rpartition(".")
    if not client or not hmac.compare_digest(signature.encode(), _sign(client).encode()):
        return None
    return client


async def caller(request: Request) -> Caller:
    client = read_internal(request.headers.get(INTERNAL_HEADER))
    if client is not None:
        return Caller(client=client)
    token = request.cookies.get(owner.SESSION_COOKIE)
    if token:
        async with request.app.state.db.read() as session:
            if await owner.session_alive(session, token):
                return Caller(client="site")
    raise HTTPException(status_code=401, detail="no identity: sign in at /login or come through the MCP door")
