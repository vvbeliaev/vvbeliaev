"""Вход владельца: пароль, сессия, ограничение попыток.

Хэш пароля владелец получает сам: `python -m almanac.auth.owner` спросит пароль
и напечатает строку для `OWNER_PASSWORD_HASH`. Разделитель — двоеточие: знак
доллара в переменных окружения подставляется оболочкой.
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
N, R, P = 2**14, 8, 1


def _digest(password: str, salt: bytes) -> bytes:
    return hashlib.scrypt(password.encode(), salt=salt, n=N, r=R, p=P, dklen=32)


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    return f"scrypt:{salt.hex()}:{_digest(password, salt).hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        scheme, salt, expected = stored.split(":")
        if scheme != "scrypt":
            return False
        return hmac.compare_digest(_digest(password, bytes.fromhex(salt)), bytes.fromhex(expected))
    except ValueError:
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
