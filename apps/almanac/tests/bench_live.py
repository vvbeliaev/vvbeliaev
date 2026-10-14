"""Живой замер собеседника на настоящих моделях: сценарии из `evals/scenarios.toml`, итог — в базе.

Не тест и в обычный прогон не входит: имя файла не `test_*`. Запуск — `make bench` (см. evals/README.md)
или напрямую, ключ — в окружении:

    BENCH_CHAIN=google:gemini-3.8-flash BENCH_GOOGLE_KEY=… BENCH_REPS=3 \\
        uv run --package almanac pytest -q tests/bench_live.py

Каждый запрос к модели стоит денег. База — временная из `conftest.py`, часы стоят. Каждый разговор —
строка JSON в `BENCH_OUT`; замер никогда не «падает» из-за ошибки модели, он её записывает.
"""

import os
from datetime import UTC, datetime
from pathlib import Path

import pytest

from almanac import assistant
from almanac.config import Settings
from evals import adapter
from evals.core import Recorder, fingerprint, git_sha, judge, load

CHAIN = os.environ.get("BENCH_CHAIN", "")
THINKING = os.environ.get("BENCH_THINKING", "low")
REPS = int(os.environ.get("BENCH_REPS", "10"))
OUT = Path(os.environ.get("BENCH_OUT", ".bench/bench.jsonl"))
# Через запятую — только эти сценарии; пусто — все.
ONLY = {name for name in os.environ.get("BENCH_ONLY", "").split(",") if name}
# Имена свои: обычные имена ключей conftest убирает из окружения каждого теста.
KEYS = {
    "anthropic_api_key": os.environ.get("BENCH_ANTHROPIC_KEY", ""),
    "google_api_key": os.environ.get("BENCH_GOOGLE_KEY", ""),
}
# Один прогон — одно значение на весь процесс: по нему отчёт отделяет этот прогон от прошлых в том же файле.
RUN = os.environ.get("BENCH_RUN") or datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
GIT = git_sha(Path(__file__).parent)

SCENARIOS = [s for s in load(adapter.SCENARIOS, adapter.checks, adapter.WORLDS) if not ONLY or s.id in ONLY]
recorder = Recorder(OUT)
_prompt: dict[str, str] = {}

pytestmark = pytest.mark.skipif(not CHAIN or not any(KEYS.values()), reason="BENCH_CHAIN and a key are required")


@pytest.mark.parametrize("rep", range(REPS))
@pytest.mark.parametrize("scenario", SCENARIOS, ids=lambda scenario: scenario.id)
async def test_bench(app, db, pg_url, monkeypatch, scenario, rep: int):
    monkeypatch.setattr(assistant, "THINKING", THINKING)
    guide = app.state.ctx.schema.guide
    if "sha" not in _prompt:
        _prompt["sha"] = fingerprint(await adapter.prompt_surface(app.state.mcp, guide))
    settings = Settings(_env_file=None, database_url=pg_url, owner_tz=adapter.TZ, assistant_model=CHAIN, **KEYS)
    talker = assistant.build(settings, app.state.mcp, guide=guide)
    row: dict = {
        "run": RUN, "git": GIT, "prompt": _prompt["sha"], "chain": CHAIN, "thinking": THINKING,
        "scenario": scenario.id, "case": scenario.sha, "split": scenario.split, "world": scenario.world,
        "rep": rep, "turns": [],
    }
    try:
        await adapter.WORLDS[scenario.world](db, app.state.ctx.schema.types)
        turns, result = await adapter.converse(talker, db, scenario)
        reasons = judge(scenario, adapter.checks, result)
        row |= {"turns": turns, "ok": not reasons, "reasons": reasons}
    except Exception as error:  # noqa: BLE001 — замер записывает любой сбой модели, а не падает на нём
        row |= {"ok": False, "reasons": ["error"], "error": f"{type(error).__name__}: {str(error)[:300]}"}
    recorder.write(row)
