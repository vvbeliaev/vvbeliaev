import re
from pathlib import Path
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PACKAGE = Path(__file__).parent
LOOPBACK = frozenset({"localhost", "127.0.0.1", "::1"})
DAY_START = re.compile(r"([01][0-9]|2[0-3]):[0-5][0-9]")


class Settings(BaseSettings):
    """Настройки из окружения; имена переменных — те же, заглавными."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite+aiosqlite:///almanac.db"
    owner_tz: str = "UTC"
    day_start: str = "09:00"
    schema_dir: Path = PACKAGE / "schema"
    base_url: str = "http://127.0.0.1:8000"
    owner_password_hash: str = ""
    mcp_code_mode: bool = True
    # Без токена и чата бот и цикл напоминаний не запускаются.
    telegram_bot_token: str = ""
    telegram_owner_chat_id: int = 0

    @field_validator("day_start")
    @classmethod
    def _day_start(cls, value: str) -> str:
        if not DAY_START.fullmatch(value):
            raise ValueError(f"DAY_START must be HH:MM from 00:00 to 23:59, got {value!r}")
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

    @field_validator("owner_tz")
    @classmethod
    def _owner_tz(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError, OSError) as error:  # неизвестное, пустое имя, каталог
            raise ValueError(f"OWNER_TZ must be an IANA zone like Europe/Berlin, got {value!r}") from error
        return value
