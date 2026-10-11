"""Кто за вызовом API.

Дверей две. Владелец в браузере приходит с cookie сессии — клиент `site`. Код
за MCP зовёт API внутри процесса и несёт внутренний заголовок с именем своего
клиента. Заголовок подписан ключом, который родился вместе с процессом:
снаружи его не подделать.

Третьего входа нет, но есть послабление для сервера на своей машине (`LOCAL_SITE`):
браузер этой же машины читает без входа. Только читает.
"""

import hashlib
import hmac
import secrets
from contextvars import ContextVar
from dataclasses import dataclass
from urllib.parse import urlsplit

from fastapi import HTTPException, Request

from almanac.auth import owner

INTERNAL_HEADER = "x-almanac-client"
READING = frozenset({"GET", "HEAD"})
LOOPBACK_PEERS = frozenset({"127.0.0.1", "::1"})
# Браузер подписывает запрос тем, откуда он сделан. Без заголовка — не браузер (curl).
OWN_FETCH = frozenset({"same-origin", "none"})
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


def _reads_from_here(request: Request) -> bool:
    """Чтение без входа с этой же машины, когда владелец включил `LOCAL_SITE`.

    Условия — все разом. Запрос только читает. Соединение пришло с самой машины. Host —
    ровно адрес сервера: страница чужого сайта, чьё имя направили на 127.0.0.1, придёт со
    своим именем и не пройдёт. И запрос сделан самим сайтом, а не чужой страницей.
    """
    settings = request.app.state.settings
    if not settings.local_site or request.method not in READING:
        return False
    peer = request.client.host if request.client else None
    return (
        peer in LOOPBACK_PEERS
        and request.headers.get("host") == urlsplit(settings.base_url).netloc
        and request.headers.get("sec-fetch-site", "none") in OWN_FETCH
    )


async def caller(request: Request) -> Caller:
    client = read_internal(request.headers.get(INTERNAL_HEADER))
    if client is not None:
        return Caller(client=client)
    token = request.cookies.get(owner.SESSION_COOKIE)
    if token:
        async with request.app.state.db.read() as session:
            if await owner.session_alive(session, token):
                return Caller(client="site")
    if _reads_from_here(request):
        return Caller(client="site")
    raise HTTPException(status_code=401, detail="no identity: sign in at /login or come through the MCP door")
