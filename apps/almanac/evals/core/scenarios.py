"""Сценарии бенча — данные, а не код: в каком мире, что сказал владелец и какой итог ждём.

Файл — TOML, по таблице `[[scenario]]` на сценарий:

    [[scenario]]
    id = "in20"
    split = "tune"            # tune — по нему правят промпт; holdout — показывает, выучено правило или фраза
    world = "empty"           # мир, который адаптер приложения засевает до разговора
    turns = ["напомни через 20 минут позвонить в банк"]
    expect.reminders = { at = ["2026-10-12T12:20"] }

`expect` — проверки по имени с параметрами. Проверки — функции на Python в реестре `Checks`;
неизвестное имя, лишний или пропущенный параметр — ошибка загрузки, а не тихий провал в прогоне.
"""

import inspect
import json
import tomllib
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from evals.core.record import fingerprint
from evals.core.state import Outcome

SPLITS = ("tune", "holdout")
KEYS = {"id", "split", "world", "turns", "expect", "tags"}
# Проверка получает итог разговора и свои параметры; молчит, когда всё сходится, иначе — причина одной строкой.
Check = Callable[..., str | None]


class ScenarioError(ValueError):
    """Файл сценариев не загрузился: сообщение говорит, какой сценарий и что в нём не так."""


class Checks:
    """Реестр проверок. Приложение собирает свой поверх общего: `Checks(generic)`."""

    def __init__(self, *bases: "Checks") -> None:
        self._found: dict[str, Check] = {}
        for base in bases:
            self._found.update(base._found)

    def register(self, check: Check) -> Check:
        self._found[check.__name__] = check
        return check

    def __contains__(self, name: str) -> bool:
        return name in self._found

    def __getitem__(self, name: str) -> Check:
        return self._found[name]

    def bind(self, name: str, params: dict[str, Any]) -> None:
        """Подходят ли параметры проверке — до прогона, а не посреди платного разговора."""
        if name not in self._found:
            raise ScenarioError(f"unknown check {name!r}; known: {', '.join(sorted(self._found))}")
        try:
            inspect.signature(self._found[name]).bind(None, **params)
        except TypeError as error:
            raise ScenarioError(f"check {name!r}: {error}") from error


@dataclass(frozen=True)
class Scenario:
    id: str
    split: str
    world: str
    turns: tuple[str, ...]
    expect: dict[str, dict[str, Any]]
    tags: tuple[str, ...] = ()

    @property
    def sha(self) -> str:
        """Отпечаток сценария: поменялись слова или ожидание — итоги до и после не сравнивают вслепую."""
        body = {"world": self.world, "turns": self.turns, "expect": self.expect}
        return fingerprint(json.dumps(body, ensure_ascii=False, sort_keys=True))


def _scenario(row: dict[str, Any], checks: Checks, worlds: set[str]) -> Scenario:
    name = row.get("id")
    if not isinstance(name, str) or not name:
        raise ScenarioError(f"a scenario without `id`: {row}")
    try:
        if extra := set(row) - KEYS:
            raise ScenarioError(f"unknown keys {sorted(extra)}")
        if row.get("split") not in SPLITS:
            raise ScenarioError(f"`split` must be one of {SPLITS}")
        world = row.get("world", "empty")
        if world not in worlds:
            raise ScenarioError(f"unknown world {world!r}; known: {', '.join(sorted(worlds))}")
        turns = row.get("turns")
        if not isinstance(turns, list) or not turns or not all(isinstance(turn, str) and turn for turn in turns):
            raise ScenarioError("`turns` must be a non-empty list of phrases")
        expect = row.get("expect")
        if not isinstance(expect, dict) or not expect:
            raise ScenarioError("`expect` must name at least one check")
        for check, params in expect.items():
            checks.bind(check, params if isinstance(params, dict) else {})
    except ScenarioError as error:
        raise ScenarioError(f"scenario {name!r}: {error}") from None
    return Scenario(name, row["split"], world, tuple(turns), expect, tuple(row.get("tags", ())))


def load(path: Path, checks: Checks, worlds: Iterable[str]) -> list[Scenario]:
    """Сценарии из файла, проверенные целиком: ошибка в любом — отказ загрузить все."""
    rows = tomllib.loads(path.read_text()).get("scenario", [])
    known = set(worlds)
    found = [_scenario(row, checks, known) for row in rows]
    seen: set[str] = set()
    for scenario in found:
        if scenario.id in seen:
            raise ScenarioError(f"scenario {scenario.id!r} appears twice")
        seen.add(scenario.id)
    return found


def judge(scenario: Scenario, checks: Checks, result: Outcome) -> list[str]:
    """Причины провала по всем проверкам сценария; пустой список — сценарий прошёл."""
    reasons = []
    for name, params in scenario.expect.items():
        if (reason := checks[name](result, **params)) is not None:
            reasons.append(f"{name}: {reason}")
    return reasons
