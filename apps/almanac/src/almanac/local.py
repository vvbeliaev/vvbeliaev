"""Локальная дверь MCP: тот же сервер по stdio, без OAuth.

    uv run --directory <путь к apps/almanac> python -m almanac.local

Для Claude Code и других клиентов на этой же машине. Сервер тот же, что за HTTP: Code Mode,
строгие аргументы, те же ручки и те же отказы. Входа нет, потому что нет и сети: процесс
запускает сам владелец, а кто может его запустить, тот и так читает базу. В журнале такие
вызовы подписаны клиентом `local`.

Нужна только база из настроек (`Settings()` читает окружение и `.env` рабочего каталога);
HTTP-сервер может идти рядом, может стоять. Бот и цикл напоминаний здесь не запускаются —
это дело сервера: второй опрос того же бота Telegram отвергнет, а напоминания ушли бы
дважды. В stdout идёт только протокол; журнал — в stderr.
"""

import asyncio

from almanac.app import create_app
from almanac.config import Settings
from almanac.identity import acting

CLIENT = "local"


async def serve(settings: Settings | None = None) -> None:
    settings = (settings or Settings()).model_copy(update={"telegram_bot_token": ""})
    app = create_app(settings)
    # Lifespan открывает базу, как в бою.
    async with app.router.lifespan_context(app):
        acting.set(CLIENT)
        await app.state.mcp.run_stdio_async(show_banner=False)


if __name__ == "__main__":
    asyncio.run(serve())
