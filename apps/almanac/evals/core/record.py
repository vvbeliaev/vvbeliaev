"""Запись прогона: строка JSON на разговор, и каждая знает, что именно мерили."""

import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any


def fingerprint(text: str) -> str:
    """Короткий отпечаток текста: одинаковый текст — одинаковый отпечаток, любая правка — другой."""
    return hashlib.sha256(text.encode()).hexdigest()[:12]


def git_sha(where: Path) -> str:
    """Коммит, на котором идёт прогон; `-dirty`, когда в рабочем дереве есть незакоммиченное."""
    try:
        sha = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"], cwd=where, capture_output=True, text=True, check=True
        ).stdout.strip()
        dirty = subprocess.run(
            ["git", "status", "--porcelain", "--", "."], cwd=where, capture_output=True, text=True, check=True
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"
    return f"{sha}-dirty" if dirty else sha


class Recorder:
    """Дописывает строки в JSONL. Файл только растёт: несколько прогонов различаются полем `run`."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def write(self, row: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a") as out:
            out.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")


def read(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
