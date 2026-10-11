from datetime import UTC, datetime


def _system() -> datetime:
    return datetime.now(UTC)


# Тесты подменяют `_now`; код зовёт только `utcnow`.
_now = _system


def utcnow() -> datetime:
    return _now()
