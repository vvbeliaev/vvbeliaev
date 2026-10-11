import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from almanac import api, mcp, schema, tree, web
from almanac.auth import owner
from almanac.auth.oauth import AlmanacOAuthProvider
from almanac.config import Settings
from almanac.db import Database
from almanac.errors import Refused
from almanac.telegram import Telegram
from almanac.timeline.scheduler import Scheduler

# `form-action` намеренно нет: браузер применяет его и к редиректу после формы согласия,
# а он ведёт на адрес клиента OAuth.
FIXED_HEADERS = {
    "X-Frame-Options": "DENY",
    "Content-Security-Policy": "frame-ancestors 'none'",
    "Referrer-Policy": "no-referrer",
}


class SecureHeaders:
    """Заголовки на каждый ответ: нельзя вставить в чужой фрейм, нельзя закэшировать.

    Чистый ASGI, а не `BaseHTTPMiddleware`: тот буферизует потоковые ответы, а MCP стримит.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def send_with_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                for name, value in FIXED_HEADERS.items():
                    headers[name] = value
                if "cache-control" not in headers:
                    headers["Cache-Control"] = "no-store"
            await send(message)

        await self.app(scope, receive, send_with_headers)


class Almanac(FastAPI):
    """FastAPI, у которого `SecureHeaders` стоит снаружи всех слоёв.

    `add_middleware` встал бы внутрь `ServerErrorMiddleware`, и ответ 500 уходил бы без заголовков.
    """

    def build_middleware_stack(self) -> ASGIApp:
        return SecureHeaders(super().build_middleware_stack())


def create_app(settings: Settings | None = None, db: Database | None = None) -> FastAPI:
    """Собирает приложение. `db` передают тесты: тогда базу здесь не создаём и не закрываем."""
    settings = settings or Settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if db is None:
            app.state.db = Database(settings.database_url)
            await app.state.db.create_all()
        background: list[asyncio.Task] = []
        try:
            # Без токена и чата бот и цикл не запускаются: срабатывания копятся в базе.
            if db is None and settings.telegram_bot_token and settings.telegram_owner_chat_id:
                scheduler = Scheduler(
                    app.state.db, Telegram(settings.telegram_bot_token, settings.telegram_owner_chat_id),
                    owner_tz=settings.owner_tz, day_start=settings.day_start,
                    owner_chat_id=settings.telegram_owner_chat_id,
                )
                background = [asyncio.create_task(scheduler.run()), asyncio.create_task(scheduler.poll())]
            async with app.state.mcp_app.lifespan(app):
                yield
        finally:
            for task in background:
                task.cancel()
            # Дожидаемся отмены, пока база ещё открыта: цикл мог быть посреди записи.
            await asyncio.gather(*background, return_exceptions=True)
            if db is None:
                await app.state.db.dispose()

    app = Almanac(title="almanac", lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
    app.state.settings = settings
    app.state.ctx = tree.Context(
        schema=schema.load(settings.schema_dir), owner_tz=settings.owner_tz, day_start=settings.day_start
    )
    if db is not None:
        app.state.db = db
    app.include_router(api.router, prefix="/api")
    app.state.attempts = owner.Attempts()
    app.include_router(web.router)
    app.state.oauth = AlmanacOAuthProvider(base_url=f"{settings.base_url}/mcp", db=lambda: app.state.db)
    # Сервер собирается после всех роутеров и до монтирования самого себя.
    server = mcp.build(
        app, auth=app.state.oauth, code_mode=settings.mcp_code_mode, client_name=app.state.oauth.client_name
    )
    app.state.mcp = server
    app.state.mcp_app = server.http_app(path="/")
    app.mount("/mcp", app.state.mcp_app)
    app.router.routes.extend(app.state.oauth.get_well_known_routes(mcp_path="/"))

    @app.get("/healthz", include_in_schema=False)
    async def healthz() -> dict:
        return {"ok": True}

    @app.exception_handler(Refused)
    async def refused(_request: Request, error: Refused) -> JSONResponse:
        return JSONResponse({"detail": str(error)}, status_code=error.status)

    return app
