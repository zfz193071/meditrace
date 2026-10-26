"""Exercise identity through HTTP and the shared owner Interface, offline only."""

from fastapi.testclient import TestClient
from urllib.parse import parse_qs, urlsplit

import pytest

from referral_review.app import create_app
from referral_review.config import Settings


def test_unconfigured_auth_is_anonymous_and_sign_in_fails_closed():
    with TestClient(create_app(Settings())) as client:
        response = client.get("/auth/session")
        assert response.status_code == 200
        assert response.json() == {
            "user": None, "csrf_token": None, "expires_at": None, "login_available": False,
        }
        assert client.get("/auth/github/start", follow_redirects=False).status_code == 503


@pytest.fixture(params=["https://referral.example.test", "http://127.0.0.1:3000"])
def auth_client(tmp_path, request):
    import base64
    import json
    from datetime import datetime, timezone
    from requests import Response
    from requests.adapters import BaseAdapter
    from referral_review.identity.service import Identity
    from referral_review.identity.github import GitHubOAuth
    from referral_review.persistence.database import create_engine
    from referral_review.persistence.migrations import HEAD, upgrade

    origin = request.param

    class GitHubTransport(BaseAdapter):
        subject = 12345
        fail = False
        token_calls = 0

        def send(self, request, **kwargs):
            if self.fail:
                raise RuntimeError("provider-token-sentinel client-secret-sentinel")
            response = Response()
            response.status_code = 200
            response.request = request
            response.url = request.url
            if request.url == "https://github.com/login/oauth/access_token":
                self.token_calls += 1
                posted = parse_qs(request.body)
                assert posted["client_secret"] == ["client-secret-sentinel"]
                assert len(posted["code_verifier"][0]) == 43
                assert posted["redirect_uri"] == [origin + "/api/v1/auth/github/callback"]
                data = {"access_token": "provider-token-sentinel", "token_type": "bearer", "scope": ""}
            elif request.url == "https://api.github.com/user":
                assert request.headers["Authorization"] == "Bearer provider-token-sentinel"
                data = {"id": self.subject, "login": "synthetic-developer", "name": "Synthetic Developer"}
            else:
                raise AssertionError("Unexpected provider URL")
            response._content = json.dumps(data).encode()
            response.headers["Content-Type"] = "application/json"
            return response

        def close(self):
            pass

    clock = [datetime(2026, 10, 20, tzinfo=timezone.utc)]
    engine = create_engine(f"sqlite:///{tmp_path / 'identity.db'}")
    with engine.begin() as connection:
        upgrade(connection, HEAD)
    settings = Settings(RR_ENVIRONMENT="test", RR_MODE="sandbox",
        RR_SITE_ORIGIN=origin,
        RR_GITHUB_CLIENT_ID="synthetic-client",
        RR_GITHUB_CLIENT_SECRET="client-secret-sentinel",
        RR_GITHUB_CALLBACK_URL=origin + "/api/v1/auth/github/callback",
        RR_SESSION_ENCRYPTION_KEY=base64.urlsafe_b64encode(b"k" * 32).decode())
    transport = GitHubTransport()
    identity = Identity(engine, settings, github=GitHubOAuth(settings, http_adapter=transport),
                        clock=lambda: clock[0])
    with TestClient(create_app(settings, identity=identity),
                    base_url=origin, follow_redirects=False) as client:
        yield client, identity, clock, transport
    engine.dispose()


def sign_in(client, return_path="/workspace"):
    started = client.get("/auth/github/start", params={"return_path": return_path})
    assert started.status_code == 302
    query = parse_qs(urlsplit(started.headers["location"]).query)
    assert query["code_challenge_method"] == ["S256"]
    assert "repo" not in query.get("scope", [""])[0]
    return client.get("/auth/github/callback", params={"state": query["state"][0], "code": "synthetic-code"})


def test_github_login_creates_a_private_session_and_returns_to_safe_page(auth_client):
    client, _, _, _ = auth_client
    completed = sign_in(client)
    assert completed.status_code == 303 and completed.headers["location"] == "/workspace"
    assert "HttpOnly" in completed.headers["set-cookie"]
    assert ("Secure" in completed.headers["set-cookie"]) == str(client.base_url).startswith("https:")
    session = client.get("/auth/session")
    body = session.json()
    assert body["user"]["display_name"] == "Synthetic Developer"
    assert body["csrf_token"] and body["expires_at"] == "2026-10-27T00:00:00Z"
    assert session.headers["cache-control"] == "private, no-store"
    assert "provider-token-sentinel" not in session.text
    assert "client-secret-sentinel" not in session.text


def test_github_issuer_callback_completes_real_provider_response_shape(auth_client):
    client, _, _, transport = auth_client
    started = client.get("/auth/github/start")
    state = parse_qs(urlsplit(started.headers["location"]).query)["state"][0]
    response = client.get("/auth/github/callback", params={"state": state,
        "code": "synthetic-code", "iss": "https://github.com/login/oauth"})
    assert response.headers["location"] == "/workspace"
    assert client.get("/auth/session").json()["user"] is not None
    assert transport.token_calls == 1


@pytest.mark.parametrize("issuers", [
    ["https://evil.example"], ["https://github.com"],
    ["https://github.com/login/oauth/"], ["http://github.com/login/oauth"], [""],
    ["https://github.com/login/oauth", "https://github.com/login/oauth"],
])
def test_untrusted_or_duplicate_issuer_never_reaches_token_exchange(auth_client, issuers):
    client, _, _, transport = auth_client
    started = client.get("/auth/github/start")
    state = parse_qs(urlsplit(started.headers["location"]).query)["state"][0]
    response = client.get("/auth/github/callback", params=[("state", state),
        ("code", "synthetic-code"), *(("iss", issuer) for issuer in issuers)])
    assert response.headers["location"] == "/login?error=oauth_failed"
    assert client.get("/auth/session").json()["user"] is None
    assert transport.token_calls == 0


def test_logout_requires_origin_and_csrf_then_revokes_the_session(auth_client):
    client, identity, _, _ = auth_client
    sign_in(client)
    token = client.cookies.get(identity.session_cookie)
    csrf = client.get("/auth/session").json()["csrf_token"]
    assert client.post("/auth/logout").status_code == 403
    assert client.post("/auth/logout", headers={
        "Origin": "https://evil.example", "X-CSRF-Token": csrf,
    }).status_code == 403
    assert client.post("/auth/logout", headers={
        "Origin": str(client.base_url).rstrip("/"), "X-CSRF-Token": csrf,
    }).status_code == 204
    client.cookies.set(identity.session_cookie, token)
    assert client.get("/auth/session").json()["user"] is None


def test_require_owner_rejects_another_account_and_hides_existence(auth_client):
    from datetime import timedelta
    from uuid import UUID, uuid4
    from fastapi import Request
    from referral_review.persistence import models as m
    from referral_review.identity.authorization import require_owner

    client, identity, clock, transport = auth_client
    sign_in(client)
    owner_id = UUID(client.get("/auth/session").json()["user"]["id"])
    packet_id = uuid4()
    # Arrange a fixture owned by the first signed-in account.
    with identity.engine.begin() as conn:
        conn.execute(m.packets.insert().values(id=packet_id, owner_id=owner_id, title="Synthetic",
            created_at=clock[0], updated_at=clock[0], expires_at=clock[0] + timedelta(days=7)))

    @client.app.get("/test-packets/{packet_id}")
    def read_packet(request: Request, packet_id: UUID):
        with identity.engine.begin() as conn:
            packet = require_owner(request, conn, packet_id)
            return {"id": str(packet["id"])}

    assert client.get(f"/test-packets/{packet_id}").json() == {"id": str(packet_id)}
    client.cookies.clear()
    transport.subject = 67890
    sign_in(client)
    forged = client.get(f"/test-packets/{packet_id}", headers={"X-User-ID": str(owner_id)})
    missing = client.get(f"/test-packets/{uuid4()}")
    assert forged.status_code == missing.status_code == 404
    assert forged.json()["error"] == missing.json()["error"]
    client.cookies.clear()
    assert client.get(f"/test-packets/{packet_id}").status_code == 401


def test_new_mutation_routes_are_csrf_protected_by_default_and_session_is_same_origin(auth_client):
    client, _, _, _ = auth_client

    @client.app.post("/test-mutation")
    def mutate():
        return {"accepted": True}

    assert client.post("/test-mutation", headers={"X-User-ID": "forged"}).status_code == 401
    sign_in(client)
    assert client.post("/test-mutation").status_code == 403
    assert client.get("/auth/session", headers={"Origin": "https://evil.example"}).status_code == 403
    csrf = client.get("/auth/session").json()["csrf_token"]
    assert client.post("/test-mutation", headers={
        "Origin": str(client.base_url).rstrip("/"), "X-CSRF-Token": csrf,
    }).json() == {"accepted": True}
    # Webhook-looking URLs do not acquire a blanket exemption.
    @client.app.post("/billing/webhook/other")
    def placeholder_webhook():
        return {"accepted": True}
    assert client.post("/billing/webhook/other").status_code == 403
    assert client.post("/billing/webhook").status_code == 503  # exact route: billing disabled, never a placeholder grant


@pytest.mark.parametrize("path", [
    "https://evil.example", "//evil.example", "/\\evil.example", "/workspace?patient=secret",
    "/workspace#fragment", "/workspace/../account", "/workspace%2f..", "/auth/logout",
    "/workspace\n", "/workspace/packets/not-a-uuid",
])
def test_login_rejects_unsafe_return_paths(auth_client, path):
    client, _, _, _ = auth_client
    response = client.get("/auth/github/start", params={"return_path": path})
    assert response.status_code == 422 and "location" not in response.headers
    assert "secret" not in response.text


@pytest.mark.parametrize("attack", ["missing_nonce", "wrong_nonce", "wrong_state", "expired",
                                   "denied", "duplicate", "forged_subject", "provider_failure"])
def test_invalid_callback_never_creates_a_session(auth_client, attack, caplog):
    from datetime import timedelta

    client, identity, clock, transport = auth_client
    started = client.get("/auth/github/start")
    state = parse_qs(urlsplit(started.headers["location"]).query)["state"][0]
    params = [("state", state), ("code", "synthetic-code")]
    if attack == "missing_nonce":
        client.cookies.clear()
    elif attack == "wrong_nonce":
        client.cookies.clear()
        client.cookies.set(identity.nonce_cookie, "x" * 43)
    elif attack == "wrong_state":
        params[0] = ("state", "x" * 43)
    elif attack == "expired":
        clock[0] += timedelta(minutes=10)
    elif attack == "denied":
        params = [("state", state), ("error", "access_denied"),
                  ("error_description", "client-secret-sentinel")]
    elif attack == "duplicate":
        params.append(("state", "x" * 43))
    elif attack == "forged_subject":
        params.append(("user_id", "12345"))
    elif attack == "provider_failure":
        transport.fail = True
    response = client.get("/auth/github/callback", params=params)
    assert response.status_code == 303
    assert response.headers["location"] == "/login?error=oauth_failed"
    assert client.get("/auth/session").json()["user"] is None
    assert "provider-token-sentinel" not in response.text + caplog.text
    # Application logs must not record provider exception bodies.
    app_logs = " ".join(r.getMessage() for r in caplog.records if r.name.startswith("meditrace"))
    assert "client-secret-sentinel" not in app_logs


def test_callback_replay_cannot_mint_a_second_session(auth_client):
    client, identity, _, _ = auth_client
    start = client.get("/auth/github/start")
    state = parse_qs(urlsplit(start.headers["location"]).query)["state"][0]
    nonce = client.cookies.get(identity.nonce_cookie)
    params = {"state": state, "code": "synthetic-code"}
    assert client.get("/auth/github/callback", params=params).headers["location"] == "/workspace"
    client.cookies.clear()
    client.cookies.set(identity.nonce_cookie, nonce)
    assert client.get("/auth/github/callback", params=params).headers["location"] == "/login?error=oauth_failed"
    assert client.get("/auth/session").json()["user"] is None


def test_login_rotates_session_without_changing_stable_account_id(auth_client):
    client, identity, _, _ = auth_client
    sign_in(client)
    original = client.cookies.get(identity.session_cookie)
    user = client.get("/auth/session").json()["user"]
    sign_in(client, "/account")
    assert original != client.cookies.get(identity.session_cookie)
    assert client.get("/auth/session").json()["user"]["id"] == user["id"]
    client.cookies.clear()
    client.cookies.set(identity.session_cookie, original)
    assert client.get("/auth/session").json()["user"] is None


def test_session_expires_after_seven_days_without_sliding_renewal(auth_client):
    from datetime import timedelta

    client, _, clock, _ = auth_client
    sign_in(client)
    clock[0] += timedelta(days=6)
    assert client.get("/auth/session").json()["user"] is not None
    clock[0] += timedelta(days=1)
    assert client.get("/auth/session").json()["user"] is None
    assert client.post("/auth/logout").status_code == 401


def test_disabled_account_loses_session_and_cannot_sign_in_again(auth_client):
    from uuid import UUID
    from referral_review.persistence import models as m

    client, identity, clock, _ = auth_client
    sign_in(client)
    user_id = UUID(client.get("/auth/session").json()["user"]["id"])
    # Arrange the account-disabled state which MT-18 will set.
    with identity.engine.begin() as conn:
        conn.execute(m.users.update().where(m.users.c.id == user_id).values(disabled_at=clock[0]))
    assert client.get("/auth/session").json()["user"] is None
    assert sign_in(client).headers["location"] == "/login?error=oauth_failed"


@pytest.mark.parametrize("subject", ["12345", None, True, -1, 0])
def test_provider_identity_requires_a_positive_numeric_subject(auth_client, subject):
    client, _, _, transport = auth_client
    transport.subject = subject
    assert sign_in(client).headers["location"] == "/login?error=oauth_failed"
    assert client.get("/auth/session").json()["user"] is None


def test_unknown_packet_return_target_falls_back_without_leaking_ownership(auth_client):
    from uuid import uuid4

    client, _, _, _ = auth_client
    assert sign_in(client, f"/workspace/packets/{uuid4()}").headers["location"] == "/workspace"


def test_mounted_auth_keeps_cookie_path_and_csrf_checks(auth_client):
    from fastapi import FastAPI
    client, identity, _, _ = auth_client
    parent = FastAPI()
    parent.mount("/api/v1", create_app(identity.settings, identity=identity))
    with TestClient(parent, base_url=identity.settings.site_origin, follow_redirects=False) as mounted:
        started = mounted.get("/api/v1/auth/github/start")
        state = parse_qs(urlsplit(started.headers["location"]).query)["state"][0]
        completed = mounted.get("/api/v1/auth/github/callback", params={"state": state, "code": "synthetic-code"})
        assert "Path=/" in completed.headers["set-cookie"]
        csrf = mounted.get("/api/v1/auth/session").json()["csrf_token"]
        assert mounted.post("/api/v1/auth/logout").status_code == 403
        assert mounted.post("/api/v1/auth/logout", headers={
            "Origin": str(client.base_url).rstrip("/"), "X-CSRF-Token": csrf,
        }).status_code == 204


def test_expired_or_deleted_packet_is_hidden_from_its_owner(auth_client):
    from datetime import timedelta
    from uuid import UUID, uuid4
    from fastapi import Request
    from referral_review.identity.authorization import require_owner
    from referral_review.persistence import models as m

    client, identity, clock, _ = auth_client
    sign_in(client)
    owner = UUID(client.get("/auth/session").json()["user"]["id"])
    ids = [uuid4(), uuid4()]
    with identity.engine.begin() as conn:
        for index, packet_id in enumerate(ids):
            conn.execute(m.packets.insert().values(id=packet_id, owner_id=owner, title="Synthetic",
                created_at=clock[0] - timedelta(days=8), updated_at=clock[0],
                expires_at=clock[0] if index == 0 else clock[0] + timedelta(days=1),
                deleted_at=None if index == 0 else clock[0]))

    @client.app.get("/test-private/{packet_id}")
    def read(request: Request, packet_id: UUID):
        with identity.engine.begin() as conn:
            return {"id": str(require_owner(request, conn, packet_id)["id"])}

    for packet_id in ids:
        assert client.get(f"/test-private/{packet_id}").status_code == 404


def test_session_cookie_never_appears_in_session_json_or_application_logs(auth_client, caplog):
    client, identity, _, _ = auth_client
    sign_in(client)
    token = client.cookies.get(identity.session_cookie)
    response = client.get("/auth/session", headers={"X-User-ID": "forged-subject"})
    assert token not in response.text + caplog.text
    assert "github_subject" not in response.text and "token_hash" not in response.text
    assert response.headers["referrer-policy"] == "no-referrer"


def test_configured_postgres_auth_starts_without_connecting_or_migrating():
    import base64

    settings = Settings(RR_ENVIRONMENT="production", RR_MODE="sandbox",
        DATABASE_URL="postgresql://synthetic:synthetic@127.0.0.1:1/not_a_real_database",
        RR_SITE_ORIGIN="https://referral.example.test",
        RR_GITHUB_CLIENT_ID="synthetic", RR_GITHUB_CLIENT_SECRET="synthetic",
        RR_GITHUB_CALLBACK_URL="https://referral.example.test/api/v1/auth/github/callback",
        RR_SESSION_ENCRYPTION_KEY=base64.urlsafe_b64encode(b"k" * 32).decode())
    with TestClient(create_app(settings), base_url="https://referral.example.test") as client:
        assert client.get("/auth/session").json()["login_available"] is True
        assert client.get("/capabilities").status_code == 200
