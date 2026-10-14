"""Итог разговора: состояние до и после, разница между ними и ответы. Общие проверки — над ним.

Состояние приложения — словарь коллекций: `{"items": {id: запись}, "pages": {path: запись}}`. Записи —
простые словари, сравнимые на равенство. Проверять удобнее разницу, чем всё состояние: мир может быть
засеян сотнями записей, а важно только то, что тронул этот разговор.
"""

from dataclasses import dataclass, field
from typing import Any

Record = dict[str, Any]
Snapshot = dict[str, dict[str, Record]]


@dataclass(frozen=True)
class Diff:
    """Что разговор сделал с каждой коллекцией. В записях есть `id` — ключ записи в своей коллекции."""

    added: dict[str, list[Record]] = field(default_factory=dict)
    removed: dict[str, list[Record]] = field(default_factory=dict)
    changed: dict[str, list[tuple[Record, Record]]] = field(default_factory=dict)

    def touched(self, collection: str) -> list[str]:
        """Ключи всех записей коллекции, которые разговор добавил, убрал или поменял."""
        return [
            *(record["id"] for record in self.added.get(collection, [])),
            *(record["id"] for record in self.removed.get(collection, [])),
            *(after["id"] for _, after in self.changed.get(collection, [])),
        ]


def diff(before: Snapshot, after: Snapshot) -> Diff:
    added: dict[str, list[Record]] = {}
    removed: dict[str, list[Record]] = {}
    changed: dict[str, list[tuple[Record, Record]]] = {}
    for collection in sorted(set(before) | set(after)):
        old, new = before.get(collection, {}), after.get(collection, {})
        if fresh := [{"id": key, **new[key]} for key in new if key not in old]:
            added[collection] = fresh
        if gone := [{"id": key, **old[key]} for key in old if key not in new]:
            removed[collection] = gone
        if moved := [({"id": key, **old[key]}, {"id": key, **new[key]}) for key in new if key in old and old[key] != new[key]]:
            changed[collection] = moved
    return Diff(added, removed, changed)


@dataclass(frozen=True)
class Outcome:
    """Всё, что видят проверки: оба состояния, их разница и ответы по ходам."""

    before: Snapshot
    after: Snapshot
    answers: tuple[str, ...]
    diff: Diff


def outcome(before: Snapshot, after: Snapshot, answers: tuple[str, ...]) -> Outcome:
    return Outcome(before, after, answers, diff(before, after))
