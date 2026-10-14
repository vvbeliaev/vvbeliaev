"""Ядро бенча агентов: сценарии как данные, проверки над разницей состояний, запись и сводка.

Ядро не знает приложения. Приложение даёт адаптер: как поднять мир, как снять состояние, как провести
один ход разговора и что уходит модели как промпт, — и свои проверки поверх общих.
"""

from evals.core.checks import generic
from evals.core.record import Recorder, fingerprint, git_sha, read
from evals.core.scenarios import Checks, Scenario, ScenarioError, judge, load
from evals.core.state import Diff, Outcome, Snapshot, diff, outcome

__all__ = [
    "Checks", "Diff", "Outcome", "Recorder", "Scenario", "ScenarioError", "Snapshot", "diff", "fingerprint",
    "generic", "git_sha", "judge", "load", "outcome", "read",
]
