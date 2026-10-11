"""Схема: правила для модели и типы страниц. Это данные: каталог подменяется через `SCHEMA_DIR`."""

import tomllib
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Schema:
    guide: str
    types: dict[str, str]


def load(directory: Path) -> Schema:
    data = tomllib.loads((directory / "types.toml").read_text(encoding="utf-8"))
    types = {name: entry["description"] for name, entry in data["types"].items()}
    return Schema(guide=(directory / "guide.md").read_text(encoding="utf-8"), types=types)
