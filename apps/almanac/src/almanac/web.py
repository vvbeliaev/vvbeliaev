"""Страницы, отрисованные сервером: вход и согласие OAuth. Остальное — API."""

import asyncio
import hmac
from html import escape
from typing import Annotated
from urllib.parse import quote, urlsplit

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response

from almanac import ics
from almanac.auth import owner
from almanac.store import items as items_store

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
    """Запрос пришёл со своей страницы.

    Названный `Origin` обязан совпасть с адресом сервера. Но свои страницы уходят с
    `Referrer-Policy: no-referrer`, а при ней браузер шлёт с формы `Origin: null` — и со своей
    страницы тоже. Тогда источник называет сам браузер в `Sec-Fetch-Site`: скрипт страницы этот
    заголовок выставить не может. Никто не назвал — отказ.
    """
    named = request.headers.get("origin")
    if named and named != "null":
        origin, own = urlsplit(named), urlsplit(request.app.state.settings.base_url)
        return (origin.scheme, origin.netloc) == (own.scheme, own.netloc)
    return request.headers.get("sec-fetch-site") == "same-origin"


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
    # scrypt занимает сотни миллисекунд и десятки мегабайт: в потоке, чтобы не вставал цикл событий.
    known = bool(settings.owner_password_hash) and await asyncio.to_thread(
        owner.verify_password, password, settings.owner_password_hash
    )
    if not known:
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


def _who(name: str) -> str:
    """Имя клиент выбирает сам и ничем не подтверждает: страница говорит об этом прямо."""
    if not name:
        return "Клиент не назвал себя."
    return f"Клиент называет себя «{escape(name)}» (не проверено)."


@router.get("/oauth/consent")
async def consent_form(request: Request, txn: str) -> Response:
    if not await signed_in(request):
        back = quote(f"/oauth/consent?txn={txn}", safe="")
        return RedirectResponse(f"/login?next={back}", status_code=303)
    view = await request.app.state.oauth.consent_view(txn)
    if view is None:
        return HTMLResponse(page("Запрос устарел", "<p>Начните подключение заново в клиенте.</p>"), 400)
    hidden = f'<input type="hidden" name="txn" value="{escape(txn, quote=True)}">'
    return HTMLResponse(
        page(
            "Доступ к almanac",
            f"<p>Код доступа уйдёт на <b>{escape(view.host)}</b>. {_who(view.client)}</p>"
            "<p>Клиент просит доступ на чтение и запись.</p>"
            f'<form method="post" action="/oauth/consent">{hidden}'
            '<button name="decision" value="allow">Разрешить</button>'
            '<button class="quiet" name="decision" value="deny">Отказать</button></form>',
        )
    )


@router.post("/oauth/consent")
async def consent(request: Request, txn: Annotated[str, Form()], decision: Annotated[str, Form()]) -> Response:
    if not await signed_in(request):
        return HTMLResponse(page("Нужен вход", "<p>Сессия закончилась.</p>"), 401)
    if not same_origin(request):
        return HTMLResponse(page("Отказано", "<p>Запрос пришёл с чужой страницы.</p>"), 403)
    target = await request.app.state.oauth.decide(txn, allow=decision == "allow")
    if target is None:
        return HTMLResponse(page("Запрос устарел", "<p>Начните подключение заново в клиенте.</p>"), 400)
    return RedirectResponse(target, status_code=303)


@router.get("/calendar/{token}.ics")
async def calendar(request: Request, token: str) -> Response:
    """Секретный адрес вместо входа: календарные приложения не умеют OAuth."""
    secret = request.app.state.settings.ics_token
    if not secret or not hmac.compare_digest(token.encode(), secret.encode()):
        return Response(status_code=404)
    async with request.app.state.db.read() as session:
        body = ics.render(await items_store.everything(session), request.app.state.settings.owner_tz)
    return Response(body, media_type="text/calendar; charset=utf-8")
