"""OAuth для MCP: хранилище под готовым `OAuthProvider` FastMCP.

Протокол — обнаружение, регистрацию клиентов, PKCE, выдачу и обновление токенов,
отзыв — делает библиотека. Здесь то, что она оставляет реализации: хранилище и
шаг «разрешить». `authorize` не решает за владельца: откладывает запрос и
отправляет браузер на страницу согласия, которая за входом.

Токены доступа живут час, обновления — 30 дней; обмен refresh-токена выдаёт
новую пару, старая сгорает целиком.
"""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from urllib.parse import urlsplit

from fastmcp.server.auth import AccessToken, OAuthProvider
from fastmcp.server.auth.auth import ClientRegistrationOptions, RevocationOptions
from mcp.server.auth.provider import (
    AuthorizationCode,
    AuthorizationParams,
    RefreshToken,
    RegistrationError,
    TokenError,
    construct_redirect_uri,
)
from mcp.shared.auth import OAuthClientInformationFull
from mcp.shared.auth import OAuthToken as IssuedToken
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from almanac.auth.tokens import hash_token, new_token
from almanac.clock import utcnow
from almanac.db import Database
from almanac.models import AuthPending, OAuthClient, OAuthCode, OAuthToken

OWNER = "owner"
CONSENT_PATH = "/oauth/consent"
CODE_TTL = timedelta(minutes=5)
CONSENT_TTL = timedelta(minutes=10)
ACCESS_TTL = timedelta(hours=1)
REFRESH_TTL = timedelta(days=30)
# Имя клиента приходит от кого угодно: регистрация открытая. Это только данные.
NAME_MAX = 60
LOOPBACK = frozenset({"localhost", "127.0.0.1", "::1"})
# Схемы, с которыми адрес возврата стал бы выполнением, а не возвратом.
FORBIDDEN_SCHEMES = frozenset({"javascript", "data", "file", "vbscript", "blob", "about", "ftp"})
CODE_FIELDS = ("redirect_uri", "redirect_uri_provided_explicitly", "scopes", "code_challenge", "resource")


@dataclass(frozen=True)
class ConsentView:
    """Что показать владельцу на странице согласия."""

    client: str
    host: str


def _acceptable_redirect(uri: str) -> bool:
    """https; http — только на себя (локальные клиенты вроде Claude Code); своя схема приложения."""
    parts = urlsplit(uri)
    scheme = parts.scheme.lower()
    if not scheme or scheme in FORBIDDEN_SCHEMES:
        return False
    if scheme == "https":
        return bool(parts.hostname)
    if scheme == "http":
        return parts.hostname in LOOPBACK
    return True


def _epoch(moment: datetime) -> int:
    return int(moment.timestamp())


class AlmanacOAuthProvider(OAuthProvider):
    def __init__(self, *, base_url: str, db: Callable[[], Database]) -> None:
        super().__init__(
            base_url=base_url,
            client_registration_options=ClientRegistrationOptions(enabled=True),
            revocation_options=RevocationOptions(enabled=True),
        )
        # Фабрика, а не база: приложение собирается раньше, чем база открыта.
        self._db = db

    # --- клиенты ---

    async def get_client(self, client_id: str) -> OAuthClientInformationFull | None:
        async with self._db().read() as session:
            row = await session.get(OAuthClient, client_id)
        return OAuthClientInformationFull.model_validate(row.info) if row else None

    async def register_client(self, client_info: OAuthClientInformationFull) -> None:
        uris = [str(uri) for uri in client_info.redirect_uris or []]
        if not uris or not all(_acceptable_redirect(uri) for uri in uris):
            raise RegistrationError(
                "invalid_redirect_uri", "redirect_uris: https, http on localhost, or the app's own scheme"
            )
        async with self._db().write() as session:
            await session.merge(OAuthClient(client_id=client_info.client_id, info=client_info.model_dump(mode="json")))

    async def client_name(self, client_id: str) -> str:
        """Имя клиента для журнала и внутреннего заголовка: только ASCII, не длиннее `NAME_MAX`."""
        async with self._db().read() as session:
            row = await session.get(OAuthClient, client_id)
        name = str((row.info if row else {}).get("client_name") or "").strip() or "mcp-client"
        return name.encode("ascii", "replace").decode()[:NAME_MAX]

    # --- согласие ---

    async def authorize(self, client: OAuthClientInformationFull, params: AuthorizationParams) -> str:
        txn = new_token()
        async with self._db().write() as session:
            session.add(
                AuthPending(
                    state_hash=hash_token(txn), kind="consent", expires_at=utcnow() + CONSENT_TTL,
                    data={
                        "client_id": client.client_id,
                        "redirect_uri": str(params.redirect_uri),
                        "redirect_uri_provided_explicitly": params.redirect_uri_provided_explicitly,
                        "state": params.state,
                        "scopes": params.scopes or [],
                        "code_challenge": params.code_challenge,
                        "resource": getattr(params, "resource", None),
                    },
                )
            )
        return f"{CONSENT_PATH}?txn={txn}"

    @staticmethod
    async def _pending(session: AsyncSession, txn: str) -> AuthPending | None:
        pending = await session.get(AuthPending, hash_token(txn or ""))
        if pending is None or pending.kind != "consent" or pending.expires_at <= utcnow():
            return None
        return pending

    async def consent_view(self, txn: str) -> ConsentView | None:
        async with self._db().read() as session:
            pending = await self._pending(session, txn)
            client = await session.get(OAuthClient, pending.data["client_id"]) if pending else None
        if pending is None or client is None:
            return None
        parts = urlsplit(pending.data["redirect_uri"])
        name = str(client.info.get("client_name") or "").strip() or parts.hostname or "client"
        return ConsentView(client=name[:NAME_MAX], host=parts.hostname or f"{parts.scheme}:")

    async def decide(self, txn: str, *, allow: bool) -> str | None:
        """Ответ владельца → куда вернуть браузер. Шаг срабатывает один раз; `None` — шага нет или он истёк."""
        async with self._db().write() as session:
            pending = await self._pending(session, txn)
            if pending is None:
                return None
            data = dict(pending.data)
            await session.delete(pending)
            if not allow:
                return construct_redirect_uri(data["redirect_uri"], error="access_denied", state=data["state"])
            code = new_token()
            session.add(
                OAuthCode(
                    code_hash=hash_token(code), client_id=data["client_id"], expires_at=utcnow() + CODE_TTL,
                    data={key: data[key] for key in CODE_FIELDS},
                )
            )
        return construct_redirect_uri(data["redirect_uri"], code=code, state=data["state"])

    # --- коды ---

    async def load_authorization_code(
        self, client: OAuthClientInformationFull, authorization_code: str
    ) -> AuthorizationCode | None:
        async with self._db().read() as session:
            row = await session.get(OAuthCode, hash_token(authorization_code))
        if row is None or row.client_id != client.client_id or row.expires_at <= utcnow():
            return None
        return AuthorizationCode(
            code=authorization_code, client_id=row.client_id, expires_at=row.expires_at.timestamp(),
            scopes=row.data["scopes"], code_challenge=row.data["code_challenge"],
            redirect_uri=row.data["redirect_uri"],
            redirect_uri_provided_explicitly=row.data["redirect_uri_provided_explicitly"],
            resource=row.data.get("resource"), subject=OWNER,
        )

    async def exchange_authorization_code(
        self, client: OAuthClientInformationFull, authorization_code: AuthorizationCode
    ) -> IssuedToken:
        async with self._db().write() as session:
            # Код сгорает при обмене: из двух обменов одного кода выигрывает один.
            gone = await session.execute(
                delete(OAuthCode).where(OAuthCode.code_hash == hash_token(authorization_code.code))
            )
            issued = (
                self._issue(session, client.client_id, authorization_code.scopes, authorization_code.resource)
                if gone.rowcount
                else None
            )
        # Отказ — за пределами `write()`: `TokenError` в mcp 2 — замороженный dataclass, а contextlib
        # при выходе из блока присваивает исключению `__traceback__` и падает с FrozenInstanceError.
        if issued is None:
            raise TokenError("invalid_grant", "authorization code not found or already used")
        return issued

    # --- токены ---

    @staticmethod
    def _issue(session: AsyncSession, client_id: str, scopes: list[str], resource: str | None) -> IssuedToken:
        now, pair = utcnow(), new_token()
        access, refresh = new_token(), new_token()
        for token, kind, ttl in ((access, "access", ACCESS_TTL), (refresh, "refresh", REFRESH_TTL)):
            session.add(
                OAuthToken(
                    token_hash=hash_token(token), kind=kind, pair_id=pair, client_id=client_id,
                    scopes=list(scopes), resource=resource, expires_at=now + ttl,
                )
            )
        return IssuedToken(
            access_token=access, token_type="Bearer", expires_in=int(ACCESS_TTL.total_seconds()),
            refresh_token=refresh, scope=" ".join(scopes) or None,
        )

    @staticmethod
    async def _live(session: AsyncSession, token: str, kind: str) -> OAuthToken | None:
        row = (
            await session.scalars(
                select(OAuthToken).where(OAuthToken.token_hash == hash_token(token), OAuthToken.kind == kind)
            )
        ).first()
        return row if row is not None and row.expires_at > utcnow() else None

    async def load_access_token(self, token: str) -> AccessToken | None:  # type: ignore[override]
        async with self._db().read() as session:
            row = await self._live(session, token, "access")
        if row is None:
            return None
        return AccessToken(
            token=token, client_id=row.client_id, scopes=list(row.scopes), expires_at=_epoch(row.expires_at),
            resource=row.resource, subject=OWNER, claims={},
        )

    async def load_refresh_token(self, client: OAuthClientInformationFull, refresh_token: str) -> RefreshToken | None:
        async with self._db().read() as session:
            row = await self._live(session, refresh_token, "refresh")
        if row is None or row.client_id != client.client_id:
            return None
        return RefreshToken(
            token=refresh_token, client_id=row.client_id, scopes=list(row.scopes),
            expires_at=_epoch(row.expires_at), resource=row.resource, subject=OWNER,
        )

    async def exchange_refresh_token(
        self, client: OAuthClientInformationFull, refresh_token: RefreshToken, scopes: list[str]
    ) -> IssuedToken:
        if not set(scopes) <= set(refresh_token.scopes):
            raise TokenError("invalid_scope", "requested scopes exceed those authorized by the refresh token")
        issued = None
        async with self._db().write() as session:
            row = await self._live(session, refresh_token.token, "refresh")
            if row is not None:
                # Вращение: пара уходит целиком, старый refresh-токен не повторить.
                await session.execute(delete(OAuthToken).where(OAuthToken.pair_id == row.pair_id))
                issued = self._issue(session, client.client_id, scopes, row.resource)
        # Отказ — за пределами `write()`, по той же причине, что и в обмене кода.
        if issued is None:
            raise TokenError("invalid_grant", "refresh token not found or already used")
        return issued

    async def revoke_token(self, token: AccessToken | RefreshToken) -> None:
        async with self._db().write() as session:
            row = await session.get(OAuthToken, hash_token(token.token))
            if row is not None:
                await session.execute(delete(OAuthToken).where(OAuthToken.pair_id == row.pair_id))
