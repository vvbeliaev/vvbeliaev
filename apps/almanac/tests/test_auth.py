import re
import threading
from datetime import timedelta

import pytest
from httpx import ASGITransport, AsyncClient

from almanac import clock
from almanac.app import create_app
from almanac.auth import owner
from almanac.config import Settings
from almanac.identity import INTERNAL_HEADER, sign_internal


def test_password_hash_round_trip():
    stored = owner.hash_password("s3cret words", n=2**14)
    assert stored.startswith("scrypt:16384:8:1:")
    assert owner.verify_password("s3cret words", stored)
    assert not owner.verify_password("other", stored)
    assert not owner.verify_password("s3cret words", "garbage")
    assert not owner.verify_password("s3cret words", "")


def test_default_hash_is_strong_and_carries_its_parameters():
    stored = owner.hash_password("s3cret words")
    assert stored.startswith("scrypt:131072:8:1:")
    assert owner.verify_password("s3cret words", stored)
    assert not owner.verify_password("other", stored)


def test_parameters_come_from_the_stored_string():
    weak = owner.hash_password("s3cret words", n=2**10)
    assert owner.verify_password("s3cret words", weak)
    # Те же соль и хэш с другим N — другой ключ: параметры действительно читаются из строки.
    _, _, r, p, salt, digest = weak.split(":")
    assert not owner.verify_password("s3cret words", f"scrypt:{2**11}:{r}:{p}:{salt}:{digest}")


@pytest.mark.parametrize(
    "stored",
    [
        "scrypt:aa:bb",  # прежний трёхчастный формат больше не принимается
        "scrypt:16384:8:1:aa",  # пять частей
        "scrypt:16384:8:1:aa:bb:cc",  # семь частей
        "scrypt:x:8:1:aa:bb",  # N не число
        "scrypt:16384:8:1:zz:bb",  # соль не hex
        "scrypt:16384:8:1:aa:zz",  # хэш не hex
        "scrypt:0:8:1:aa:bb",
        "scrypt:16385:8:1:aa:bb",  # N не степень двойки
        "scrypt:-16384:8:1:aa:bb",
        "scrypt:16384:0:1:aa:bb",
        "scrypt:16384:8:0:aa:bb",
        f"scrypt:{2**21}:8:1:aa:bb",  # N выше потолка 2**20
        f"scrypt:16384:{2**70}:1:aa:bb",
        "argon2:16384:8:1:aa:bb",
        "scrypt:::::",
        "garbage",
        "",
    ],
)
def test_malformed_hash_is_refused(stored):
    assert owner.verify_password("s3cret words", stored) is False


async def test_login_check_runs_off_the_event_loop(anon, password, monkeypatch):
    seen = []
    real = owner.verify_password

    def spy(candidate, stored):
        seen.append(threading.get_ident())
        return real(candidate, stored)

    monkeypatch.setattr(owner, "verify_password", spy)
    assert (await anon.post("/login", data={"password": password})).status_code == 303
    assert seen and seen[0] != threading.get_ident()


async def test_api_is_closed_without_identity(anon):
    assert (await anon.get("/api/guide")).status_code == 401
    assert (await anon.get("/healthz")).status_code == 200


HTTP_METHODS = {"get", "put", "post", "patch", "delete", "options", "head", "trace"}


async def test_every_api_operation_refuses_an_anonymous_caller(app, anon):
    """Обход по схеме, а не по списку из головы: новая ручка без входа не пройдёт незамеченной."""
    refused = []
    for path, methods in app.openapi()["paths"].items():
        if not path.startswith("/api"):
            continue
        for method, operation in methods.items():
            if method not in HTTP_METHODS:
                continue
            url = re.sub(r"\{[^}]+\}", "x", path)
            body = {"json": {}} if "requestBody" in operation else {}
            response = await anon.request(method.upper(), url, **body)
            assert response.status_code == 401, (method, path, response.status_code)
            refused.append((method, path))
    assert len(refused) >= 13  # все инструменты на месте: обход не пустой
    assert ("get", "/api/guide") in refused


async def test_login_opens_the_api(anon, password):
    wrong = await anon.post("/login", data={"password": "nope"})
    assert wrong.status_code == 401

    ok = await anon.post("/login", data={"password": password, "next": "/api/guide"})
    assert (ok.status_code, ok.headers["location"]) == (303, "/api/guide")
    assert "httponly" in ok.headers["set-cookie"].lower()
    assert (await anon.get("/api/guide")).status_code == 200

    fact = (await anon.post("/api/facts", json={"text": "проверка входа"})).json()
    assert fact["client"] == "site"

    await anon.post("/logout")
    assert (await anon.get("/api/guide")).status_code == 401


async def test_owner_session_dies_after_thirty_days(anon, password, now, monkeypatch):
    await anon.post("/login", data={"password": password})

    monkeypatch.setattr(clock, "_now", lambda: now + timedelta(days=29))
    assert (await anon.get("/api/guide")).status_code == 200  # ещё жива: проверка не пустая

    monkeypatch.setattr(clock, "_now", lambda: now + timedelta(days=31))
    assert (await anon.get("/api/guide")).status_code == 401


async def test_session_cookie_is_secure_only_over_https(db, now, password, settings):
    async def cookie_for(base_url):
        configured = Settings(_env_file=None, base_url=base_url, owner_password_hash=settings.owner_password_hash)
        async with AsyncClient(transport=ASGITransport(app=create_app(configured, db=db)), base_url="http://test") as http:
            return (await http.post("/login", data={"password": password})).headers["set-cookie"].lower()

    behind_https = await cookie_for("https://almanac.example")
    assert "secure" in behind_https.split("; ") and "httponly" in behind_https and "samesite=lax" in behind_https
    assert "secure" not in (await cookie_for("http://127.0.0.1:8000")).split("; ")


async def test_login_does_not_redirect_outside(anon, password):
    for target in ("https://evil.example", "//evil.example", "/\\evil.example"):
        ok = await anon.post("/login", data={"password": password, "next": target})
        assert ok.headers["location"] == "/"


async def test_login_attempts_are_limited(anon):
    codes = [(await anon.post("/login", data={"password": "nope"})).status_code for _ in range(6)]
    assert codes == [401] * 5 + [429]


async def test_internal_header_names_the_client(anon):
    ok = await anon.post("/api/facts", json={"text": "из MCP"}, headers={INTERNAL_HEADER: sign_internal("Claude")})
    assert ok.json()["client"] == "Claude"
    forged = await anon.get("/api/guide", headers={INTERNAL_HEADER: "Claude.deadbeef"})
    assert forged.status_code == 401


async def test_login_page_renders(anon):
    page = await anon.get("/login", params={"next": "/oauth/consent?txn=abc"})
    assert page.status_code == 200
    assert 'name="password"' in page.text
    assert "/oauth/consent?txn=abc" in page.text
