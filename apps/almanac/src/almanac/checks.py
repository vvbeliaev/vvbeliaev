"""Проверки записи, которым не нужна база. Отказ — `Refused` с текстом для модели."""

import re
from collections.abc import Iterable, Iterator
from datetime import timedelta

from almanac.errors import Refused

# Оба выражения применяются через `fullmatch`: `$` пропускает перевод строки в конце.
PAGE_PATH = re.compile(r"pages/([a-z0-9-]+)/([a-z0-9]+(?:-[a-z0-9]+)*)\.md")
LIST_SLUG = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
SLUG_LIMIT = 60
# Пределы колонок `items.list` и `items.rrule`: Postgres длину проверяет, и без отказа здесь запись упала бы в базе.
LIST_LIMIT = 60
RRULE_LIMIT = 300


def page_path(path: str, types: Iterable[str]) -> tuple[str, str]:
    known = ", ".join(sorted(types))
    match = PAGE_PATH.fullmatch(path)
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


# Postgres не хранит нулевой символ в тексте и в JSON: без отказа здесь запись упала бы в базе, а ручка отдала 500.
NUL = "\x00"
# То, что Postgres не сохранит: нулевой символ и одиночный суррогат — половина пары UTF-16,
# которую в UTF-8 не закодировать. Оба проходят как допустимый JSON.
UNSTORABLE = re.compile("[\x00\ud800-\udfff]")


def has_nul(value: object) -> bool:
    """Есть ли несохраняемый символ в строке, а также в списках и словарях (ключи и значения) на любой глубине."""
    if isinstance(value, str):
        return UNSTORABLE.search(value) is not None
    if isinstance(value, dict):
        return any(has_nul(key) or has_nul(item) for key, item in value.items())
    if isinstance(value, (list, tuple)):
        return any(has_nul(item) for item in value)
    return False


def no_nul(*values: object) -> None:
    if any(has_nul(value) for value in values):
        raise Refused(
            "text contains a character that cannot be stored: NUL (\\x00) or half of a surrogate pair; "
            "remove it and try again"
        )


def one_line(value: str, *, name: str, limit: int) -> str:
    text = (value or "").strip()
    if not text:
        raise Refused(f"{name} is empty")
    if "\n" in text or "\r" in text:
        raise Refused(f"{name} must be one line")
    if len(text) > limit:
        raise Refused(f"{name} is longer than {limit} characters")
    return text


def reason(value: str) -> str:
    """Причина записи: одна строка, без секретов. Она остаётся в журнале и в ревизиях."""
    text = one_line(value, name="reason", limit=200)
    no_secret(text)
    return text


# Все символы, которые отображение дня считает концом строки (как `str.splitlines`).
LINE_BREAK = re.compile(r"[\n\r\x0b\x0c\x1c-\x1e\x85\u2028\u2029]")
URL_LIMIT = 2000


def web_url(value: str) -> str:
    """Адрес источника: одна строка до 2000 символов, `http://` или `https://`."""
    if len(value) > URL_LIMIT or LINE_BREAK.search(value) or not value.startswith(("http://", "https://")):
        raise Refused("url must be a single-line http(s) address")
    return value


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
# Номер карты ищем окнами по группам цифр: рядом с номером бывают срок, CVV, номер заказа,
# и жадный «самый длинный ряд» тогда не проходит Luhn. Группы разделены пробелами, точками
# или дефисами. 13 цифр подряд не берём: это длина отметки времени в миллисекундах.
DIGIT_RUN = re.compile(r"\d+(?:[ .\-]+\d+)*")
DIGITS = re.compile(r"\d+")


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


def _card_candidates(text: str) -> Iterator[str]:
    """Цифры, похожие на номер карты: одна группа в 15–19 цифр, 4×4 (и хвост 1–3), Amex 4-6-5."""
    for run in DIGIT_RUN.finditer(text):
        groups = DIGITS.findall(run.group())
        for start, group in enumerate(groups):
            if 15 <= len(group) <= 19:
                yield group
            head = groups[start : start + 4]
            if len(head) == 4 and all(len(part) == 4 for part in head):
                yield "".join(head)
                tail = groups[start + 4 : start + 5]
                if tail and len(tail[0]) <= 3:
                    yield "".join(head) + tail[0]
            if [len(part) for part in groups[start : start + 3]] == [4, 6, 5]:
                yield "".join(groups[start : start + 3])


def no_secret(*texts: str | None) -> None:
    for text in texts:
        if not text:
            continue
        for label, pattern in SECRET_PATTERNS:
            if pattern.search(text):
                raise Refused(f"looks like a secret ({label}); secrets are not stored here")
        if any(_luhn(number) for number in _card_candidates(text)):
            raise Refused("looks like a secret (card number); secrets are not stored here")


# Числа до четырёх цифр: больше не нужно, а `timedelta` на огромном числе падает с OverflowError.
DURATION = re.compile(r"P(?:(\d{1,4})W)?(?:(\d{1,4})D)?(?:T(?:(\d{1,4})H)?(?:(\d{1,4})M)?)?")


def duration(value: str) -> timedelta:
    """Смещение ISO 8601 из недель, дней, часов и минут: `PT0M`, `PT1H`, `P1D`, `P1W`."""
    match = DURATION.fullmatch(value or "")
    if match is None or value in ("P", "PT") or value.endswith("T"):
        raise Refused(f"bad duration {value!r}: ISO 8601 like PT0M, PT30M, PT1H, P1D, P1W")
    weeks, days, hours, minutes = (int(group) if group else 0 for group in match.groups())
    return timedelta(weeks=weeks, days=days, hours=hours, minutes=minutes)
