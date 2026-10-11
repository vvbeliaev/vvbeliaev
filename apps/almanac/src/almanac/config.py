import re
from pathlib import Path
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PACKAGE = Path(__file__).parent
LOOPBACK = frozenset({"localhost", "127.0.0.1", "::1"})
DAY_START = re.compile(r"([01][0-9]|2[0-3]):[0-5][0-9]")
ICS_TOKEN_MIN = 32
DATABASE_SCHEME = "postgresql+asyncpg://"


class Settings(BaseSettings):
    """Настройки из окружения; имена переменных — те же, заглавными."""

    # Без значения во вводе: в адресе базы стоит пароль, а текст ошибки уходит в журнал запуска.
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", hide_input_in_errors=True)

    # Локальная база из compose. Пароль сюда не вписан: адрес с ним лежит в `.env` (`make up`).
    database_url: str = "postgresql+asyncpg://almanac@127.0.0.1:5434/almanac"
    owner_tz: str = "UTC"
    day_start: str = "09:00"
    schema_dir: Path = PACKAGE / "schema"
    base_url: str = "http://127.0.0.1:8000"
    owner_password_hash: str = ""
    mcp_code_mode: bool = True
    # Сайт на этой же машине читает без входа (`identity.py`). Только при BASE_URL на саму машину.
    local_site: bool = False
    # Собранный сайт (`make web`). Каталога нет — сайта нет.
    site_dir: Path = PACKAGE.parents[1] / "web" / "dist"
    # Без токена и чата бот и цикл напоминаний не запускаются.
    telegram_bot_token: str = ""
    telegram_owner_chat_id: int = 0
    # Секрет в адресе ленты `/calendar/<токен>.ics`. Пусто — лента выключена.
    ics_token: str = ""

    @field_validator("database_url")
    @classmethod
    def _database_url(cls, value: str) -> str:
        """Драйвер один — asyncpg, и сервер, и миграции идут на нём. Значение в ошибку не попадает: там пароль."""
        if not value.startswith(DATABASE_SCHEME):
            scheme = value.partition("://")[0] if "://" in value else "no scheme"
            raise ValueError(f"DATABASE_URL must start with {DATABASE_SCHEME}, got {scheme!r}")
        return value

    @field_validator("day_start")
    @classmethod
    def _day_start(cls, value: str) -> str:
        if not DAY_START.fullmatch(value):
            raise ValueError(f"DAY_START must be HH:MM from 00:00 to 23:59, got {value!r}")
        return value

    @field_validator("ics_token")
    @classmethod
    def _ics_token(cls, value: str) -> str:
        """Секрет в адресе — единственная защита ленты: короткий угадывается. Пусто — лента выключена."""
        if value and len(value) < ICS_TOKEN_MIN:
            raise ValueError(f"ICS_TOKEN must be empty or at least {ICS_TOKEN_MIN} characters, got {len(value)}")
        return value

    @field_validator("base_url")
    @classmethod
    def _base_url(cls, value: str) -> str:
        """Адрес, по которому сервер виден снаружи: из него строятся адреса OAuth и проверяется `Origin`.
        По голому http токены и cookie ходили бы открытым текстом, поэтому http — только на себя."""
        value = value.rstrip("/")
        parts = urlsplit(value)
        try:
            host = parts.hostname
        except ValueError:
            host = None
        if not host or not (parts.scheme == "https" or (parts.scheme == "http" and host in LOOPBACK)):
            raise ValueError(f"BASE_URL must be https://…, or http:// on localhost, got {value!r}")
        return value

    @model_validator(mode="after")
    def _local_site(self) -> "Settings":
        """Чтение без входа — только для сервера, который виден лишь со своей машины."""
        if self.local_site and urlsplit(self.base_url).hostname not in LOOPBACK:
            raise ValueError("LOCAL_SITE works only when BASE_URL points at this machine (localhost, 127.0.0.1)")
        return self

    @field_validator("owner_tz")
    @classmethod
    def _owner_tz(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError, OSError) as error:  # неизвестное, пустое имя, каталог
            raise ValueError(f"OWNER_TZ must be an IANA zone like Europe/Berlin, got {value!r}") from error
        return value
