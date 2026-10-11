"""Проверки записи, которым не нужна база. Отказ — `Refused` с текстом для модели."""

import re
from collections.abc import Iterable
from datetime import timedelta

from almanac.errors import Refused

PAGE_PATH = re.compile(r"^pages/([a-z0-9-]+)/([a-z0-9]+(?:-[a-z0-9]+)*)\.md$")
LIST_SLUG = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
SLUG_LIMIT = 60


def page_path(path: str, types: Iterable[str]) -> tuple[str, str]:
    known = ", ".join(sorted(types))
    match = PAGE_PATH.match(path)
    if match is None:
        raise Refused(
            f"bad page path {path!r}: expected pages/<type>/<slug>.md, slug of a-z, 0-9 and single dashes; "
            f"types: {known}"
        )
    kind, slug = match.groups()
    if kind not in types:
        raise Refused(f"unknown page type {kind!r}; types: {known}")
    if len(slug) > SLUG_LIMIT:
        raise Refused(f"slug is longer than {SLUG_LIMIT} characters")
    return kind, slug


def one_line(value: str, *, name: str, limit: int) -> str:
    text = (value or "").strip()
    if not text:
        raise Refused(f"{name} is empty")
    if "\n" in text or "\r" in text:
        raise Refused(f"{name} must be one line")
    if len(text) > limit:
        raise Refused(f"{name} is longer than {limit} characters")
    return text


def norm_name(value: str) -> str:
    """Имя для сравнения дублей: без регистра, `ё` как `е`, пробелы схлопнуты."""
    return " ".join(value.casefold().replace("ё", "е").split())


def fragment(body: str, old: str) -> None:
    if not old:
        raise Refused("`old` is empty")
    count = body.count(old)
    if count == 0:
        raise Refused("`old` not found in the page body; read the page again and copy the fragment exactly")
    if count > 1:
        raise Refused(f"`old` occurs {count} times; widen the fragment until it is unique")


SECRET_PATTERNS = [
    ("private key", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("API key", re.compile(r"\bsk-[A-Za-z0-9_-]{20,}")),
    ("GitHub token", re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{36}\b|\bgithub_pat_[A-Za-z0-9_]{20,}")),
    ("Slack token", re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}")),
    ("AWS key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("Telegram bot token", re.compile(r"\b\d{8,10}:[A-Za-z0-9_-]{35}\b")),
    ("JWT", re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}")),
]
# 15–19 цифр подряд, между ними допустим один пробел или дефис. 13 цифр не берём:
# это длина отметки времени в миллисекундах.
CARD = re.compile(r"(?<!\d)(?:\d[ -]?){14,18}\d(?!\d)")


def _luhn(digits: str) -> bool:
    total = 0
    for index, char in enumerate(reversed(digits)):
        digit = int(char)
        if index % 2 == 1:
            digit *= 2
            if digit > 9:
                digit -= 9
        total += digit
    return total % 10 == 0


def no_secret(*texts: str | None) -> None:
    for text in texts:
        if not text:
            continue
        for label, pattern in SECRET_PATTERNS:
            if pattern.search(text):
                raise Refused(f"looks like a secret ({label}); secrets are not stored here")
        for match in CARD.finditer(text):
            if _luhn(re.sub(r"\D", "", match.group())):
                raise Refused("looks like a secret (card number); secrets are not stored here")


DURATION = re.compile(r"^P(?:(\d+)W)?(?:(\d+)D)?(?:T(?:(\d+)H)?(?:(\d+)M)?)?$")


def duration(value: str) -> timedelta:
    """Смещение ISO 8601 из недель, дней, часов и минут: `PT0M`, `PT1H`, `P1D`, `P1W`."""
    match = DURATION.match(value or "")
    if match is None or value in ("P", "PT") or value.endswith("T"):
        raise Refused(f"bad duration {value!r}: ISO 8601 like PT0M, PT30M, PT1H, P1D, P1W")
    weeks, days, hours, minutes = (int(group) if group else 0 for group in match.groups())
    return timedelta(weeks=weeks, days=days, hours=hours, minutes=minutes)
