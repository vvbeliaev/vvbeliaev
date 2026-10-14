"""Адаптер almanac для бенча без сети: файл сценариев, миры, проверки и весь путь разговора на подставной модели."""

import re

import pytest
from pydantic_ai.messages import (
    ModelMessage,
    ModelRequest,
    ModelResponse,
    TextPart,
    ToolCallPart,
    ToolReturnPart,
)
from pydantic_ai.models.function import AgentInfo, FunctionModel

from almanac import assistant
from evals import adapter
from evals.core import judge, load, outcome

SCENARIOS = {scenario.id: scenario for scenario in load(adapter.SCENARIOS, adapter.checks, adapter.WORLDS)}


def test_the_scenario_file_loads_and_covers_both_splits():
    assert {scenario.split for scenario in SCENARIOS.values()} == {"tune", "holdout"}
    assert {scenario.world for scenario in SCENARIOS.values()} == set(adapter.WORLDS)


@pytest.mark.parametrize("world", sorted(adapter.WORLDS))
async def test_every_world_seeds(app, db, now, world):
    await adapter.WORLDS[world](db, app.state.ctx.schema.types)
    state = await adapter.snapshot(db)
    assert set(state) == {"items", "pages", "facts"}
    if world == "year":
        titles = [item["title"] for item in state["items"].values()]
        assert len(titles) > 800 and titles.count("Встреча с Олегом") >= 2
        assert sum(1 for fact in state["facts"].values() if fact["dismissed"]) >= 1000


class Script:
    """Подставная модель: на первый запрос хода зовёт `execute` с кодом, получив вывод — отвечает."""

    def __init__(self, code: str, answer: str) -> None:
        self.code, self.answer = code, answer

    def __call__(self, messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        last = messages[-1]
        if isinstance(last, ModelRequest) and any(isinstance(part, ToolReturnPart) for part in last.parts):
            return ModelResponse(parts=[TextPart(self.answer)])
        prompt = "".join(str(part.content) for part in last.parts if hasattr(part, "content"))
        fact = re.search(r"recorded as fact (f_[a-z0-9]+)", prompt).group(1)
        return ModelResponse(parts=[ToolCallPart("execute", {"code": self.code.replace("FACT", fact)})])


def _talker(app, script: Script) -> assistant.Assistant:
    return assistant.Assistant(
        assistant.agent_over(FunctionModel(script), app.state.mcp), guide=app.state.ctx.schema.guide,
        owner_tz=adapter.TZ, day_start="09:00", quiet_hours="23:00-08:00", mcp=app.state.mcp,
    )


def _remind_in(minutes: int) -> str:
    return (
        f"return await call_tool('item_add', {{'kind': 'task', 'title': 'Позвонить в банк', 'in': 'PT{minutes}M', "
        "'remind': ['PT0M'], 'facts': ['FACT'], 'reason': 'reminder'})"
    )


@pytest.mark.parametrize(("minutes", "reasons"), [(20, []), (30, ["reminders: at ['2026-10-12T12:30'], want"])])
async def test_a_conversation_goes_from_world_to_verdict(app, db, now, minutes, reasons):
    scenario = SCENARIOS["in20"]
    await adapter.WORLDS[scenario.world](db, app.state.ctx.schema.types)
    turns, result = await adapter.converse(_talker(app, Script(_remind_in(minutes), "Напомню.")), db, scenario)
    found = judge(scenario, adapter.checks, result)
    assert [reason[: len(want)] for reason, want in zip(found, reasons, strict=True)] == reasons
    assert turns[0]["answer"] == "Напомню." and turns[0]["requests"] == 2
    assert turns[0]["trace"][0].startswith("CALL execute")


async def test_the_prompt_surface_holds_instructions_guide_and_schemas(app):
    surface = await adapter.prompt_surface(app.state.mcp, app.state.ctx.schema.guide)
    assert surface.startswith(assistant.INSTRUCTIONS) and "# almanac guide" in surface and "### item_add" in surface


def _items(**records) -> dict:
    return {"items": records, "pages": {}, "facts": {}}


def _event(title: str, at: str, status: str = "open") -> dict:
    return {"kind": "event", "title": title, "status": status, "at": at, "remind": ["PT1H"]}


def test_moved_and_set_status_find_the_one_item():
    before = _items(a=_event("Созвон с Петей", "2026-10-15T11:00"), b=_event("Созвон с Петровым", "2026-10-15T14:00"))
    right = _items(a=_event("Созвон с Петей", "2026-10-15T16:00"), b=before["items"]["b"])
    wrong = _items(a=before["items"]["a"], b=_event("Созвон с Петровым", "2026-10-15T16:00"))
    assert adapter.checks["moved"](outcome(before, right, ("ок",)), title="Созвон с Петей", at="2026-10-15T16:00") is None
    assert adapter.checks["moved"](outcome(before, wrong, ("ок",)), title="Созвон с Петей", at="2026-10-15T16:00") == (
        "changed 'Созвон с Петровым', want 'Созвон с Петей'"
    )
    cancelled = _items(a=_event("Созвон с Петей", "2026-10-15T11:00", "cancelled"), b=before["items"]["b"])
    check = adapter.checks["set_status"]
    assert check(outcome(before, cancelled, ("ок",)), title="Петей", status="cancelled", at="2026-10-15T11:00") is None
    assert check(outcome(before, cancelled, ("ок",)), title="Петей", status="cancelled", at="2026-10-19T18:00") == (
        "changed the one at 2026-10-15T11:00, want the one at 2026-10-19T18:00"
    )


def test_case_added_wants_a_dated_line_on_that_page_only():
    page = "pages/principles/x.md"
    before = {"items": {}, "facts": {}, "pages": {page: {"body": "## Случаи\n\n- 2026-09 — старое\n"}}}
    after = {"items": {}, "facts": {}, "pages": {page: {"body": "## Случаи\n\n- 2026-09 — старое\n- 2026-10 — almanac\n"}}}
    check = adapter.checks["case_added"]
    assert check(outcome(before, after, ("ок",)), page=page, month="2026-10", words=["Almanac"]) is None
    assert check(outcome(before, before, ("ок",)), page=page, month="2026-10", words=["almanac"]) == f"{page} unchanged"
    undated = {"items": {}, "facts": {}, "pages": {page: {"body": before["pages"][page]["body"] + "almanac\n"}}}
    assert check(outcome(before, undated, ("ок",)), page=page, month="2026-10", words=["almanac"]) == (
        "no new line starting with '- 2026-10'"
    )
