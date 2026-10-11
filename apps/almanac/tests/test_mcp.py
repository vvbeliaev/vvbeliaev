import json
from urllib.parse import parse_qs, urlsplit

import httpx2
import pytest
from asgi_lifespan import LifespanManager
from fastmcp import Client
from fastmcp.client.transports import StreamableHttpTransport
from fastmcp.exceptions import ToolError
from httpx import ASGITransport, AsyncClient
from mcp.server.auth.provider import AuthorizationParams
from mcp.shared.auth import OAuthClientInformationFull
from pydantic import AnyUrl
from sqlalchemy import select

from almanac.app import create_app
from almanac.config import Settings
from almanac.identity import acting
from almanac.models import Journal

TOOLS = {
    "guide", "ls", "grep", "read", "note", "dismiss", "write", "edit", "remove", "history",
    "item_add", "item_update", "items",
}


def _value(result):
    """Что вернул инструмент: структурой, JSON-текстом или (строка из песочницы) голым текстом."""
    if result.data is not None:
        return result.data
    text = result.content[0].text
    try:
        return json.loads(text)
    except ValueError:
        return text


@pytest.fixture
async def mcp(app):
    """Клиент MCP в памяти от имени клиента `claude-test`. Контекст не сбрасываем:
    фикстура и тест идут разными задачами."""
    acting.set("claude-test")
    async with Client(app.state.mcp) as client:
        yield client


@pytest.fixture
async def direct(db, settings, now):
    """Тот же сервер без Code Mode: инструменты видны напрямую."""
    plain = Settings(_env_file=None, owner_tz="Europe/Berlin", mcp_code_mode=False)
    acting.set("claude-test")
    async with Client(create_app(plain, db=db).state.mcp) as client:
        yield client


async def test_code_mode_shows_only_meta_tools(mcp):
    assert {tool.name for tool in await mcp.list_tools()} == {"search", "get_schema", "execute"}


async def test_execute_writes_through_the_api(mcp, db):
    result = await mcp.call_tool(
        "execute",
        {"code": "fact = await call_tool('note', {'text': 'купить лампочки'})\nreturn fact['id']"},
    )
    fact_id = _value(result)
    assert fact_id.startswith("f_")
    async with db.read() as session:
        entry = (await session.scalars(select(Journal))).one()
    assert (entry.op, entry.target, entry.client) == ("note", fact_id, "claude-test")


async def test_refusal_reaches_the_model(mcp):
    code = (
        "return await call_tool('write', {'path': 'pages/people/anna.md', 'title': 'Анна', "
        "'description': 'Подруга', 'body': 'Текст', 'reason': 'проверка'})"
    )
    with pytest.raises(ToolError, match="name the source"):
        await mcp.call_tool("execute", {"code": code})


async def test_direct_mode_exposes_every_tool(direct):
    assert {tool.name for tool in await direct.list_tools()} == TOOLS


async def test_unknown_argument_is_refused(direct):
    with pytest.raises(ToolError, match="unknown parameters: pth"):
        await direct.call_tool("ls", {"pth": "pages"})


async def test_call_without_identity_is_refused(db, settings, now):
    acting.set(None)
    async with Client(create_app(settings, db=db).state.mcp) as client:
        with pytest.raises(ToolError):
            await client.call_tool("execute", {"code": "return await call_tool('guide', {})"})


async def test_http_door_needs_a_token(app):
    ping = {"jsonrpc": "2.0", "id": 1, "method": "ping"}
    headers = {"Accept": "application/json, text/event-stream"}
    async with (
        LifespanManager(app),
        AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as http,
    ):
        assert (await http.post("/mcp/", json=ping, headers=headers)).status_code == 401
        bad = {**headers, "Authorization": "Bearer nope"}
        assert (await http.post("/mcp/", json=ping, headers=bad)).status_code == 401


async def test_http_token_names_the_client_in_the_journal(app, db):
    """Настоящий путь двери: токен OAuth -> имя клиента -> подписанный заголовок -> журнал.
    Заголовок, пришедший снаружи под тем же именем, ничего не решает."""
    acting.set(None)  # имя берётся из токена, а не из процесса
    oauth = app.state.oauth
    callback = "https://claude.ai/api/mcp/auth_callback"
    client = OAuthClientInformationFull(
        client_id="client-1", redirect_uris=[AnyUrl(callback)], client_name="Claude Code"
    )
    await oauth.register_client(client)
    params = AuthorizationParams(
        state="state-1", scopes=[], code_challenge="c" * 43, redirect_uri=AnyUrl(callback),
        redirect_uri_provided_explicitly=True,
    )
    txn = (await oauth.authorize(client, params)).split("txn=")[1]
    code = parse_qs(urlsplit(await oauth.decide(txn, allow=True)).query)["code"][0]
    issued = await oauth.exchange_authorization_code(client, await oauth.load_authorization_code(client, code))

    def factory(**kwargs):
        kwargs.pop("verify", None)
        return httpx2.AsyncClient(transport=httpx2.ASGITransport(app=app), **kwargs)

    headers = {"Authorization": f"Bearer {issued.access_token}", "x-almanac-client": "site.forged"}
    transport = StreamableHttpTransport("http://test/mcp/", headers=headers, httpx_client_factory=factory)
    async with app.state.mcp_app.lifespan(app), Client(transport) as http_client:
        result = await http_client.call_tool(
            "execute", {"code": "fact = await call_tool('note', {'text': 'через токен'})\nreturn fact['client']"}
        )
    assert _value(result) == "Claude Code"
    async with db.read() as session:
        entry = (await session.scalars(select(Journal))).one()
    assert (entry.op, entry.client) == ("note", "Claude Code")
