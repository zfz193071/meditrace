"""Offline signed events and provider failures; never performs a Stripe purchase."""
import copy
import hashlib
import hmac
import json
from datetime import timedelta
from uuid import uuid4

import httpx
import pytest
import sqlalchemy as sa

from referral_review.billing import Billing
from referral_review.billing.provider import StripeTest, verify_event
from referral_review.errors import ApiError
from referral_review.persistence import models as m
from referral_review.schemas import ErrorCode
from test_identity import auth_client, sign_in


class Provider:
    def __init__(self):
        self.sessions = {}
        self.creates = []
        self.fail = False
        self.lose_response = False

    def create(self, order, detail):
        self.creates.append(order["id"])
        sid = "cs_test_" + order["id"].hex
        self.sessions.setdefault(sid, dict(id=sid, livemode=False, mode="payment", client_reference_id=str(order["id"]),
            metadata={"order_id": str(order["id"])}, amount_total=order["amount"], currency=order["currency"],
            verified_price_id=order["price_id"], url="https://checkout.stripe.com/c/pay/" + sid,
            status="open", payment_status="unpaid", payment_intent=None))
        if self.lose_response:
            raise ApiError(ErrorCode.PAYMENT_PENDING)
        return copy.deepcopy(self.sessions[sid])

    def session(self, sid):
        if self.fail:
            raise ApiError(ErrorCode.PAYMENT_PENDING)
        return copy.deepcopy(self.sessions[sid])

    def resolve(self, kind, object_id):
        if kind.startswith("checkout."):
            return self.session(object_id)
        return self.session(next(iter(self.sessions)))

    def paid(self, sid):
        session = self.sessions[sid]
        pi = "pi_" + session["client_reference_id"].replace("-", "")
        session.update(status="complete", payment_status="paid", payment_intent=dict(id=pi, livemode=False,
            amount=session["amount_total"], currency=session["currency"], metadata=session["metadata"], status="succeeded",
            latest_charge=dict(id="ch_test", payment_intent=pi, livemode=False, paid=True, amount_refunded=0, disputed=False)))


@pytest.fixture
def billing(auth_client):
    client, identity, clock, github = auth_client
    identity.settings = identity.settings.model_copy(update={
        "stripe_secret_key": __import__('pydantic').SecretStr("sk_test_synthetic"),
        "stripe_webhook_secret": __import__('pydantic').SecretStr("whsec_synthetic"),
        "stripe_price_id": "price_synthetic", "stripe_amount_minor": 500,
        "maintenance_token": __import__('pydantic').SecretStr("operator" * 8),
    })
    provider = Provider()
    service = Billing(identity, provider=provider)
    client.app.state.billing = service
    sign_in(client)
    csrf = client.get('/auth/session').json()['csrf_token']
    headers = {'origin': identity.settings.site_origin, 'x-csrf-token': csrf, 'idempotency-key': 'checkout-key-1'}
    return client, service, provider, clock, headers, github


def create(b, key='checkout-key-1', path='/workspace'):
    client, _, _, _, headers, _ = b
    return client.post('/billing/checkout', json={'return_path': path}, headers=headers | {'idempotency-key': key})


def signed(b, sid, kind='checkout.session.completed', eid='evt_one', **extra):
    _, service, _, clock, _, _ = b
    event = dict(id=eid, type=kind, created=int(clock[0].timestamp()), livemode=False,
                 data={'object': {'id': sid, 'livemode': False}})
    event.update(extra)
    raw = json.dumps(event).encode()
    t = str(int(clock[0].timestamp()))
    sig = hmac.new(service.settings.stripe_webhook_secret.get_secret_value().encode(), t.encode()+b'.'+raw, hashlib.sha256).hexdigest()
    return raw, {'stripe-signature': f't={t},v1={sig}'}


def event(b, sid, **kwargs):
    raw, headers = signed(b, sid, **kwargs)
    return b[0].post('/billing/webhook', content=raw, headers=headers)


def rows(b, table):
    with b[1].engine.begin() as conn:
        return [dict(r) for r in conn.execute(sa.select(table)).mappings()]


def test_deleted_account_rejects_late_and_duplicate_payment_events(billing):
    from referral_review.lifecycle import Lifecycle
    b = billing
    create(b)
    sid = rows(b, m.orders)[0]["checkout_session_id"]
    b[2].paid(sid)
    assert event(b, sid).status_code == 200
    assert len(rows(b, m.memberships)) == 1
    response = b[0].request("DELETE", "/account", json={"confirmation": "DELETE"}, headers=b[4])
    assert response.status_code == 202
    # Before physical cleanup the disabled user still prevents new grants.
    assert event(b, sid, eid="evt_late_before_purge").status_code in (400, 401)
    result = Lifecycle(b[1].identity).maintain()
    assert result["backlog"] == 0
    assert rows(b, m.users) == [] and rows(b, m.memberships)[0]["owner_id"] is None
    assert event(b, sid).status_code == 200  # Already-processed dedupe is harmless.
    assert event(b, sid, eid="evt_late_after_purge").status_code == 400
    sign_in(b[0])
    assert b[0].get("/membership").json()["remaining"] == 0
    assert len(rows(b, m.memberships)) == 1


def test_checkout_reuses_pending_order_and_paid_entitlement_is_exactly_once(billing):
    b = billing
    first = create(b)
    assert first.status_code == 200, first.text
    order = first.json()
    assert create(b).json() == order
    assert create(b, key='different-key').json() == order
    assert len(b[2].creates) == 1
    sid = rows(b, m.orders)[0]['checkout_session_id']
    assert event(b, sid).status_code == 200  # pending does not grant
    assert rows(b, m.memberships) == []
    b[2].paid(sid)
    for eid in ['evt_paid', 'evt_paid', 'evt_paid_again']:
        assert event(b, sid, eid=eid).status_code == 200
    member = rows(b, m.memberships)
    assert len(member) == 1 and member[0]['granted_units'] == 20
    assert member[0]['valid_until'] - member[0]['valid_from'] == timedelta(days=30)
    assert create(b, key='buy-again-key').status_code == 409
    assert b[0].get('/membership').json()['real_ai_allowed'] is False
    assert rows(b, m.runs) == []
    assert b[0].get('/billing/orders/'+order['id']).json()['state'] == 'paid'


@pytest.mark.parametrize('early', [True, False])
def test_refund_before_or_after_completion_is_monotonic(billing, early):
    b = billing; create(b)
    sid = rows(b, m.orders)[0]['checkout_session_id']; b[2].paid(sid)
    if not early:
        assert event(b, sid).status_code == 200
    b[2].sessions[sid]['payment_intent']['latest_charge']['amount_refunded'] = 1
    assert event(b, 'ch_test', kind='charge.refunded', eid='evt_refund').status_code == 200
    # Even a stale paid snapshot delivered after refund cannot resurrect membership.
    b[2].sessions[sid]['payment_intent']['latest_charge']['amount_refunded'] = 0
    assert event(b, sid, eid='evt_late').status_code == 200
    assert rows(b, m.orders)[0]['state'] == 'refunded'
    assert all(r['revoked_at'] is not None for r in rows(b, m.memberships))
    assert b[0].get('/membership').json()['remaining'] == 0


@pytest.mark.parametrize('field,value', [('amount_total', 1), ('currency', 'nzd'), ('livemode', True),
    ('verified_price_id', 'price_wrong'), ('client_reference_id', str(uuid4())), ('mode', 'subscription')])
def test_provider_state_must_match_server_order(billing, field, value):
    b = billing; create(b)
    sid = rows(b, m.orders)[0]['checkout_session_id']; b[2].paid(sid)
    b[2].sessions[sid][field] = value
    assert event(b, sid).status_code == 400
    assert rows(b, m.memberships) == []
    assert rows(b, m.billing_events)[0]['state'] == 'rejected'


def test_signed_raw_body_freshness_live_events_and_cookie_csrf(billing):
    b = billing
    assert b[0].post('/billing/checkout', json={}).status_code == 403
    assert b[0].post('/billing/checkout', json={'price': 'price_client'}, headers=b[4]).status_code == 422
    create(b); sid = rows(b, m.orders)[0]['checkout_session_id']
    raw, headers = signed(b, sid)
    assert b[0].post('/billing/webhook', content=raw+b' ', headers=headers).status_code == 400
    b[3][0] += timedelta(seconds=301)
    assert b[0].post('/billing/webhook', content=raw, headers=headers).status_code == 400
    assert event(b, sid, livemode=True).status_code == 400
    assert rows(b, m.billing_events) == []
    assert b[0].post('/internal/maintenance').status_code == 403


def test_failed_event_is_durable_and_operator_recovery_is_authenticated(billing):
    b = billing; create(b)
    sid = rows(b, m.orders)[0]['checkout_session_id']; b[2].paid(sid); b[2].fail = True
    assert event(b, sid).status_code == 503
    assert rows(b, m.billing_events)[0]['state'] == 'failed'
    b[2].fail = False
    assert b[0].post('/internal/maintenance', headers={'authorization': 'Bearer '+ 'operator'*8}).status_code == 200
    assert len(rows(b, m.memberships)) == 1
    assert event(b, sid).status_code == 200
    assert len(rows(b, m.memberships)) == 1


def test_lost_checkout_response_reuses_provider_idempotency_order(billing):
    b = billing; b[2].lose_response = True
    assert create(b).status_code == 503
    b[2].lose_response = False
    assert create(b).status_code == 200
    assert b[2].creates[0] == b[2].creates[1]
    assert len(rows(b, m.orders)) == 1


def test_order_ownership_safe_return_and_read_only_success_query(billing):
    b = billing
    assert create(b, path='https://evil.test').status_code == 422
    assert create(b, path='/workspace/packets/'+str(uuid4())).status_code == 404
    first = create(b).json()
    assert create(b, path='/account').status_code == 409
    assert b[0].get('/billing/orders/'+first['id']+'?paid=true').json()['state'] == 'pending'
    assert rows(b, m.memberships) == []
    b[5].subject = 45678; sign_in(b[0])
    assert b[0].get('/billing/orders/'+first['id']).status_code == 404


def test_delayed_payment_expiry_and_repurchase(billing):
    b = billing; create(b)
    sid = rows(b, m.orders)[0]['checkout_session_id']
    b[2].sessions[sid]['status'] = 'complete'
    assert event(b, sid).status_code == 200
    assert rows(b, m.memberships) == []
    b[2].paid(sid)
    assert event(b, sid, kind='checkout.session.async_payment_succeeded', eid='evt_async').status_code == 200
    b[3][0] += timedelta(days=31)
    sign_in(b[0]); b[4]['x-csrf-token'] = b[0].get('/auth/session').json()['csrf_token']
    assert create(b, key='new-period-key').status_code == 200
    assert len(rows(b, m.orders)) == 2
    assert b[0].get('/membership').json()['remaining'] == 0


def test_stripe_adapter_fixed_test_price_form_and_idempotency(billing):
    b = billing; create(b)
    order = rows(b, m.orders)[0]; detail = rows(b, m.checkout_details)[0]
    seen = []
    def transport(request):
        seen.append(request)
        if '/prices/' in str(request.url):
            return httpx.Response(200, json=dict(livemode=False, active=True, type='one_time', unit_amount=500, currency='usd'))
        return httpx.Response(200, json=b[2].sessions[order['checkout_session_id']])
    provider = StripeTest(b[1].settings, transport=httpx.MockTransport(transport))
    provider.create(order, detail)
    assert seen[1].headers['idempotency-key'] == 'rr-order-'+str(order['id'])
    from urllib.parse import parse_qs
    body = parse_qs(seen[1].content.decode())
    assert body['mode'] == ['payment'] and body['line_items[0][price]'] == ['price_synthetic']
    assert body['success_url'] == body['cancel_url']
    assert 'paid=true' not in body['success_url'][0]
    live = StripeTest(b[1].settings, transport=httpx.MockTransport(lambda _: httpx.Response(200,
        json=dict(livemode=True, active=True, type='one_time', unit_amount=500, currency='usd'))))
    with pytest.raises(ApiError, match='EVENT_REJECTED'):
        live.create(order, detail)


def test_transaction_failure_rolls_back_grant_and_event_is_retryable(billing):
    b = billing; create(b)
    sid = rows(b, m.orders)[0]['checkout_session_id']; b[2].paid(sid)
    with b[1].engine.begin() as conn:
        conn.exec_driver_sql("CREATE TRIGGER fail_event BEFORE UPDATE ON rr_billing_events WHEN NEW.state='processed' BEGIN SELECT RAISE(ABORT, 'synthetic failure'); END")
    assert event(b, sid).status_code == 503
    assert rows(b, m.memberships) == []
    assert rows(b, m.orders)[0]['state'] == 'pending'
    assert rows(b, m.billing_events)[0]['state'] == 'failed'
    with b[1].engine.begin() as conn:
        conn.exec_driver_sql('DROP TRIGGER fail_event')
    assert event(b, sid).status_code == 200
    assert len(rows(b, m.memberships)) == 1


def test_operator_recovers_ambiguous_create_without_new_order(billing):
    b = billing; b[2].lose_response = True
    assert create(b).status_code == 503
    b[2].lose_response = False
    b[3][0] += timedelta(minutes=32)
    sid = next(iter(b[2].sessions)); b[2].sessions[sid]['status'] = 'expired'
    assert b[1].recover()['processed'] == 1
    assert rows(b, m.orders)[0]['state'] == 'expired'
    assert len(set(b[2].creates)) == 1
    assert create(b, key='replacement-key').status_code == 200


def test_dispute_closure_never_reactivates_and_event_id_cannot_change_object(billing):
    b = billing; create(b)
    sid = rows(b, m.orders)[0]['checkout_session_id']; b[2].paid(sid)
    assert event(b, 'dp_test', kind='charge.dispute.created').status_code == 200
    assert event(b, sid, eid='evt_late_paid').status_code == 200
    assert rows(b, m.orders)[0]['state'] == 'revoked'
    assert rows(b, m.memberships) == []
    assert event(b, sid, eid='evt_one').status_code == 400


def test_payment_return_login_is_allowlisted_but_not_a_checkout_destination(billing):
    b = billing; order = create(b).json()
    path = '/account/payment?order='+order['id']
    assert sign_in(b[0], path).headers['location'] == path
    assert b[0].get('/auth/github/start', params={'return_path': path+'&next=https://evil.test'}).status_code == 422
