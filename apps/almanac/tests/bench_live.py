"""Живой замер собеседника на настоящих моделях: фразы владельца и проверяемый итог в базе.

Не тест и в обычный прогон не входит: имя файла не `test_*`. Запуск явный, ключ — в окружении:

    BENCH_CHAIN=anthropic:claude-haiku-5-5 BENCH_THINKING=low BENCH_ANTHROPIC_KEY=… BENCH_OUT=out.jsonl \\
        uv run --package almanac pytest -q tests/bench_live.py

Каждый запрос к модели стоит денег. Данные выдуманные, база — временная из `conftest.py`, часы стоят:
понедельник 2026-10-12, 12:00 в Берлине. Итог каждого разговора — строка JSON в `BENCH_OUT`; замер
никогда не «падает» из-за ошибки модели, он её записывает.
"""

import json
import os
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import pytest
from pydantic_ai.messages import ModelResponse
from sqlalchemy import select

from almanac import assistant
from almanac.config import Settings
from almanac.models import Item
from almanac.store import facts

CHAIN = os.environ.get("BENCH_CHAIN", "")
THINKING = os.environ.get("BENCH_THINKING", "low")
REPS = int(os.environ.get("BENCH_REPS", "10"))
OUT = Path(os.environ.get("BENCH_OUT", "bench.jsonl"))
# Имена свои: обычные имена ключей conftest убирает из окружения каждого теста.
KEYS = {
    "anthropic_api_key": os.environ.get("BENCH_ANTHROPIC_KEY", ""),
    "google_api_key": os.environ.get("BENCH_GOOGLE_KEY", ""),
}

pytestmark = pytest.mark.skipif(not CHAIN or not any(KEYS.values()), reason="BENCH_CHAIN and a key are required")

HOUR_BEFORE = {"PT1H", "PT60M"}


@dataclass(frozen=True)
class State:
    """Что осталось после разговора: дела, хвост во входящих и ответы собеседника."""

    items: list[dict]
    inbox: int
    answers: list[str]

    @property
    def open(self) -> list[dict]:
        return [item for item in self.items if item["status"] == "open"]


Check = Callable[[State], str | None]


def reminders(*moments: datetime, lead: set[str] | None = None, kind: str | None = None) -> Check:
    """Ровно эти открытые дела на эти минуты, и у каждого есть напоминание (`lead` — какое именно, `kind` — вид)."""

    def check(state: State) -> str | None:
        if len(state.open) != len(moments):
            return f"open items: {len(state.open)}, want {len(moments)}"
        if sorted(item["at"] for item in state.open) != sorted(moments):
            return f"at {[str(item['at']) for item in state.open]}"
        for item in state.open:
            if not item["remind"]:
                return "no remind"
            if lead and not lead & set(item["remind"]):
                return f"remind {item['remind']}"
            if kind and item["kind"] != kind:
                return f"kind {item['kind']}, want {kind}"
        return None

    return check


def nothing_open(status: str) -> Check:
    def check(state: State) -> str | None:
        if state.open:
            return f"still open: {len(state.open)}"
        if [item["status"] for item in state.items] != [status]:
            return f"statuses {[item['status'] for item in state.items]}, want [{status}]"
        return None

    return check


def asks_instead_of_guessing(state: State) -> str | None:
    if any(item["at"] for item in state.open):
        return "guessed a time"
    return None if "?" in state.answers[-1] else "no question"


def tells_the_plan(state: State) -> str | None:
    said = state.answers[-1].lower()
    if "стоматолог" not in said or "9" not in said:
        return "the plan is not in the answer"
    return None if len(state.items) == 1 else f"items: {len(state.items)}, want 1"


@dataclass(frozen=True)
class Scenario:
    name: str
    turns: tuple[str, ...]
    check: Check


BANK = "напомни через 20 минут позвонить в банк"
DENTIST = "напомни завтра в 9 утра про стоматолога"
SCENARIOS = [
    Scenario("in20", (BANK,), reminders(datetime(2026, 10, 12, 12, 20))),
    Scenario("tomorrow9", (DENTIST,), reminders(datetime(2026, 10, 13, 9, 0))),
    Scenario(
        "friday_hour_before", ("в пятницу в 15:00 встреча с Олегом, напомни за час",),
        reminders(datetime(2026, 10, 16, 15, 0), lead=HOUR_BEFORE),
    ),
    Scenario(
        "two_in_one", ("напомни в 18:00 забрать посылку и в 19:30 позвонить Ане",),
        reminders(datetime(2026, 10, 12, 18, 0), datetime(2026, 10, 12, 19, 30)),
    ),
    Scenario("unclear", ("напомни позвонить маме",), asks_instead_of_guessing),
    Scenario("move", (BANK, "перенеси на час позже"), reminders(datetime(2026, 10, 12, 13, 20))),
    Scenario("cancel", (BANK, "отмени"), nothing_open("cancelled")),
    Scenario("done", (BANK, "позвонил, готово"), nothing_open("done")),
    Scenario("question", (DENTIST, "что у меня на завтра?"), tells_the_plan),
    # Те же умения другими словами: по ним видно, что правка подсказок учит правилу, а не фразе.
    Scenario("in30_oven", ("напомни через полчаса выключить духовку",), reminders(datetime(2026, 10, 12, 12, 30))),
    Scenario("in2h_write", ("через два часа напомни написать Кате",), reminders(datetime(2026, 10, 12, 14, 0))),
    Scenario("done_report", ("напомни в 16:00 отправить отчёт Марине", "отправил"), nothing_open("done")),
    Scenario(
        "concert", ("в четверг в 19:00 концерт, напомни за два часа",),
        reminders(datetime(2026, 10, 15, 19, 0), lead={"PT2H", "PT120M"}, kind="event"),
    ),
]


async def _turn(talker: assistant.Assistant, db, text: str) -> dict:
    async with db.write() as session:
        fact = (await facts.add(session, client="telegram", text=text)).id
    before = len(talker.history)
    started = time.monotonic()
    answer = await talker.reply(text, fact)
    spent = time.monotonic() - started
    fresh = talker.history[before:]
    responses = [message for message in fresh if isinstance(message, ModelResponse)]
    return {
        "trace": [_brief(part) for message in fresh for part in message.parts if _brief(part)],
        "seconds": round(spent, 2),
        "requests": len(responses),
        "input": sum(r.usage.input_tokens for r in responses),
        "cache_read": sum(r.usage.cache_read_tokens for r in responses),
        "cache_write": sum(r.usage.cache_write_tokens for r in responses),
        "output": sum(r.usage.output_tokens for r in responses),
        "models": sorted({r.model_name or "" for r in responses}),
        "answer": answer,
    }


def _brief(part) -> str:
    """Вызов инструмента и ответ на него одной строкой: по ним видно, почему разговор кончился не тем."""
    kind = type(part).__name__
    if kind == "ToolCallPart":
        return f"CALL {part.tool_name} {str(part.args)[:500]}"
    if kind in ("ToolReturnPart", "RetryPromptPart"):
        return f"{kind[:-4].upper()} {str(part.content)[:300]}"
    return ""


async def _state(db, answers: list[str]) -> State:
    async with db.read() as session:
        rows = (await session.scalars(select(Item).order_by(Item.id))).all()
        left = await facts.inbox(session)
    items = [
        {"kind": row.kind, "title": row.title, "at": row.at, "remind": row.remind, "status": row.status}
        for row in rows
    ]
    return State(items=items, inbox=len(left), answers=answers)


def _record(row: dict) -> None:
    with OUT.open("a") as out:
        out.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")


@pytest.mark.parametrize("rep", range(REPS))
@pytest.mark.parametrize("scenario", SCENARIOS, ids=lambda scenario: scenario.name)
async def test_bench(app, db, pg_url, monkeypatch, scenario: Scenario, rep: int):
    monkeypatch.setattr(assistant, "THINKING", THINKING)
    settings = Settings(_env_file=None, database_url=pg_url, owner_tz="Europe/Berlin", assistant_model=CHAIN, **KEYS)
    talker = assistant.build(settings, app.state.mcp, guide=app.state.ctx.schema.guide)
    row: dict = {"chain": CHAIN, "thinking": THINKING, "scenario": scenario.name, "rep": rep, "turns": []}
    try:
        for text in scenario.turns:
            row["turns"].append(await _turn(talker, db, text))
        state = await _state(db, [turn["answer"] for turn in row["turns"]])
        reason = scenario.check(state)
        row |= {"ok": reason is None, "reason": reason, "items": state.items, "inbox": state.inbox}
    except Exception as error:  # noqa: BLE001 — замер записывает любой сбой модели, а не падает на нём
        row |= {"ok": False, "reason": "error", "error": f"{type(error).__name__}: {str(error)[:300]}"}
    _record(row)
