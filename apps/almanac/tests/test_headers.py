from httpx import ASGITransport, AsyncClient
from starlette.applications import Starlette
from starlette.responses import PlainTextResponse
from starlette.routing import Route

from almanac.app import SecureHeaders

FIXED = {
    "x-frame-options": "DENY",
    "content-security-policy": "frame-ancestors 'none'",
    "referrer-policy": "no-referrer",
}


async def test_every_kind_of_response_carries_the_headers(anon):
    for path in ("/login", "/oauth/consent?txn=x", "/api/guide", "/healthz"):
        response = await anon.get(path)
        for name, value in FIXED.items():
            assert response.headers.get(name) == value, (path, name)
    assert (await anon.get("/login")).headers["cache-control"] == "no-store"


async def test_the_oauth_metadata_keeps_its_own_cache_policy(anon):
    metadata = await anon.get("/.well-known/oauth-authorization-server/mcp")
    assert metadata.headers["cache-control"] == "public, max-age=3600"
    assert metadata.headers["x-frame-options"] == "DENY"


async def test_an_unhandled_error_still_carries_the_headers(app):
    async def boom():
        raise RuntimeError("test failure")

    app.add_api_route("/boom", boom)
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/boom")
    assert response.status_code == 500
    for name, value in FIXED.items():
        assert response.headers.get(name) == value, name
    assert response.headers["cache-control"] == "no-store"


async def test_no_form_action_is_set(anon):
    # form-action ломает возврат к клиенту OAuth: браузер применяет его и к редиректу после формы.
    assert "form-action" not in (await anon.get("/login")).headers["content-security-policy"]


async def test_own_cache_control_is_kept():
    async def cached(_request):
        return PlainTextResponse("ok", headers={"Cache-Control": "public, max-age=60"})

    async def plain(_request):
        return PlainTextResponse("ok")

    wrapped = SecureHeaders(Starlette(routes=[Route("/cached", cached), Route("/plain", plain)]))
    async with AsyncClient(transport=ASGITransport(app=wrapped), base_url="http://test") as client:
        kept = await client.get("/cached")
        added = await client.get("/plain")
    assert kept.headers["cache-control"] == "public, max-age=60"
    assert kept.headers["x-frame-options"] == "DENY"
    assert added.headers["cache-control"] == "no-store"


async def test_a_weaker_policy_of_its_own_is_replaced_and_the_site_one_is_kept():
    from almanac.app import SITE_CSP

    async def weak(_request):
        return PlainTextResponse("ok", headers={"Content-Security-Policy": "default-src *"})

    async def site(_request):
        return PlainTextResponse("ok", headers={"Content-Security-Policy": SITE_CSP})

    wrapped = SecureHeaders(Starlette(routes=[Route("/weak", weak), Route("/site", site)]))
    async with AsyncClient(transport=ASGITransport(app=wrapped), base_url="http://test") as client:
        replaced = await client.get("/weak")
        kept = await client.get("/site")
    assert replaced.headers["content-security-policy"] == "frame-ancestors 'none'"
    assert kept.headers["content-security-policy"] == SITE_CSP

