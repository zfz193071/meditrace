"""Authenticated read-only entitlement information and shared upload limits."""
from datetime import timedelta
from uuid import UUID, uuid4

import sqlalchemy as sa

from referral_review.persistence import models as m
from test_identity import auth_client, sign_in
from test_packets import workspace, create, upload


def test_membership_requires_auth_and_does_not_accept_frontend_entitlements(auth_client):
    client, identity, clock, _ = auth_client
    assert client.get("/membership").status_code == 401
    sign_in(client)
    response = client.get("/membership?owner_id=other&member=true&real_ai_allowed=true")
    assert response.status_code == 200
    assert response.json() == dict(environment="test", valid_until=None, remaining=0, reserved=0, real_ai_allowed=False)
    assert response.headers["cache-control"] == "private, no-store"
    assert client.post("/membership", json={"granted_units": 999}).status_code == 405


def test_membership_scoped_to_session_and_expiry_keeps_editing_available(workspace):
    client, identity, clock, transport, headers = workspace
    packet = create(workspace).json()
    owner = UUID(client.get("/auth/session").json()["user"]["id"])
    order = uuid4()
    with identity.engine.begin() as conn:
        conn.execute(m.orders.insert().values(id=order, owner_id=owner, environment="test", price_id="synthetic",
            amount=100, currency="usd", state="paid", created_at=clock[0], paid_at=clock[0]))
        conn.execute(m.memberships.insert().values(owner_id=owner, source_order_id=order, environment="test",
            valid_from=clock[0], valid_until=clock[0] + timedelta(minutes=1), granted_units=20,
            reserved_units=2, consumed_units=3))
    assert client.get("/membership").json()["remaining"] == 15
    assert client.get("/membership").json()["real_ai_allowed"] is False
    clock[0] += timedelta(minutes=2)
    assert client.get("/membership").json()["remaining"] == 0
    assert client.patch(f"/packets/{packet['id']}", json={"title": "Still editable"},
        headers=headers | {"Idempotency-Key": uuid4().hex}).status_code == 200
    client.app.state.usage.check_export(client.cookies.get(identity.session_cookie), UUID(packet["id"]))
    transport.subject = 999
    sign_in(client)
    assert client.get("/membership").json()["remaining"] == 0


def test_upload_attempt_rate_is_shared_and_rollback_does_not_erase_it(workspace):
    client, identity, clock, _, headers = workspace
    pid = create(workspace).json()["id"]
    # Unsupported text is rejected after reservation; even failures consume attempts.
    for _ in range(10):
        response = client.post(f"/packets/{pid}/documents", json={"text": ""},
            headers=headers | {"Idempotency-Key": uuid4().hex})
        assert response.status_code == 422
    response = client.post(f"/packets/{pid}/documents", json={"text": "Synthetic"},
        headers=headers | {"Idempotency-Key": uuid4().hex})
    assert response.status_code == 429
    clock[0] += timedelta(minutes=1)
    upload(workspace, pid)
