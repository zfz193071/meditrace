"""Concurrent webhook processing against isolated PostgreSQL; Fake provider only."""
from datetime import datetime, timedelta, timezone
import base64
import multiprocessing
import os
from uuid import uuid4

import pytest
import sqlalchemy as sa
from pydantic import SecretStr

from referral_review.billing import Billing
from referral_review.config import Settings
from referral_review.identity.service import Identity
from referral_review.persistence import models as m
from referral_review.persistence.database import create_engine
from referral_review.persistence.migrations import HEAD, upgrade
from referral_review.persistence.test_database import isolated_database, test_url as configured_test_url

NOW = datetime(2026, 10, 20, tzinfo=timezone.utc)
_BARRIER = None


def initialize(barrier):
    global _BARRIER
    _BARRIER = barrier


class FakeStripe:
    def __init__(self, session):
        self.session = session

    def resolve(self, kind, _object_id):
        result = dict(self.session)
        result["payment_intent"] = dict(self.session["payment_intent"])
        result["payment_intent"]["latest_charge"] = dict(self.session["payment_intent"]["latest_charge"])
        if kind == "charge.refunded":
            result["payment_intent"]["latest_charge"]["amount_refunded"] = 1
        return result


def process(payload):
    url, schema, event_id, session = payload
    engine = create_engine(url, schema=schema)
    try:
        settings = Settings(RR_ENVIRONMENT="test", RR_MODE="sandbox", RR_SITE_ORIGIN="https://example.test",
            RR_SESSION_ENCRYPTION_KEY=SecretStr(base64.urlsafe_b64encode(b"k" * 32).decode()),
            RR_STRIPE_SECRET_KEY="sk_test_synthetic",
            RR_STRIPE_WEBHOOK_SECRET="whsec_synthetic", RR_STRIPE_PRICE_ID="price_synthetic",
            RR_STRIPE_AMOUNT_MINOR=500, RR_STRIPE_CURRENCY="usd")
        service = Billing(Identity(engine, settings, clock=lambda: NOW), provider=FakeStripe(session))
        _BARRIER.wait(timeout=20)
        service.process_event(event_id)
        return "success"
    finally:
        engine.dispose()


@pytest.fixture
def pg():
    if not os.getenv("TEST_DATABASE_URL"):
        pytest.skip("TEST_DATABASE_URL missing; PostgreSQL webhook races not verified")
    with isolated_database(configured_test_url()) as engine:
        with engine.begin() as conn:
            upgrade(conn, HEAD)
        yield engine


def graph(engine):
    owner, order = uuid4(), uuid4()
    session_id = "cs_test_" + order.hex
    payment_id = "pi_" + order.hex
    session = dict(id=session_id, livemode=False, mode="payment", client_reference_id=str(order),
        metadata={"order_id": str(order)}, amount_total=500, currency="usd", verified_price_id="price_synthetic",
        url="https://checkout.stripe.com/c/pay/" + session_id, status="complete", payment_status="paid",
        payment_intent=dict(id=payment_id, livemode=False, amount=500, currency="usd",
            metadata={"order_id": str(order)}, status="succeeded",
            latest_charge=dict(id="ch_test_" + order.hex, payment_intent=payment_id, livemode=False,
                paid=True, amount_refunded=0, disputed=False)))
    with engine.begin() as conn:
        conn.execute(m.users.insert().values(id=owner, github_subject=str(owner), display_name="Synthetic", created_at=NOW))
        conn.execute(m.orders.insert().values(id=order, owner_id=owner, environment="test", price_id="price_synthetic",
            amount=500, currency="usd", state="pending", created_at=NOW, checkout_session_id=session_id))
        conn.execute(m.checkout_details.insert().values(order_id=order, return_path="/account",
            expires_at=NOW + timedelta(minutes=31), checkout_url="https://checkout.stripe.com/c/pay/" + session_id))
    return order, session


def race(engine, session, event_ids):
    with engine.connect() as conn:
        schema = conn.execute(sa.text("SELECT current_schema()")).scalar_one()
    with engine.begin() as conn:
        for event_id, kind, object_id in event_ids:
            conn.execute(m.billing_events.insert().values(stripe_event_id=event_id, event_type=kind,
                object_id=object_id, state="pending", received_at=NOW))
    context = multiprocessing.get_context("spawn")
    barrier = context.Barrier(len(event_ids))
    with context.Pool(len(event_ids), initializer=initialize, initargs=(barrier,)) as pool:
        payloads = [(engine.url.render_as_string(hide_password=False), schema, event_id, session)
                    for event_id, _, _ in event_ids]
        return pool.map_async(process, payloads).get(timeout=60)


def state(engine):
    with engine.begin() as conn:
        order = dict(conn.execute(sa.select(m.orders)).mappings().one())
        members = [dict(row) for row in conn.execute(sa.select(m.memberships)).mappings()]
        events = [dict(row) for row in conn.execute(sa.select(m.billing_events)).mappings()]
    return order, members, events


def test_concurrent_distinct_paid_events_grant_one_membership(pg):
    order, session = graph(pg)
    events = [(f"evt_paid_{i}", "checkout.session.completed", session["id"]) for i in range(4)]
    assert race(pg, session, events) == ["success"] * 4
    current, members, stored = state(pg)
    assert current["id"] == order and current["state"] == "paid"
    assert len(members) == 1 and members[0]["source_order_id"] == order and members[0]["granted_units"] == 20
    assert {event["state"] for event in stored} == {"processed"}


def test_concurrent_refund_and_paid_event_never_reactivate_entitlement(pg):
    order, session = graph(pg)
    events = [("evt_paid", "checkout.session.completed", session["id"]),
              ("evt_refund", "charge.refunded", session["payment_intent"]["latest_charge"]["id"])]
    assert race(pg, session, events) == ["success", "success"]
    current, members, stored = state(pg)
    assert current["id"] == order and current["state"] == "refunded"
    assert len(members) <= 1
    assert all(member["revoked_at"] is not None for member in members)
    assert {event["state"] for event in stored} == {"processed"}
