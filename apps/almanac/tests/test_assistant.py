"""Собеседник в Telegram: агент на нашем MCP. Модель в тестах подставная и говорит по сценарию."""

import re
from datetime import UTC, datetime

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
from sqlalchemy import select

from almanac import assistant, clock
from almanac.config import Settings
from almanac.identity import acting
from almanac.models import Item, ItemFact, Journal
from almanac.store import facts

TZ = "Europe/Berlin"


class Script:
    """Подставная модель: на первый запрос хода зовёт `execute` с кодом, получив вывод — отвечает текстом.
    Запоминает, что ей показали: инструкции и сколько сообщений было в истории."""

    def __init__(self, code: str = "", answer: str = "Готово.") -> None:
        self.code, self.answer = code, answer
        self.instructions: list[str] = []
        self.histories: list[int] = []
        self.prompts: list[str] = []
        self.tools: set[str] = set()

    def __call__(self, messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        last = messages[-1]
        self.tools = {tool.name for tool in info.function_tools}
        answered = isinstance(last, ModelRequest) and any(isinstance(part, ToolReturnPart) for part in last.parts)
        if answered or not self.code:
            return ModelResponse(parts=[TextPart(self.answer)])
        self.instructions.append(info.instructions or "")
        self.histories.append(len(messages))
        prompt = "".join(str(part.content) for part in last.parts if hasattr(part, "content"))
        self.prompts.append(prompt)
        fact = re.search(r"f_[a-z0-9]+", prompt).group(0)
        return ModelResponse(parts=[ToolCallPart("execute", {"code": self.code.replace("FACT", fact)})])


def _talker(app, script: Script) -> assistant.Assistant:
    return assistant.Assistant(
        assistant.agent_over(FunctionModel(script), app.state.mcp),
        guide=app.state.ctx.schema.guide, owner_tz=TZ, day_start="09:00", quiet_hours="23:00-08:00",
        mcp=app.state.mcp,
    )


async def _said(db, text: str) -> str:
    """Слова владельца, как их записывает бот до вызова собеседника."""
    async with db.write() as session:
        return (await facts.add(session, client="telegram", text=text)).id


REMIND = (
    "return await call_tool('item_add', {'kind': 'task', 'title': 'Позвонить в банк', 'in': 'PT20M', "
    "'remind': ['PT0M'], 'facts': ['FACT'], 'reason': 'reminder'})"
)


async def test_it_builds_a_reminder_from_the_recorded_words(app, db, now):
    script = Script(REMIND, "Напомню в 12:20: позвонить в банк.")
    fact = await _said(db, "напомни через 20 минут позвонить в банк")
    answer = await _talker(app, script).reply("напомни через 20 минут позвонить в банк", fact)

    assert answer == "Напомню в 12:20: позвонить в банк."
    async with db.read() as session:
        item = (await session.scalars(select(Item))).one()
        linked = (await session.scalars(select(ItemFact.fact_id).where(ItemFact.item_id == item.id))).all()
        added = (await session.scalars(select(Journal).where(Journal.op == "item_add"))).one()
        inbox = await facts.inbox(session)
    assert (item.title, item.at, item.remind) == ("Позвонить в банк", datetime(2026, 10, 12, 12, 20), ["PT0M"])
    # Источник — те самые слова, второй раз они не записаны; пишет не «telegram», а собеседник.
    assert linked == [fact]
    assert added.client == "agent"
    assert inbox == []


async def test_it_works_through_the_same_door_as_any_client(app, db, now):
    script = Script(REMIND)
    await _talker(app, script).reply("напомни", await _said(db, "напомни"))
    assert script.tools == {"search", "get_schema", "execute"}


async def test_it_is_told_the_rules_and_the_time(app, db, now):
    script = Script(REMIND)
    await _talker(app, script).reply("напомни", await _said(db, "напомни"))
    told = script.instructions[0]
    assert "Three kinds of data" in told  # руководство уже в инструкциях: ход на `guide` не нужен
    # И схема каждой операции со смыслом полей: ходы на `search` и `get_schema` тоже не нужны.
    assert all(f"### {name}" in told for name in ("item_add", "item_update", "dismiss", "write", "move", "grep"))
    assert "this far from now" in told
    assert "now: 2026-10-12T12:00 Europe/Berlin, Monday" in told
    assert "day_start 09:00" in told and "quiet 23:00-08:00" in told
    # Слова владельца приходят с номером факта, под которым записаны.
    assert re.fullmatch(r"напомни\n\n\[recorded as fact f_[a-z0-9]+\]", script.prompts[0])


async def test_a_conversation_is_remembered_while_it_lasts(app, db, now, monkeypatch):
    script = Script(REMIND)
    talker = _talker(app, script)
    await talker.reply("напомни про банк", await _said(db, "напомни про банк"))
    await talker.reply("а теперь про врача", await _said(db, "а теперь про врача"))
    assert script.histories[0] == 1
    assert script.histories[1] > script.histories[0]  # второй ход видит первый

    # Полчаса тишины — разговор окончен: следующее сообщение начинает с чистого листа.
    later = datetime(2026, 10, 12, 10, 45, tzinfo=UTC)
    monkeypatch.setattr(clock, "_now", lambda: later)
    await talker.reply("купить хлеб", await _said(db, "купить хлеб"))
    assert script.histories[2] == 1


async def test_a_long_conversation_keeps_only_its_last_turns(app, db, now):
    script = Script(REMIND)
    talker = _talker(app, script)
    for number in range(assistant.MAX_TURNS + 3):
        await talker.reply(f"дело {number}", await _said(db, f"дело {number}"))
    turns = [m for m in talker.history if isinstance(m, ModelRequest) and assistant.asks(m)]
    assert len(turns) == assistant.MAX_TURNS


async def test_old_tool_output_is_dropped_from_the_history(app, db, now):
    script = Script(REMIND)
    talker = _talker(app, script)
    for number in range(4):
        await talker.reply(f"дело {number}", await _said(db, f"дело {number}"))
    shown = assistant.compact(talker.history)
    returns = [part.content for m in shown if isinstance(m, ModelRequest) for part in m.parts
               if isinstance(part, ToolReturnPart)]
    assert [str(content).startswith("[output omitted") for content in returns] == [True, True, False, False]


async def test_the_caller_identity_does_not_leak_out_of_a_reply(app, db, now):
    await _talker(app, Script(REMIND)).reply("напомни", await _said(db, "напомни"))
    assert acting.get() is None


def test_without_a_key_there_is_no_assistant(pg_url):
    settings = Settings(_env_file=None, database_url=pg_url)
    assert settings.llm_api_key == ""
    assert assistant.build(settings, mcp=None, guide="") is None


def test_the_key_is_not_shown_when_settings_are_printed():
    key = "AIza" + "x" * 20
    assert key not in repr(Settings(_env_file=None, llm_api_key=key))


@pytest.mark.parametrize("model", ["", " "])
def test_an_empty_model_name_is_refused(model):
    from pydantic import ValidationError

    with pytest.raises(ValidationError, match="ASSISTANT_MODEL"):
        Settings(_env_file=None, assistant_model=model)
