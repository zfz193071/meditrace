"""Order/user locks, durable event retries and monotonic revocation. Network outside transactions."""
from datetime import timedelta
from uuid import UUID, uuid4

import sqlalchemy as sa

from ..errors import ApiError
from ..identity.service import safe_return_path
from ..packets.service import Packets
from ..persistence import models as m
from ..persistence.migrations import require_current_schema
from ..schemas import ErrorCode, OrderResponse
from ..usage.rates import ensure, lock_user, consume
from .provider import StripeTest, checkout_url, identifier, rejected, verify_event


def configured(settings):
    return bool(settings.mode != "bundled_demo" and settings.site_origin and settings.stripe_secret_key
                and settings.stripe_webhook_secret and settings.stripe_price_id and settings.stripe_amount_minor > 0)


class Billing:
    def __init__(self, identity, *, provider=None):
        self.identity, self.engine, self.clock = identity, identity.engine, identity.clock
        self.settings = identity.settings
        self.provider = provider if provider is not None else StripeTest(self.settings)
        self.packets = Packets(identity)

    def _detail(self, conn, order_id):
        return conn.execute(sa.select(m.checkout_details).where(m.checkout_details.c.order_id == order_id)).mappings().one()

    def _response(self, order, detail):
        url = detail["checkout_url"] if order["state"] == "pending" and detail["expires_at"] > self.clock() else None
        return OrderResponse(id=order["id"], state=order["state"], amount=order["amount"],
                             currency=order["currency"], return_path=detail["return_path"], checkout_url=url)

    def get(self, token, order_id):
        with self.engine.begin() as conn:
            owner = self.packets._user(conn, token)
            order = conn.execute(sa.select(m.orders).where(m.orders.c.id == order_id, m.orders.c.owner_id == owner)).mappings().first()
            if not order:
                raise ApiError(ErrorCode.NOT_FOUND)
            return self._response(order, self._detail(conn, order_id))

    def create_checkout(self, token, return_path, key):
        return_path = safe_return_path(return_path)
        if return_path.startswith("/account/payment"):
            raise ApiError(ErrorCode.SCHEMA_INVALID)
        now = self.clock()
        with self.engine.begin() as conn:
            owner = self.packets._user(conn, token)  # serializes per owner
            if return_path.startswith("/workspace/packets/"):
                self.identity.require_owner(conn, token, UUID(return_path.rsplit("/", 1)[1]))
            prior, digest = self.packets._previous(conn, owner, "checkout", key, {"return_path": return_path})
            if prior:
                order = conn.execute(sa.select(m.orders).where(m.orders.c.id == prior["resource_id"], m.orders.c.owner_id == owner)).mappings().first()
                if not order:
                    raise ApiError(ErrorCode.NOT_FOUND)
            else:
                active = conn.execute(sa.select(m.memberships.c.id).where(m.memberships.c.owner_id == owner,
                    m.memberships.c.revoked_at.is_(None), m.memberships.c.valid_until > now)).first()
                if active:
                    raise ApiError(ErrorCode.MEMBERSHIP_ACTIVE)
                order = conn.execute(sa.select(m.orders).where(m.orders.c.owner_id == owner,
                    m.orders.c.state == "pending").with_for_update()).mappings().first()
                if order and self._detail(conn, order["id"])["return_path"] != return_path:
                    raise ApiError(ErrorCode.PAYMENT_PENDING)
                if not order:
                    order = dict(id=uuid4(), owner_id=owner, environment="test", price_id=self.settings.stripe_price_id,
                        amount=self.settings.stripe_amount_minor, currency=self.settings.stripe_currency, state="pending", created_at=now,
                        checkout_session_id=None, payment_intent_id=None, paid_at=None)
                    conn.execute(m.orders.insert().values(**order))
                    conn.execute(m.checkout_details.insert().values(order_id=order["id"], return_path=return_path,
                        expires_at=now + timedelta(minutes=31)))
                self.packets._record(conn, owner, "checkout", key, digest, order["id"])
            order = dict(order)
            detail = dict(self._detail(conn, order["id"]))
        if order["state"] != "pending" or detail["checkout_url"]:
            return self._response(order, detail)
        # Never retry an ambiguous create beyond the fixed Checkout lifetime.
        if now >= order["created_at"] + timedelta(minutes=30):
            raise ApiError(ErrorCode.PAYMENT_PENDING)
        with self.engine.begin() as conn:
            consume(conn, owner, "checkout", now)
        session = self.provider.create(order, detail)
        self._validate(order, session, line_items=False)
        with self.engine.begin() as conn:
            lock_user(conn, owner)
            current = conn.execute(sa.select(m.orders).where(m.orders.c.id == order["id"]).with_for_update()).mappings().one()
            if current["checkout_session_id"] not in (None, session["id"]):
                raise rejected()
            conn.execute(m.orders.update().where(m.orders.c.id == order["id"]).values(checkout_session_id=session["id"]))
            conn.execute(m.checkout_details.update().where(m.checkout_details.c.order_id == order["id"]).values(checkout_url=checkout_url(session["url"])))
        return self.get(token, order["id"])

    def _validate(self, order, session, *, line_items=True):
        identifier(session.get("id"), "cs_test_")
        if (session.get("livemode") is not False or session.get("mode") != "payment"
            or session.get("client_reference_id") != str(order["id"])
            or session.get("metadata", {}).get("order_id") != str(order["id"])
            or session.get("amount_total") != order["amount"] or session.get("currency") != order["currency"]
            or (line_items and session.get("verified_price_id") != order["price_id"])
            or order["checkout_session_id"] not in (None, session["id"])):
            raise rejected()

    def receive(self, raw, signature):
        event = verify_event(raw, signature, self.settings.stripe_webhook_secret.get_secret_value(), self.clock())
        with self.engine.begin() as conn:
            require_current_schema(conn)
            ensure(conn, m.billing_events, dict(stripe_event_id=event["id"], event_type=event["type"],
                object_id=event["data"]["object"]["id"], state="pending", received_at=self.clock()))
            stored = conn.execute(sa.select(m.billing_events).where(m.billing_events.c.stripe_event_id == event["id"])).mappings().one()
            if stored["event_type"] != event["type"] or stored["object_id"] != event["data"]["object"]["id"]:
                raise rejected()
        self.process_event(event["id"])

    def process_event(self, event_id):
        with self.engine.begin() as conn:
            event = conn.execute(sa.select(m.billing_events).where(m.billing_events.c.stripe_event_id == event_id)).mappings().one()
            if event["state"] in ("processed", "rejected"):
                return
        try:
            session = self.provider.resolve(event["event_type"], event["object_id"])
            self._apply(session, event)
        except ApiError as exc:
            with self.engine.begin() as conn:
                conn.execute(m.billing_events.update().where(m.billing_events.c.stripe_event_id == event_id,
                    m.billing_events.c.state.in_(["pending", "failed"])).values(
                        state="rejected" if exc.code in (ErrorCode.EVENT_REJECTED, ErrorCode.AUTH_REQUIRED) else "failed"))
            raise
        except Exception:
            with self.engine.begin() as conn:
                conn.execute(m.billing_events.update().where(m.billing_events.c.stripe_event_id == event_id,
                    m.billing_events.c.state.in_(["pending", "failed"])).values(state="failed"))
            raise ApiError(ErrorCode.PAYMENT_PENDING) from None

    def _apply(self, session, event=None):
        try:
            order_id = UUID(session.get("client_reference_id", ""))
        except (ValueError, TypeError):
            raise rejected() from None
        with self.engine.begin() as conn:
            order = conn.execute(sa.select(m.orders).where(m.orders.c.id == order_id)).mappings().first()
            if not order or not order["owner_id"] or order["created_at"] < self.clock() - timedelta(days=90):
                raise rejected()
            lock_user(conn, order["owner_id"])
            order = conn.execute(sa.select(m.orders).where(m.orders.c.id == order_id).with_for_update()).mappings().one()
            if event:
                current = conn.execute(sa.select(m.billing_events.c.state).where(
                    m.billing_events.c.stripe_event_id == event["stripe_event_id"]).with_for_update()).scalar_one()
                if current in ("processed", "rejected"):
                    return
            self._validate(order, session)
            intent = session.get("payment_intent")
            intent_id = None
            charge = None
            if intent:
                if not isinstance(intent, dict) or intent.get("livemode") is not False:
                    raise rejected()
                intent_id = identifier(intent.get("id"), "pi_")
                if (intent.get("amount") != order["amount"] or intent.get("currency") != order["currency"]
                    or intent.get("metadata", {}).get("order_id") != str(order_id)
                    or order["payment_intent_id"] not in (None, intent_id)):
                    raise rejected()
                charge = intent.get("latest_charge")
                if charge and (not isinstance(charge, dict) or charge.get("livemode") is not False
                               or charge.get("payment_intent") != intent_id):
                    raise rejected()
            values = dict(checkout_session_id=session["id"])
            if intent_id:
                values["payment_intent_id"] = intent_id
            revoked = bool(charge and (charge.get("amount_refunded", 0) > 0 or charge.get("disputed")))
            # A verified dispute event remains a revocation even after a dispute closes.
            revoked = revoked or bool(event and "dispute" in event["event_type"])
            state = order["state"]
            if revoked:
                state = "refunded" if charge and charge.get("amount_refunded", 0) > 0 else "revoked"
                conn.execute(m.memberships.update().where(m.memberships.c.source_order_id == order_id,
                    m.memberships.c.revoked_at.is_(None)).values(revoked_at=self.clock()))
            elif state not in ("refunded", "revoked"):
                if session.get("payment_status") == "paid":
                    if session.get("status") != "complete" or not intent or intent.get("status") != "succeeded" or not charge or charge.get("paid") is not True:
                        raise rejected()
                    member = conn.execute(sa.select(m.memberships.c.id).where(m.memberships.c.source_order_id == order_id)).first()
                    if not member:
                        active = conn.execute(sa.select(m.memberships.c.id).where(m.memberships.c.owner_id == order["owner_id"],
                            m.memberships.c.revoked_at.is_(None), m.memberships.c.valid_until > self.clock())).first()
                        if active:
                            raise ApiError(ErrorCode.PAYMENT_PENDING)
                        conn.execute(m.memberships.insert().values(owner_id=order["owner_id"], source_order_id=order_id,
                            environment="test", valid_from=self.clock(), valid_until=self.clock() + timedelta(days=30), granted_units=20))
                    state = "paid"
                    values["paid_at"] = order["paid_at"] or self.clock()
                elif state != "paid" and session.get("status") == "expired":
                    state = "expired"
                elif state != "paid" and event and event["event_type"] == "checkout.session.async_payment_failed":
                    state = "failed"
            conn.execute(m.orders.update().where(m.orders.c.id == order_id).values(**values, state=state))
            if event:
                conn.execute(m.billing_events.update().where(m.billing_events.c.stripe_event_id == event["stripe_event_id"])
                    .values(state="processed", processed_at=self.clock()))

    def recover(self, limit=20):
        """Operator-only bounded recovery; never called by GET or by success page."""
        with self.engine.begin() as conn:
            require_current_schema(conn)
            events = conn.execute(sa.select(m.billing_events.c.stripe_event_id).where(
                m.billing_events.c.state.in_(["pending", "failed"])).order_by(m.billing_events.c.received_at).limit(limit)).scalars().all()
            sessions = conn.execute(sa.select(m.orders.c.checkout_session_id).where(m.orders.c.state == "pending",
                m.orders.c.checkout_session_id.is_not(None)).order_by(m.orders.c.created_at).limit(limit)).scalars().all()
            ambiguous = conn.execute(sa.select(m.orders).where(m.orders.c.state == "pending",
                m.orders.c.checkout_session_id.is_(None),
                m.orders.c.created_at > self.clock() - timedelta(hours=23)).order_by(m.orders.c.created_at).limit(limit)).mappings().all()
            ambiguous = [(dict(order), dict(self._detail(conn, order["id"]))) for order in ambiguous]
        success = failed = 0
        for order, detail in ambiguous:
            try:
                # Same immutable request/key, within Stripe's minimum 24h retention.
                # Past expires_at an unexecuted request cannot create a new usable Checkout.
                session = self.provider.create(order, detail)
                self._validate(order, session, line_items=False)
                self._apply(self.provider.session(session["id"]))
                success += 1
            except ApiError:
                failed += 1
        for event_id in events:
            try:
                self.process_event(event_id)
                success += 1
            except ApiError:
                failed += 1
        for session_id in sessions:
            try:
                self._apply(self.provider.session(session_id))
                success += 1
            except ApiError:
                failed += 1
        return {"processed": success, "failed": failed}
