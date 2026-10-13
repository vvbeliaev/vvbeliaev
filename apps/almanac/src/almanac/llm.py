"""Модель собеседника: чья она и какая — решает настройка, а не код.

Своей абстракции здесь нет: общий язык провайдеров — `Model` из pydantic-ai. Модуль читает цепочку из
`ASSISTANT_MODEL` и собирает по ней модель. Что провайдеру сказать о глубине размышления и о кэше
постоянной части промпта, знает его строитель ниже: слова у каждого свои.
"""

import logging
import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal, get_args

if TYPE_CHECKING:
    from pydantic_ai.models import Model

log = logging.getLogger("almanac.llm")
# Глубина размышления: эти три ступени понимают оба провайдера.
Depth = Literal["low", "medium", "high"]
DEPTHS = get_args(Depth)
# Имя модели — как у провайдера, без пробелов; провайдер — одно слово. Глубина — по желанию, после `@`.
LINK = re.compile(r"([a-z]+):([^\s@]+)(?:@([a-z]+))?")


@dataclass(frozen=True)
class Route:
    """Звено цепочки: провайдер, имя модели у него и своя глубина размышления, если она названа."""

    provider: str
    model: str
    thinking: Depth | None = None

    def __str__(self) -> str:
        depth = f"@{self.thinking}" if self.thinking else ""
        return f"{self.provider}:{self.model}{depth}"


# Библиотека моделей подключается внутри функций: цепочку проверяют настройки, а их читают и миграции,
# которым модель ни к чему.
def _anthropic(name: str, key: str, thinking: Depth) -> "Model":
    """Claude кэширует только то, что помечено: `cache` ставит отметки после постоянной части инструкций,
    после схем инструментов и на хвост разговора. Без них каждый запрос платил бы за весь промпт заново."""
    from pydantic_ai.models.anthropic import AnthropicModel
    from pydantic_ai.providers.anthropic import AnthropicProvider
    from pydantic_ai.settings import ModelSettings

    settings = ModelSettings(thinking=thinking, cache=True)
    return AnthropicModel(name, provider=AnthropicProvider(api_key=key), settings=settings)


def _google(name: str, key: str, thinking: Depth) -> "Model":
    """Нативный адрес Google: он полнее держит многошаговые вызовы инструментов, чем совместимый с OpenAI.

    Глубина — своим параметром Google, а не общим `thinking`: общий заодно просит пересказ мыслей в каждом
    ответе, а он ложится в историю и владельцу не нужен. Кэш у Gemini неявный, просить его не надо.
    """
    from pydantic_ai.models.google import GoogleModel, GoogleModelSettings
    from pydantic_ai.providers.google import GoogleProvider

    settings = GoogleModelSettings(google_thinking_config={"thinking_level": thinking})
    return GoogleModel(name, provider=GoogleProvider(api_key=key), settings=settings)


PROVIDERS: dict[str, Callable[[str, str, Depth], "Model"]] = {"anthropic": _anthropic, "google": _google}


def routes(spec: str) -> tuple[Route, ...]:
    """Цепочка из настройки: `провайдер:модель` через запятую, первая — основная.

    Глубину размышления звено называет само: `провайдер:модель@medium`. Она подбирается под модель замером,
    поэтому и живёт рядом с её именем.
    """
    found = []
    for link in spec.split(","):
        match = LINK.fullmatch(link.strip())
        if match is None:
            raise ValueError(f"a model is written as provider:name or provider:name@depth, got {link.strip()!r}")
        provider, name, depth = match.groups()
        if provider not in PROVIDERS:
            raise ValueError(f"unknown provider {provider!r}, known: {', '.join(PROVIDERS)}")
        if depth is not None and depth not in DEPTHS:
            raise ValueError(f"unknown depth {depth!r}, known: {', '.join(DEPTHS)}")
        found.append(Route(provider, name, depth))
    return tuple(found)


def model(chain: Sequence[Route], keys: Mapping[str, str], *, thinking: Depth) -> "Model | None":
    """Модель по цепочке: одно звено — оно само, несколько — откат по порядку, когда API отказал.

    `thinking` — глубина для звеньев, которые свою не назвали.

    Ни одного ключа вообще — модели нет, и это не сбой: собеседник не настроен. Но когда ключи есть, каждое
    звено, выпавшее без своего, названо в журнале: иначе о сменившейся или молчащей модели владелец узнал бы
    из счёта или из тишины в чате.
    """
    from pydantic_ai.models.fallback import FallbackModel

    if not any(keys.values()):
        return None
    for route in chain:
        if not keys.get(route.provider):
            log.warning("no key for %s: the link is left out of the chain", route)
    links = [
        PROVIDERS[route.provider](route.model, keys[route.provider], route.thinking or thinking)
        for route in chain if keys.get(route.provider)
    ]
    if not links:
        log.warning("no link of the chain has a key: the assistant is off")
        return None
    return links[0] if len(links) == 1 else FallbackModel(*links)
