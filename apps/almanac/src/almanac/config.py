from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

PACKAGE = Path(__file__).parent


class Settings(BaseSettings):
    """Настройки из окружения; имена переменных — те же, заглавными."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite+aiosqlite:///almanac.db"
    owner_tz: str = "UTC"
    day_start: str = "09:00"
    schema_dir: Path = PACKAGE / "schema"
