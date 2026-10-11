"""Страницы, отрисованные сервером: вход и согласие OAuth. Остальное — API."""

from html import escape
from typing import Annotated
from urllib.parse import urlsplit

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response

from almanac.auth import owner

router = APIRouter(include_in_schema=False)

# Токены — из корневого DESIGN.md. Здесь они только отображены в CSS.
STYLE = """
:root { --bg: #04050b; --surface: #0a0c14; --text: #e3e5ee; --muted: #7d8294; --accent: #f08a72; }
* { box-sizing: border-box; }
body { margin: 0; min-height: 100vh; display: grid; place-items: center; padding: 16px;
       background: var(--bg); color: var(--text); font: 16px/1.5 system-ui, sans-serif; }
main { width: 100%; max-width: 360px; padding: 24px; background: var(--surface); border-radius: 12px; }
h1 { margin: 0 0 16px; font-size: 20px; }
p { margin: 0 0 16px; color: var(--muted); }
input, button { width: 100%; padding: 10px 12px; font: inherit; border-radius: 8px; }
input { margin-bottom: 12px; background: var(--bg); color: var(--text); border: 1px solid var(--muted); }
button { border: 0; background: var(--accent); color: var(--bg); cursor: pointer; }
button.quiet { margin-top: 8px; background: transparent; color: var(--muted); border: 1px solid var(--muted); }
.error { color: var(--accent); }
"""


def page(title: str, body: str) -> str:
    return (
        '<!doctype html><html lang="ru"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        f"<title>{escape(title)} · almanac</title><style>{STYLE}</style></head>"
        f"<body><main><h1>{escape(title)}</h1>{body}</main></body></html>"
    )


def safe_next(target: str | None) -> str:
    """Куда вернуть после входа: только путь на этом же сайте."""
    if target and target.startswith("/") and not target.startswith("//") and "\\" not in target:
        return target
    return "/"


def same_origin(request: Request) -> bool:
    """Запрос пришёл со своей страницы: `Origin` совпадает с адресом сервера."""
    origin = urlsplit(request.headers.get("origin") or "")
    own = urlsplit(request.app.state.settings.base_url)
    return bool(origin.scheme) and (origin.scheme, origin.netloc) == (own.scheme, own.netloc)


async def signed_in(request: Request) -> bool:
    async with request.app.state.db.read() as session:
        return await owner.session_alive(session, request.cookies.get(owner.SESSION_COOKIE))


def _login_page(target: str, error: str = "") -> str:
    note = f'<p class="error">{escape(error)}</p>' if error else ""
    return page(
        "Вход",
        f'{note}<form method="post" action="/login">'
        f'<input type="hidden" name="next" value="{escape(target, quote=True)}">'
        '<input type="password" name="password" placeholder="Пароль" autofocus required>'
        "<button>Войти</button></form>",
    )


@router.get("/login")
async def login_form(next: str = "/") -> HTMLResponse:
    return HTMLResponse(_login_page(safe_next(next)))


@router.post("/login")
async def login(
    request: Request, password: Annotated[str, Form()], next: Annotated[str, Form()] = "/"
) -> Response:
    settings = request.app.state.settings
    target = safe_next(next)
    if not request.app.state.attempts.allow():
        return HTMLResponse(page("Слишком много попыток", "<p>Подождите минуту и попробуйте снова.</p>"), 429)
    if not settings.owner_password_hash or not owner.verify_password(password, settings.owner_password_hash):
        return HTMLResponse(_login_page(target, "Неверный пароль"), 401)
    async with request.app.state.db.write() as session:
        token = await owner.open_session(session)
    response = RedirectResponse(target, status_code=303)
    response.set_cookie(
        owner.SESSION_COOKIE, token, max_age=int(owner.SESSION_TTL.total_seconds()), path="/",
        httponly=True, samesite="lax", secure=settings.base_url.startswith("https"),
    )
    return response


@router.post("/logout")
async def logout(request: Request) -> Response:
    async with request.app.state.db.write() as session:
        await owner.close_session(session, request.cookies.get(owner.SESSION_COOKIE))
    response = RedirectResponse("/login", status_code=303)
    response.delete_cookie(owner.SESSION_COOKIE, path="/")
    return response
