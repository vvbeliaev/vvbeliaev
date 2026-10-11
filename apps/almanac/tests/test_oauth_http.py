"""OAuth целиком по настоящим маршрутам HTTP: то, что видит клиент MCP, а не вызовы провайдера."""

import base64
import hashlib
import secrets
from dataclasses import dataclass
from urllib.parse import parse_qs, urlsplit

import pytest
from asgi_lifespan import LifespanManager
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select

from almanac.models import AuthPending

CALLBACK = "https://claude.ai/api/mcp/auth_callback"
INITIALIZE = {
    "jsonrpc": "2.0", "id": 1, "method": "initialize",
    "params": {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "test", "version": "1"}},
}
MCP_HEADERS = {"Accept": "application/json, text/event-stream"}


def _path(url: str) -> str:
    """Адреса из метаданных абсолютные и смотрят на `base_url`; тестовый клиент ходит по пути."""
    parts = urlsplit(url)
    return parts.path + (f"?{parts.query}" if parts.query else "")


def _challenge(verifier: str) -> str:
    return base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()


@dataclass
class Door:
    http: AsyncClient
    meta: dict
    origin: str
    password: str

    async def register(self, name="Claude", redirect=CALLBACK):
        payload = {
            "redirect_uris": [redirect], "client_name": name, "token_endpoint_auth_method": "client_secret_post",
            "grant_types": ["authorization_code", "refresh_token"], "response_types": ["code"],
        }
        return await self.http.post(_path(self.meta["registration_endpoint"]), json=payload)

    async def authorize(self, client: dict, verifier: str, redirect=CALLBACK, method="S256"):
        params = {
            "response_type": "code", "client_id": client["client_id"], "redirect_uri": redirect, "state": "st1",
            "code_challenge": _challenge(verifier) if method == "S256" else verifier, "code_challenge_method": method,
        }
        return await self.http.get(_path(self.meta["authorization_endpoint"]), params=params)

    async def approve(self, consent_url: str) -> str:
        """Согласие по-настоящему: страница за входом, вход паролем, «Разрешить» со своим `Origin`."""
        stranger = await self.http.get(consent_url)
        assert stranger.status_code == 303 and stranger.headers["location"].startswith("/login")
        login = await self.http.post("/login", data={"password": self.password, "next": consent_url})
        assert login.headers["location"] == consent_url
        assert (await self.http.get(consent_url)).status_code == 200
        txn = parse_qs(urlsplit(consent_url).query)["txn"][0]
        decision = await self.http.post(
            "/oauth/consent", data={"txn": txn, "decision": "allow"}, headers={"origin": self.origin}
        )
        assert decision.status_code == 303
        return parse_qs(urlsplit(decision.headers["location"]).query)["code"][0]

    async def exchange(self, client: dict, code: str, verifier: str, redirect=CALLBACK):
        form = {
            "grant_type": "authorization_code", "code": code, "redirect_uri": redirect, "code_verifier": verifier,
            "client_id": client["client_id"], "client_secret": client["client_secret"],
        }
        return await self.http.post(_path(self.meta["token_endpoint"]), data=form)

    async def grant(self, name="Claude"):
        """Весь путь до пары токенов. Возвращает клиента, проверку PKCE и ответ `/token`."""
        client = (await self.register(name)).json()
        verifier = secrets.token_urlsafe(48)
        authorize = await self.authorize(client, verifier)
        assert authorize.status_code == 302
        code = await self.approve(authorize.headers["location"])
        return client, verifier, code, await self.exchange(client, code, verifier)

    async def knock(self, access_token: str):
        headers = {**MCP_HEADERS, "Authorization": f"Bearer {access_token}"}
        return await self.http.post("/mcp/", json=INITIALIZE, headers=headers)


@pytest.fixture
async def door(app, settings, password):
    async with (
        LifespanManager(app),
        AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as http,
    ):
        meta = (await http.get("/.well-known/oauth-authorization-server/mcp")).json()
        yield Door(http, meta, settings.base_url, password)


async def test_whole_flow_ends_in_a_door_that_opens(door):
    client, _, _, issued = await door.grant()

    assert issued.status_code == 200
    pair = issued.json()
    assert pair["token_type"] == "Bearer" and pair["access_token"] and pair["refresh_token"]
    assert (await door.knock(pair["access_token"])).status_code == 200
    assert (await door.knock(pair["access_token"] + "x")).status_code == 401

    # Отзыв по настоящему маршруту: умирает вся пара.
    revoke = {"token": pair["access_token"], "client_id": client["client_id"], "client_secret": client["client_secret"]}
    assert (await door.http.post(_path(door.meta["revocation_endpoint"]), data=revoke)).status_code == 200
    assert (await door.knock(pair["access_token"])).status_code == 401
    refresh = {
        "grant_type": "refresh_token", "refresh_token": pair["refresh_token"],
        "client_id": client["client_id"], "client_secret": client["client_secret"],
    }
    assert (await door.http.post(_path(door.meta["token_endpoint"]), data=refresh)).status_code == 401


async def test_wrong_code_verifier_is_refused(door):
    client = (await door.register()).json()
    verifier = secrets.token_urlsafe(48)
    code = await door.approve((await door.authorize(client, verifier)).headers["location"])

    refused = await door.exchange(client, code, secrets.token_urlsafe(48))

    assert refused.status_code in (400, 401)
    assert refused.json()["error"] == "invalid_grant" and "access_token" not in refused.json()


async def test_replayed_code_is_refused(door):
    client, verifier, code, first = await door.grant()
    assert first.status_code == 200

    replay = await door.exchange(client, code, verifier)

    assert replay.status_code in (400, 401)
    assert replay.json()["error"] == "invalid_grant" and "access_token" not in replay.json()


async def test_code_cannot_be_used_by_another_client(door):
    client = (await door.register()).json()
    thief = (await door.register("Other")).json()
    verifier = secrets.token_urlsafe(48)
    code = await door.approve((await door.authorize(client, verifier)).headers["location"])

    refused = await door.exchange(thief, code, verifier)

    assert refused.status_code in (400, 401) and "access_token" not in refused.json()


async def test_unregistered_redirect_uri_is_refused_at_authorize(door, db):
    client = (await door.register()).json()

    refused = await door.authorize(client, secrets.token_urlsafe(48), redirect="https://evil.example/cb")

    assert refused.status_code == 400
    assert "location" not in refused.headers  # на чужой адрес браузер не отправляют даже с ошибкой
    async with db.read() as session:
        assert await session.scalar(select(func.count()).select_from(AuthPending)) == 0


async def test_pkce_is_required_and_only_s256(door, db):
    client = (await door.register()).json()

    plain = await door.authorize(client, secrets.token_urlsafe(48), method="plain")
    bare = await door.http.get(
        _path(door.meta["authorization_endpoint"]),
        params={"response_type": "code", "client_id": client["client_id"], "redirect_uri": CALLBACK},
    )

    for refused in (plain, bare):
        # Отказ уходит клиенту на его зарегистрированный адрес; страницы согласия не будет.
        assert refused.status_code == 302 and refused.headers["location"].startswith(CALLBACK + "?error=invalid_request")
    async with db.read() as session:
        assert await session.scalar(select(func.count()).select_from(AuthPending)) == 0


@pytest.mark.parametrize("redirect", ["ms-msdt:/id x", "search-ms:query=x", "intent://x", "http://evil.example/cb"])
async def test_registration_route_refuses_unsafe_redirects(door, redirect):
    refused = await door.register(redirect=redirect)
    assert refused.status_code == 400
    assert refused.json()["error"] == "invalid_redirect_uri"


async def test_registration_route_refuses_a_very_long_client_name(door):
    refused = await door.register(name="x" * 201)
    assert refused.status_code == 400
    assert refused.json()["error"] == "invalid_client_metadata"
    assert (await door.register(name="x" * 200)).status_code == 201


async def test_registration_route_refuses_a_nul_in_the_client_name(door):
    refused = await door.register(name="Claude\x00")
    assert refused.status_code == 400
    assert refused.json()["error"] == "invalid_client_metadata"


async def test_authorize_route_answers_an_unknown_client_with_a_nul_in_its_id_without_a_500(door):
    unknown = await door.authorize({"client_id": "client\x00"}, secrets.token_urlsafe(48))
    assert unknown.status_code == 400
