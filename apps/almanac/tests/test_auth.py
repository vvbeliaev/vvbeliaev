from almanac.auth import owner
from almanac.identity import INTERNAL_HEADER, sign_internal


def test_password_hash_round_trip():
    stored = owner.hash_password("s3cret words")
    assert stored.startswith("scrypt:")
    assert owner.verify_password("s3cret words", stored)
    assert not owner.verify_password("other", stored)
    assert not owner.verify_password("s3cret words", "garbage")
    assert not owner.verify_password("s3cret words", "")


async def test_api_is_closed_without_identity(anon):
    assert (await anon.get("/api/guide")).status_code == 401
    assert (await anon.get("/healthz")).status_code == 200


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
