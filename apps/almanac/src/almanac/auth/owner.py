"""Вход владельца: пароль, сессия, ограничение попыток.

Хэш пароля владелец получает сам: `python -m almanac.auth.owner` спросит пароль
и напечатает строку для `OWNER_PASSWORD_HASH`: `scrypt:N:r:p:соль:хэш`. Разделитель —
двоеточие: знак доллара в переменных окружения подставляется оболочкой.
"""

import getpass
import hashlib
import hmac
import secrets
from collections import deque
from datetime import timedelta

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from almanac.auth.tokens import hash_token, new_token
from almanac.clock import utcnow
from almanac.models import Session

SESSION_COOKIE = "almanac_session"
SESSION_TTL = timedelta(days=30)
# Боевые параметры scrypt (OWASP: N не ниже 2**17 при r=8, p=1). Они лежат в самой строке хэша,
# так что стоимость можно поднять, не ломая старые хэши.
N, R, P = 2**17, 8, 1
MAX_N = 2**20
MAX_MEMORY = 2**28


def _digest(password: str, salt: bytes, n: int, r: int, p: int) -> bytes:
    return hashlib.scrypt(password.encode(), salt=salt, n=n, r=r, p=p, maxmem=MAX_MEMORY, dklen=32)


def hash_password(password: str, n: int = N) -> str:
    salt = secrets.token_bytes(16)
    return f"scrypt:{n}:{R}:{P}:{salt.hex()}:{_digest(password, salt, n, R, P).hex()}"


def verify_password(password: str, stored: str) -> bool:
    """Строка — `scrypt:N:r:p:соль:хэш`. Всё, что на неё не похоже, — `False`, не исключение."""
    try:
        scheme, n, r, p, salt, expected = stored.split(":")
        n, r, p = int(n), int(r), int(p)
        if scheme != "scrypt" or n > MAX_N:
            return False
        actual = _digest(password, bytes.fromhex(salt), n, r, p)
        return hmac.compare_digest(actual, bytes.fromhex(expected))
    except (ValueError, TypeError, OverflowError):  # не тот формат, не число, не hex, параметры scrypt вне границ
        return False


async def open_session(session: AsyncSession) -> str:
    token, now = new_token(), utcnow()
    session.add(Session(token_hash=hash_token(token), created_at=now, expires_at=now + SESSION_TTL))
    return token


async def session_alive(session: AsyncSession, token: str | None) -> bool:
    if not token:
        return False
    row = await session.get(Session, hash_token(token))
    return row is not None and row.expires_at > utcnow()


async def close_session(session: AsyncSession, token: str | None) -> None:
    await session.execute(delete(Session).where(Session.token_hash == hash_token(token or "")))


class Attempts:
    """Не больше `limit` попыток входа за `window` секунд. Владелец один, счётчик общий."""

    def __init__(self, limit: int = 5, window: float = 60.0) -> None:
        self._limit, self._window = limit, window
        self._seen: deque[float] = deque()

    def allow(self) -> bool:
        now = utcnow().timestamp()
        while self._seen and now - self._seen[0] > self._window:
            self._seen.popleft()
        if len(self._seen) >= self._limit:
            return False
        self._seen.append(now)
        return True


if __name__ == "__main__":
    print(hash_password(getpass.getpass("Пароль владельца: ")))
