"""Сайт: собранные файлы и чтение без входа с этой же машины (`LOCAL_SITE`)."""

import pytest
from httpx import ASGITransport, AsyncClient
from pydantic import ValidationError

from almanac.app import SITE_CSP, create_app
from almanac.config import Settings

HERE = "http://127.0.0.1:8910"


@pytest.fixture
def local(db, settings, now):
    """Приложение, как его поднимает `make up`: адрес — сама машина, чтение без входа включено."""
    return create_app(settings.model_copy(update={"base_url": HERE, "local_site": True}), db=db)


def _client(app, *, base_url=HERE, peer="127.0.0.1", **headers):
    transport = ASGITransport(app=app, client=(peer, 50000))
    return AsyncClient(transport=transport, base_url=base_url, headers=headers)


async def test_this_machine_reads_without_signing_in(local):
    async with _client(local) as client:
        tree = await client.get("/api/tree")
        week = await client.get("/api/file", params={"path": "views/week.md"})
    assert tree.status_code == 200
    assert week.json()["path"] == "views/week.md"


async def test_reading_is_all_it_gets(local, db):
    async with _client(local) as client:
        written = await client.post("/api/facts", json={"text": "записать без входа"})
    assert written.status_code == 401


async def test_another_machine_does_not_get_in(local):
    async with _client(local, peer="203.0.113.7") as client:
        assert (await client.get("/api/tree")).status_code == 401


async def test_a_page_whose_name_was_pointed_at_this_machine_does_not_get_in(local):
    """Чужое имя, перенаправленное на 127.0.0.1: соединение местное, но Host — не адрес сервера."""
    async with _client(local, base_url="http://evil.example:8910") as client:
        assert (await client.get("/api/tree")).status_code == 401


async def test_a_request_made_by_another_site_does_not_get_in(local):
    async with _client(local, **{"sec-fetch-site": "cross-site"}) as client:
        assert (await client.get("/api/tree")).status_code == 401
    async with _client(local, **{"sec-fetch-site": "same-origin"}) as client:
        assert (await client.get("/api/tree")).status_code == 200


async def test_without_the_setting_this_machine_signs_in_like_anyone(db, settings, now):
    app = create_app(settings.model_copy(update={"base_url": HERE}), db=db)
    async with _client(app) as client:
        assert (await client.get("/api/tree")).status_code == 401


async def test_consent_still_needs_the_owner_to_sign_in(local):
    """Чтение без входа не делает никого владельцем: выдать доступ клиенту OAuth оно не даёт."""
    async with _client(local) as client:
        response = await client.get("/oauth/consent", params={"txn": "x"})
    assert response.status_code in (302, 303, 307)
    assert response.headers["location"].startswith("/login")


def test_the_setting_is_refused_on_a_public_address():
    with pytest.raises(ValidationError, match="LOCAL_SITE"):
        Settings(_env_file=None, base_url="https://almanac.example", local_site=True)
    assert Settings(_env_file=None, base_url=HERE, local_site=True).local_site


@pytest.fixture
def built(tmp_path):
    (tmp_path / "assets").mkdir()
    (tmp_path / "index.html").write_text("<!doctype html><title>almanac</title>")
    (tmp_path / "assets" / "app.js").write_text("export {};")
    return tmp_path


async def test_the_built_site_is_served_at_the_root_with_a_strict_policy(db, settings, now, built):
    app = create_app(settings.model_copy(update={"site_dir": built}), db=db)
    async with _client(app, base_url="http://test") as client:
        home = await client.get("/")
        script = await client.get("/assets/app.js")
        api = await client.get("/api/guide")
        health = await client.get("/healthz")
    assert home.status_code == 200 and "<title>almanac</title>" in home.text
    assert script.status_code == 200
    for response in (home, script):
        assert response.headers["content-security-policy"] == SITE_CSP
        assert response.headers["x-frame-options"] == "DENY"
    # Сайт стоит последним: свои адреса сервер не отдаёт ему.
    assert api.status_code == 401
    assert api.headers["content-security-policy"] == "frame-ancestors 'none'"
    assert health.json() == {"ok": True}


async def test_no_built_site_no_root(anon):
    assert (await anon.get("/")).status_code == 404
