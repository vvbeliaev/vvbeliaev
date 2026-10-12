"""Собеседник в Telegram: агент на нашем же MCP.

Ядро остаётся без модели: хранение, проверки и время — код. Собеседник — ещё один клиент той же двери,
что у Claude: те же мета-инструменты, те же отказы, то же руководство. Нет ключа модели — нет
собеседника, и бот только записывает, как раньше.

Наружу у него один канал — ответ владельцу в его же чат. Чужой текст в базе может подсказать ему
глупость, но унести записи ему некуда; а всё, что он пишет, помечено в журнале его именем.
"""

import json
from dataclasses import replace
from datetime import datetime, timedelta
from typing import Any

from fastmcp import Client, FastMCP
from pydantic_ai import Agent
from pydantic_ai.capabilities import ProcessHistory
from pydantic_ai.mcp import MCPToolset
from pydantic_ai.messages import ModelMessage, ModelRequest, ToolReturnPart, UserPromptPart
from pydantic_ai.models import Model
from pydantic_ai.models.google import GoogleModel, GoogleModelSettings
from pydantic_ai.providers.google import GoogleProvider
from pydantic_ai.usage import UsageLimits

from almanac import api, tree
from almanac.clock import utcnow
from almanac.config import Settings
from almanac.identity import acting

# Имя в журнале и в заголовке факта. Слова владельца бот пишет как `telegram`, а построенное из них — он.
CLIENT = "agent"
# Зациклившийся агент останавливается сам: обычный ход — схема, один-два `execute` и ответ.
REQUEST_LIMIT = 12
# Разговор живёт, пока идёт: после тишины «перенеси на час» относилось бы неизвестно к чему.
IDLE_RESET = timedelta(minutes=30)
# Столько последних ходов остаются с выводами инструментов; в остальных вывод заменён меткой.
KEEP_TURNS = 2
# Больше ходов история не держит: она живёт в памяти процесса и уходит модели целиком.
MAX_TURNS = 12
# Отказ сервера — подсказка, а не провал: модель читает его и зовёт снова. Столько раз подряд.
TOOL_RETRIES = 3
# Думать долго тут не над чем: разобрать фразу и собрать один вызов. Владелец ждёт у телефона.
THINKING = "low"

INSTRUCTIONS = """You are almanac in the owner's Telegram: their notebook and their reminders. The owner writes short messages from a phone, often in a hurry.

Reply in the owner's language, in one to three short lines of plain text: no Markdown, no lists of what you could do. Say exactly what you did — what was saved, and the date and time of a reminder as the owner would say it. Never claim what you did not do: when a call is refused and you cannot fix it, say what is not done.

Every message is already recorded as a fact before you see it; its id comes at the end of the message. Build tasks, events and pages from that fact: pass `facts: [id]`, never `said`, and never call `note` for the same words. When the message is a question, or a command that leaves nothing to keep, answer it and close its fact with `dismiss`.

"Remind me" is an item with `remind`; "in twenty minutes" is `in`. When the day or the time is unclear, ask one short question instead of guessing. To undo what you just did, set the item's status to `cancelled`. `item_update` takes no `facts`: after you change or cancel an item on the owner's word, close the message's fact with `dismiss`.

You work through `execute`: Python that calls almanac's tools. The owner is waiting at the phone, so be quick: do the whole job in one `execute` — the writes and the `dismiss` together — and answer. The answer of a call is the confirmation: do not read the inbox or a view to check your own work. Look for an item only when you must change it, and `grep` only before you create a page or when the owner asks about something stored.

The rules and the formats are in the guide below, and after it the schema of every tool: you already have both, so do not call `guide`, `search` or `get_schema`. The current time is at the end of these instructions."""


def asks(message: ModelMessage) -> bool:
    """Начало хода: сообщение владельца."""
    return isinstance(message, ModelRequest) and any(isinstance(part, UserPromptPart) for part in message.parts)


def compact(messages: list[ModelMessage]) -> list[ModelMessage]:
    """История перед обращением к модели: в старых ходах вывод инструментов заменён меткой с его размером.

    Модели нужен итог прошлых ходов, а не их сырьё. Код вызова остаётся: по нему видно, что делалось.
    """
    starts = [index for index, message in enumerate(messages) if asks(message)]
    if len(starts) <= KEEP_TURNS:
        return messages
    boundary = starts[-KEEP_TURNS]
    return [_shrink(message) for message in messages[:boundary]] + messages[boundary:]


def _shrink(message: ModelMessage) -> ModelMessage:
    if not isinstance(message, ModelRequest):
        return message
    if not any(isinstance(part, ToolReturnPart) for part in message.parts):
        return message
    return replace(message, parts=[_omit(part) if isinstance(part, ToolReturnPart) else part for part in message.parts])


def _omit(part: ToolReturnPart) -> ToolReturnPart:
    return replace(part, content=f"[output omitted: {_size(part.content)} chars]")


def _size(content: Any) -> int:
    if isinstance(content, str):
        return len(content)
    return len(json.dumps(content, ensure_ascii=False, default=str))


def _last_turns(messages: list[ModelMessage], turns: int) -> list[ModelMessage]:
    """Последние `turns` ходов целиком: резать можно только по началу хода, иначе вызов останется без вывода."""
    starts = [index for index, message in enumerate(messages) if asks(message)]
    return messages if len(starts) <= turns else messages[starts[-turns]:]


def agent_over(model: Model, mcp: FastMCP) -> Agent[None, str]:
    """Агент на нашем MCP в памяти процесса: те же инструменты, тот же журнал."""
    toolset = MCPToolset(mcp, max_retries=TOOL_RETRIES)
    return Agent(model, toolsets=[toolset], capabilities=[ProcessHistory(compact)])


async def schemas(mcp: FastMCP) -> str:
    """Схемы всех операций одним текстом — тем же, что отдаёт `get_schema`.

    В инструкциях они экономят владельцу секунды: без них каждый ход начинался бы с поиска и схемы.
    Без Code Mode инструмента `get_schema` нет, а схемы приходят с самими инструментами: тогда пусто.
    """
    async with Client(mcp) as client:
        if "get_schema" not in {tool.name for tool in await client.list_tools()}:
            return ""
        found = await client.call_tool("get_schema", {"tools": api.operations()})
    return found.content[0].text


class Assistant:
    """Собеседник одного владельца: агент, его инструкции и память разговора.

    Память — в процессе: сервер один и воркер один, а разговор, пропавший при перезапуске, не потеря.
    """

    def __init__(
        self, agent: Agent[None, str], *, guide: str, owner_tz: str, day_start: str, quiet_hours: str,
        mcp: FastMCP | None = None,
    ) -> None:
        self.agent = agent
        self.limits = UsageLimits(request_limit=REQUEST_LIMIT)
        self.owner_tz, self.day_start, self.quiet_hours = owner_tz, day_start, quiet_hours
        # Постоянная часть инструкций: своё и руководство. Время — в хвосте: постоянная часть кэшируется.
        self._constant = f"{INSTRUCTIONS}\n\n{guide}"
        # Схемы инструментов дописываются к постоянной части при первом ответе: взять их можно только из цикла.
        self._mcp = mcp
        self.history: list[ModelMessage] = []
        self._last: datetime | None = None

    def instructions(self) -> str:
        moment = tree.local_now(self.owner_tz)
        quiet = self.quiet_hours or "none"
        clock = f"now: {moment:%Y-%m-%dT%H:%M} {self.owner_tz}, {moment:%A}; day_start {self.day_start}; quiet {quiet}"
        return f"{self._constant}\n\n{clock}"

    async def reply(self, text: str, fact_id: str) -> str:
        """Ответ на слова владельца, уже записанные фактом `fact_id`."""
        now = utcnow()
        if self._last is None or now - self._last > IDLE_RESET:
            self.history = []
        if self._mcp is not None:
            tools, self._mcp = await schemas(self._mcp), None
            if tools:
                self._constant = f"{self._constant}\n\n# Tools\n\n{tools}"
        # Вызовы инструментов идут под именем собеседника; за пределы ответа имя не выходит.
        token = acting.set(CLIENT)
        try:
            result = await self.agent.run(
                f"{text}\n\n[recorded as fact {fact_id}]", instructions=self.instructions(),
                message_history=self.history, usage_limits=self.limits,
            )
        finally:
            acting.reset(token)
        self.history = _last_turns(result.all_messages(), MAX_TURNS)
        self._last = now
        return result.output.strip()


def build(settings: Settings, mcp: FastMCP, guide: str) -> Assistant | None:
    """Собеседник по настройкам; без ключа модели его нет. Модель — нативная Google: она полнее держит
    многошаговые вызовы инструментов, чем совместимый с OpenAI адрес."""
    if not settings.llm_api_key:
        return None
    model = GoogleModel(
        settings.assistant_model, provider=GoogleProvider(api_key=settings.llm_api_key),
        settings=GoogleModelSettings(google_thinking_config={"thinking_level": THINKING}),
    )
    return Assistant(
        agent_over(model, mcp), guide=guide, owner_tz=settings.owner_tz, day_start=settings.day_start,
        quiet_hours=settings.quiet_hours, mcp=mcp,
    )
