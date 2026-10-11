import asyncio
import os
import sys

from mcp.server.auth.provider import AuthorizationParams
from mcp.shared.auth import OAuthClientInformationFull
from pydantic import AnyUrl

from almanac.auth import owner
from almanac.auth.revoke import revoke_all
from almanac.db import Database

CALLBACK = "https://claude.ai/api/mcp/auth_callback"
TABLES = ["oauth_tokens", "oauth_codes", "auth_pending", "oauth_clients", "sessions"]


def _params():
    return AuthorizationParams(
        state="state-1", scopes=[], code_challenge="c" * 43, redirect_uri=AnyUrl(CALLBACK),
        redirect_uri_provided_explicitly=True,
    )


def _client(client_id):
    return OAuthClientInformationFull(client_id=client_id, redirect_uris=[AnyUrl(CALLBACK)], client_name="Claude")


async def _txn(oauth, client):
    return (await oauth.authorize(client, _params())).split("txn=")[1]


async def _everything_granted(app, db):
    """По живой строке в каждой из пяти таблиц, а токенов — пара."""
    oauth = app.state.oauth
    first, second = _client("client-1"), _client("client-2")
    await oauth.register_client(first)
    await oauth.register_client(second)

    code = (await oauth.decide(await _txn(oauth, first), allow=True)).split("code=")[1].split("&")[0]
    issued = await oauth.exchange_authorization_code(first, await oauth.load_authorization_code(first, code))
    await oauth.decide(await _txn(oauth, second), allow=True)  # код выдан и не обменян
    pending = await _txn(oauth, second)  # владелец ещё не ответил
    async with db.write() as session:
        cookie = await owner.open_session(session)
    return {"issued": issued, "pending": pending, "cookie": cookie}


async def test_revoke_all_kills_every_credential(app, db):
    oauth = app.state.oauth
    granted = await _everything_granted(app, db)
    issued = granted["issued"]
    assert await oauth.load_access_token(issued.access_token) is not None

    counts = await revoke_all(db)

    # Токен доступа и обновления, неиспользованный код, согласие в ожидании, два клиента, браузер владельца.
    assert counts == {"oauth_tokens": 2, "oauth_codes": 1, "auth_pending": 1, "oauth_clients": 2, "sessions": 1}
    assert list(counts) == TABLES
    assert await oauth.load_access_token(issued.access_token) is None
    assert await oauth.get_client("client-1") is None
    assert await oauth.get_client("client-2") is None
    assert await oauth.decide(granted["pending"], allow=True) is None
    async with db.read() as session:
        assert not await owner.session_alive(session, granted["cookie"])


async def test_everyone_signs_in_again_after_revoke(app, db, anon, password):
    await anon.post("/login", data={"password": password})
    assert (await anon.get("/api/guide")).status_code == 200

    await revoke_all(db)

    assert (await anon.get("/api/guide")).status_code == 401
    assert (await anon.post("/login", data={"password": password})).status_code == 303
    assert (await anon.get("/api/guide")).status_code == 200


async def test_revoke_all_on_an_empty_database_removes_nothing(db):
    assert await revoke_all(db) == dict.fromkeys(TABLES, 0)


async def test_command_line_prints_what_it_removed(tmp_path):
    url = f"sqlite+aiosqlite:///{tmp_path / 'cli.db'}"
    database = Database(url)
    await database.create_all()
    async with database.write() as session:
        await owner.open_session(session)
    await database.dispose()

    # Каталог запуска пустой, и `.env` оттуда не прочитается; переменные окружения задаём сами.
    env = {**os.environ, "DATABASE_URL": url}
    process = await asyncio.create_subprocess_exec(
        sys.executable, "-m", "almanac.auth.revoke", env=env, cwd=tmp_path,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
    )
    out, err = await process.communicate()

    assert process.returncode == 0, err.decode()
    assert out.decode().splitlines() == [f"{table}: {1 if table == 'sessions' else 0}" for table in TABLES]
