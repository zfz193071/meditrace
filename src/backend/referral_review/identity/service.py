"""Identity Module. Transactions and OAuth details stay behind this Interface.

External provider calls occur AFTER the single-use state transaction commits.
No automatic schema creation, no callback replay, no provider retry.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
import hashlib
import re
import secrets
from urllib.parse import urlencode, urlsplit
from uuid import UUID, uuid4

from cryptography.fernet import Fernet, InvalidToken
import sqlalchemy as sa
from sqlalchemy.exc import SQLAlchemyError

from ..config import ConfigurationError
from ..errors import ApiError
from ..schemas import ErrorCode, SessionResponse, SessionUser
from ..persistence import models as m
from ..persistence.database import create_engine
from ..persistence.migrations import require_current_schema, MigrationRequired
from ..persistence.repository import owned_packet, NotFound, require_transaction
from .github import GitHubOAuth

TOKEN_PATTERN = re.compile(r"^[A-Za-z0-9_-]{43}$")
RETURN_PATTERN = re.compile(r"^/workspace/packets/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")


def now_utc():
    return datetime.now(timezone.utc)


def hashed(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def safe_return_path(value: str) -> str:
    if value not in {"/workspace", "/account"} and not RETURN_PATTERN.fullmatch(value):
        raise ApiError(ErrorCode.SCHEMA_INVALID)
    return value


@dataclass(frozen=True)
class LoginStart:
    url: str = field(repr=False)
    nonce: str = field(repr=False)


@dataclass(frozen=True)
class LoginComplete:
    token: str = field(repr=False)
    return_path: str


class Identity:
    def __init__(self, engine, settings, *, github=None, clock=now_utc):
        self.engine, self.settings, self.clock = engine, settings, clock
        self.github = github or GitHubOAuth(settings)
        try:
            self.cipher = Fernet(settings.session_encryption_key.get_secret_value())
        except (ValueError, AttributeError):
            raise ConfigurationError("RR_SESSION_ENCRYPTION_KEY must be a Fernet key") from None
        self.secure_cookie = urlsplit(settings.site_origin).scheme == "https"
        self.session_cookie = "__Host-rr_session" if self.secure_cookie else "rr_session"
        self.nonce_cookie = "__Host-rr_oauth" if self.secure_cookie else "rr_oauth"

    def start(self, return_path: str) -> LoginStart:
        path = safe_return_path(return_path)
        state, nonce, verifier = (secrets.token_urlsafe(32) for _ in range(3))
        url = self.github.authorization_url(state, verifier)
        with self.engine.begin() as conn:
            require_current_schema(conn)
            conn.execute(m.oauth_states.insert().values(
                state_hash=hashed(state), browser_nonce_hash=hashed(nonce),
                encrypted_verifier=self.cipher.encrypt(verifier.encode()).decode(),
                return_path=path, expires_at=self.clock() + timedelta(minutes=10)))
        return LoginStart(url, nonce)

    def complete(self, *, state: str, nonce: str, code: str | None,
                 denied: bool = False, old_token: str | None = None) -> LoginComplete:
        if not TOKEN_PATTERN.fullmatch(state or "") or not TOKEN_PATTERN.fullmatch(nonce or ""):
            raise ApiError(ErrorCode.OAUTH_FAILED)
        now = self.clock()
        with self.engine.begin() as conn:
            require_current_schema(conn)
            row = conn.execute(sa.update(m.oauth_states).where(
                m.oauth_states.c.state_hash == hashed(state),
                m.oauth_states.c.browser_nonce_hash == hashed(nonce),
                m.oauth_states.c.consumed_at.is_(None), m.oauth_states.c.expires_at > now,
            ).values(consumed_at=now).returning(m.oauth_states)).mappings().first()
        # A committed state claim cannot be replayed even after network failure.
        if row is None or denied or not code or len(code) > 1024:
            raise ApiError(ErrorCode.OAUTH_FAILED)
        try:
            verifier = self.cipher.decrypt(row["encrypted_verifier"].encode()).decode()
        except InvalidToken:
            raise ApiError(ErrorCode.OAUTH_FAILED) from None
        authority = self.github.identify(state=state, verifier=verifier,
            authorization_response=self.settings.github_callback_url + "?" + urlencode({"state": state, "code": code}))
        token, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
        # Use the stable provider subject, never request headers/JSON/login handle.
        with self.engine.begin() as conn:
            from sqlalchemy.dialects.postgresql import insert as pg_insert
            from sqlalchemy.dialects.sqlite import insert as sqlite_insert
            insert = pg_insert if conn.dialect.name == "postgresql" else sqlite_insert
            conn.execute(insert(m.users).values(id=uuid4(), github_subject=authority.subject,
                display_name=authority.display_name, created_at=now).on_conflict_do_nothing(
                    index_elements=[m.users.c.github_subject]))
            user = conn.execute(sa.select(m.users).where(
                m.users.c.github_subject == authority.subject).with_for_update()).mappings().one()
            if user["disabled_at"] is not None:
                raise ApiError(ErrorCode.OAUTH_FAILED)
            conn.execute(sa.update(m.users).where(m.users.c.id == user["id"]).values(display_name=authority.display_name))
            if old_token and TOKEN_PATTERN.fullmatch(old_token):
                conn.execute(sa.update(m.sessions).where(m.sessions.c.token_hash == hashed(old_token),
                    m.sessions.c.revoked_at.is_(None)).values(revoked_at=now))
            conn.execute(m.sessions.insert().values(user_id=user["id"], token_hash=hashed(token),
                csrf_secret=csrf, expires_at=now + timedelta(days=7)))
            path = safe_return_path(row["return_path"])
            if path.startswith("/workspace/packets/"):
                packet_id = UUID(path.rsplit("/", 1)[1])
                owned = conn.execute(sa.select(m.packets.c.id).where(
                    m.packets.c.id == packet_id, m.packets.c.owner_id == user["id"],
                    m.packets.c.deleted_at.is_(None), m.packets.c.expires_at > now)).first()
                if not owned:
                    path = "/workspace"
        return LoginComplete(token, path)

    def session(self, token: str | None) -> SessionResponse:
        if not token or not TOKEN_PATTERN.fullmatch(token):
            return SessionResponse(login_available=True)
        with self.engine.begin() as conn:
            require_current_schema(conn)
            row = conn.execute(sa.select(m.sessions, m.users.c.display_name).join(m.users).where(
                m.sessions.c.token_hash == hashed(token), m.sessions.c.revoked_at.is_(None),
                m.sessions.c.expires_at > self.clock(), m.users.c.disabled_at.is_(None))).mappings().first()
        if row is None:
            return SessionResponse(login_available=True)
        return SessionResponse(user=SessionUser(id=row["user_id"], display_name=row["display_name"]),
            csrf_token=row["csrf_secret"], expires_at=row["expires_at"], login_available=True)

    def require_mutation(self, request) -> SessionResponse:
        session = self.session(request.cookies.get(self.session_cookie))
        if session.user is None:
            raise ApiError(ErrorCode.AUTH_REQUIRED)
        origins = request.headers.getlist("origin")
        tokens = request.headers.getlist("x-csrf-token")
        if (origins != [self.settings.site_origin] or len(tokens) != 1
            or not TOKEN_PATTERN.fullmatch(tokens[0])
            or not secrets.compare_digest(tokens[0], session.csrf_token)):
            raise ApiError(ErrorCode.FORBIDDEN)
        return session

    def logout(self, token: str):
        with self.engine.begin() as conn:
            conn.execute(sa.update(m.sessions).where(
                m.sessions.c.token_hash == hashed(token), m.sessions.c.revoked_at.is_(None),
            ).values(revoked_at=self.clock()))

    def require_owner(self, connection, token: str | None, packet_id: UUID):
        """Call in the SAME transaction as the protected read/write.

        Locks user then session then packet; future child queries must constrain
        their packet_id to the returned packet, never trust a caller's owner ID.
        """
        require_transaction(connection)
        if not token or not TOKEN_PATTERN.fullmatch(token):
            raise ApiError(ErrorCode.AUTH_REQUIRED)
        now = self.clock()
        condition = (
            (m.sessions.c.token_hash == hashed(token)) & m.sessions.c.revoked_at.is_(None)
            & (m.sessions.c.expires_at > now)
        )
        user_id = connection.execute(sa.select(m.sessions.c.user_id).where(condition)).scalar_one_or_none()
        if user_id is None:
            raise ApiError(ErrorCode.AUTH_REQUIRED)
        user = connection.execute(sa.select(m.users.c.id).where(
            m.users.c.id == user_id, m.users.c.disabled_at.is_(None)).with_for_update()).first()
        session = connection.execute(sa.select(m.sessions.c.id).where(condition).with_for_update()).first()
        if user is None or session is None:
            raise ApiError(ErrorCode.AUTH_REQUIRED)
        try:
            return owned_packet(connection, user_id, packet_id, now, lock=True)
        except NotFound:
            raise ApiError(ErrorCode.NOT_FOUND) from None


def configured_identity(settings):
    """No connection until first use, no schema writes during application startup."""
    if settings.mode == "bundled_demo" or not all((
        settings.database_url, settings.site_origin, settings.github_client_id,
        settings.github_client_secret, settings.github_callback_url, settings.session_encryption_key,
    )):
        return None
    return Identity(create_engine(settings.database_url.get_secret_value()), settings)


DATABASE_FAILURES = (SQLAlchemyError, MigrationRequired)
