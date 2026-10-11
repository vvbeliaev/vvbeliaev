import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from almanac import api, mcp, schema, tree, web
from almanac.auth import owner
from almanac.auth.oauth import AlmanacOAuthProvider
from almanac.config import Settings
from almanac.db import Database
from almanac.errors import Refused
from almanac.telegram import Telegram
from almanac.timeline.scheduler import Scheduler


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

    app = FastAPI(title="almanac", lifespan=lifespan)
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
