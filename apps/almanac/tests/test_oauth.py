from urllib.parse import parse_qs, urlsplit

import pytest
from mcp.server.auth.provider import AuthorizationParams, RegistrationError, TokenError
from mcp.shared.auth import OAuthClientInformationFull
from pydantic import AnyUrl

CALLBACK = "https://claude.ai/api/mcp/auth_callback"


def _client(redirect=CALLBACK, name="Claude"):
    return OAuthClientInformationFull(client_id="client-1", redirect_uris=[AnyUrl(redirect)], client_name=name)


def _params():
    return AuthorizationParams(
        state="state-1", scopes=[], code_challenge="c" * 43, redirect_uri=AnyUrl(CALLBACK),
        redirect_uri_provided_explicitly=True,
    )


def _query(url):
    return {key: values[0] for key, values in parse_qs(urlsplit(url).query).items()}


async def _granted(oauth):
    """Клиент зарегистрирован, владелец разрешил: возвращает клиента и выданную пару токенов."""
    client = _client()
    await oauth.register_client(client)
    txn = _query(await oauth.authorize(client, _params()))["txn"]
    code = _query(await oauth.decide(txn, allow=True))["code"]
    loaded = await oauth.load_authorization_code(client, code)
    return client, await oauth.exchange_authorization_code(client, loaded)


@pytest.fixture
def oauth(app):
    return app.state.oauth


@pytest.mark.parametrize("redirect", ["javascript:alert(1)", "http://evil.example/cb", "ftp://example.org/cb"])
async def test_registration_refuses_unsafe_redirects(oauth, redirect):
    with pytest.raises(RegistrationError):
        await oauth.register_client(_client(redirect))


@pytest.mark.parametrize("redirect", [CALLBACK, "http://localhost:53124/callback", "cursor://oauth/callback"])
async def test_registration_accepts_https_loopback_and_app_schemes(oauth, redirect):
    await oauth.register_client(_client(redirect))
    assert (await oauth.get_client("client-1")).client_name == "Claude"


async def test_consent_grants_a_working_token(oauth):
    client = _client()
    await oauth.register_client(client)
    consent_url = await oauth.authorize(client, _params())
    assert consent_url.startswith("/oauth/consent?txn=")
    txn = _query(consent_url)["txn"]

    view = await oauth.consent_view(txn)
    assert (view.client, view.host) == ("Claude", "claude.ai")

    back = _query(await oauth.decide(txn, allow=True))
    assert back["state"] == "state-1"
    assert await oauth.decide(txn, allow=True) is None  # шаг срабатывает один раз

    code = await oauth.load_authorization_code(client, back["code"])
    issued = await oauth.exchange_authorization_code(client, code)
    access = await oauth.load_access_token(issued.access_token)
    assert (access.client_id, access.subject) == ("client-1", "owner")
    with pytest.raises(TokenError):
        await oauth.exchange_authorization_code(client, code)  # код сгорает при обмене


async def test_denied_consent_returns_an_error(oauth):
    client = _client()
    await oauth.register_client(client)
    txn = _query(await oauth.authorize(client, _params()))["txn"]
    assert _query(await oauth.decide(txn, allow=False))["error"] == "access_denied"


async def test_refresh_rotates_the_pair(oauth):
    client, first = await _granted(oauth)
    refresh = await oauth.load_refresh_token(client, first.refresh_token)
    second = await oauth.exchange_refresh_token(client, refresh, [])
    assert await oauth.load_access_token(first.access_token) is None
    assert await oauth.load_refresh_token(client, first.refresh_token) is None
    assert await oauth.load_access_token(second.access_token) is not None


async def test_rotated_refresh_token_cannot_be_exchanged_again(oauth):
    client, first = await _granted(oauth)
    refresh = await oauth.load_refresh_token(client, first.refresh_token)
    await oauth.exchange_refresh_token(client, refresh, [])
    with pytest.raises(TokenError):
        await oauth.exchange_refresh_token(client, refresh, [])


async def test_revoke_kills_the_pair(oauth):
    client, issued = await _granted(oauth)
    await oauth.revoke_token(await oauth.load_access_token(issued.access_token))
    assert await oauth.load_access_token(issued.access_token) is None
    assert await oauth.load_refresh_token(client, issued.refresh_token) is None


async def test_client_name_is_safe_for_a_header(oauth):
    await oauth.register_client(_client(name="Клод Desktop"))
    name = await oauth.client_name("client-1")
    assert name.isascii() and name.endswith("Desktop")
    assert await oauth.client_name("unknown") == "mcp-client"


async def test_consent_page_needs_the_owner(anon, oauth, password, settings):
    client = _client()
    await oauth.register_client(client)
    consent_url = await oauth.authorize(client, _params())
    txn = _query(consent_url)["txn"]

    stranger = await anon.get(consent_url)
    assert stranger.status_code == 303
    assert stranger.headers["location"].startswith("/login?next=")

    await anon.post("/login", data={"password": password})
    shown = await anon.get(consent_url)
    assert shown.status_code == 200
    assert "Claude" in shown.text and "claude.ai" in shown.text

    foreign = await anon.post(
        "/oauth/consent", data={"txn": txn, "decision": "allow"}, headers={"origin": "https://evil.example"}
    )
    assert foreign.status_code == 403

    allowed = await anon.post(
        "/oauth/consent", data={"txn": txn, "decision": "allow"}, headers={"origin": settings.base_url}
    )
    assert allowed.status_code == 303
    assert allowed.headers["location"].startswith(CALLBACK + "?code=")
