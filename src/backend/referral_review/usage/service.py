"""Atomic usage ledger; only server orchestration may call reserve/settle/adjust.

Lock order: user -> packet -> run -> membership -> global control -> budget keys
-> slots. Rate attempts use a separate committed transaction. No provider calls.
Reservation replay is NOT permission to dispatch again; MT-11 owns dispatch CAS.
"""
from datetime import timedelta, timezone
import hashlib
import json
from uuid import uuid4

import sqlalchemy as sa

from ..config import ConfigurationError
from ..errors import ApiError
from ..extraction.contracts import TokenUsage
from ..persistence import models as m
from ..persistence.migrations import require_current_schema
from ..persistence.repository import NotFound, owned_packet
from ..schemas import ErrorCode, MembershipResponse
from . import rates


def cost(input_tokens, output_tokens, input_price, output_price):
    if any(type(v) is not int or v < 0 for v in (input_tokens, output_tokens, input_price, output_price)):
        raise ApiError(ErrorCode.SCHEMA_INVALID)
    value = (input_tokens * input_price + output_tokens * output_price + 999_999) // 1_000_000
    if value > 2**62:
        raise ApiError(ErrorCode.SERVICE_NOT_READY)
    return value


def bucket_limits(settings, now):
    now = now.astimezone(timezone.utc)
    return {f"day:{now:%Y-%m-%d}": settings.daily_budget_microusd,
            f"month:{now:%Y-%m}": settings.monthly_budget_microusd}


class Usage:
    def __init__(self, identity):
        self.identity, self.engine = identity, identity.engine
        self.settings, self.clock = identity.settings, identity.clock

    def _run(self, conn, owner, run_id, *, active):
        require_current_schema(conn)
        # Settling deleted/disabled accounts is necessary to account for already spent money.
        user = conn.execute(sa.select(m.users.c.id).where(m.users.c.id == owner).with_for_update()).first()
        if not user:
            raise ApiError(ErrorCode.NOT_FOUND)
        if active:
            rates.lock_user(conn, owner)
        run = conn.execute(sa.select(m.runs).where(m.runs.c.id == run_id, m.runs.c.owner_id == owner)).mappings().first()
        if not run:
            raise ApiError(ErrorCode.NOT_FOUND)
        if active:
            try:
                owned_packet(conn, owner, run["packet_id"], self.clock(), lock=True)
            except NotFound:
                raise ApiError(ErrorCode.NOT_FOUND) from None
        else:
            conn.execute(sa.select(m.packets.c.id).where(m.packets.c.id == run["packet_id"]).with_for_update()).first()
        return conn.execute(sa.select(m.runs).where(m.runs.c.id == run_id).with_for_update()).mappings().one()

    def _member(self, conn, owner):
        now = self.clock()
        rows = conn.execute(sa.select(m.memberships).where(m.memberships.c.owner_id == owner,
            m.memberships.c.environment == "test", m.memberships.c.valid_from <= now,
            m.memberships.c.valid_until > now, m.memberships.c.revoked_at.is_(None))
            .order_by(m.memberships.c.id).with_for_update()).mappings().all()
        if len(rows) != 1:
            raise ApiError(ErrorCode.MEMBERSHIP_REQUIRED)
        return rows[0]

    def _real_configuration(self, owner):
        try:
            self.settings.require_real_ai_configuration()
        except ConfigurationError:
            raise ApiError(ErrorCode.REAL_AI_NOT_ALLOWED) from None
        if owner not in self.settings.real_ai_user_ids:
            raise ApiError(ErrorCode.REAL_AI_NOT_ALLOWED)

    def _control(self, conn):
        rates.ensure(conn, m.usage_controls, {"key": "real_ai", "halted": False})
        return conn.execute(sa.select(m.usage_controls).where(m.usage_controls.c.key == "real_ai")
                            .with_for_update()).mappings().one()

    def _prior(self, conn, run_id):
        return conn.execute(sa.select(m.usage_reservations).where(m.usage_reservations.c.run_id == run_id)).mappings().first()

    def _replay(self, conn, prior, input_bound, output_limit):
        detail = conn.execute(sa.select(m.usage_details).where(m.usage_details.c.reservation_id == prior["id"])).mappings().first()
        if not detail or (detail["input_bound"], detail["output_limit"]) != (input_bound, output_limit):
            raise ApiError(ErrorCode.USAGE_CONFLICT)
        return dict(prior)

    def reserve(self, owner, run_id, *, input_bound, output_limit=6000):
        """Server-only input token upper bound from MT-08; client never supplies mode/prices/member."""
        if (type(input_bound) is not int or not 0 < input_bound <= 16000
            or type(output_limit) is not int or not 0 < output_limit <= 6000):
            raise ApiError(ErrorCode.SCHEMA_INVALID)
        # Failed budget/member/config attempts still consume shared attempt counters.
        with self.engine.begin() as conn:
            self._run(conn, owner, run_id, active=True)
            prior = self._prior(conn, run_id)
            if prior:
                return self._replay(conn, prior, input_bound, output_limit)
            rates.consume(conn, owner, "execute", self.clock())
        with self.engine.begin() as conn:
            run = self._run(conn, owner, run_id, active=True)
            prior = self._prior(conn, run_id)
            if prior:
                return self._replay(conn, prior, input_bound, output_limit)
            if run["state"] != "pending" or run["provider_dispatched_at"] is not None:
                raise ApiError(ErrorCode.USAGE_CONFLICT)
            if run["mode"] not in ("fake", "real") or self.settings.mode == "bundled_demo":
                raise ApiError(ErrorCode.REAL_AI_NOT_ALLOWED)
            real = run["mode"] == "real"
            if real:
                self._real_configuration(owner)
                if run["model_requested"] != self.settings.model_id:
                    raise ApiError(ErrorCode.REAL_AI_NOT_ALLOWED)
            member = self._member(conn, owner)
            if member["reserved_units"] + member["consumed_units"] >= member["granted_units"]:
                raise ApiError(ErrorCode.QUOTA_EXHAUSTED)
            rates.check_failures(conn, owner, self.clock())
            input_price = self.settings.input_microusd_per_million if real else 0
            output_price = self.settings.output_microusd_per_million if real else 0
            upper = cost(input_bound, output_limit, input_price, output_price)
            keys = bucket_limits(self.settings, self.clock()) if real else {}
            if real and self._control(conn)["halted"]:
                raise ApiError(ErrorCode.BUDGET_EXHAUSTED)
            for key, limit in sorted(keys.items()):
                rates.ensure(conn, m.budget_buckets, {"bucket_key": key, "limit_microusd": limit})
                bucket = conn.execute(sa.select(m.budget_buckets).where(m.budget_buckets.c.bucket_key == key)
                                      .with_for_update()).mappings().one()
                if limit <= 0 or bucket["reserved_microusd"] + bucket["spent_microusd"] + upper > min(limit, bucket["limit_microusd"]):
                    raise ApiError(ErrorCode.BUDGET_EXHAUSTED)
            lease = self.clock() + timedelta(seconds=240)
            for scope, capacity in ((f"account:{owner}", 1), ("global", 2)):
                for slot in range(capacity):
                    rates.ensure(conn, m.concurrency_slots, {"scope": scope, "slot_number": slot})
                slots = conn.execute(sa.select(m.concurrency_slots).where(m.concurrency_slots.c.scope == scope)
                                     .order_by(m.concurrency_slots.c.slot_number).with_for_update()).mappings().all()
                free = next((s for s in slots if s["run_id"] is None or s["lease_expires_at"] <= self.clock()), None)
                if free is None:
                    raise ApiError(ErrorCode.RUN_ACTIVE)
                conn.execute(m.concurrency_slots.update().where(m.concurrency_slots.c.scope == scope,
                    m.concurrency_slots.c.slot_number == free["slot_number"]).values(run_id=run_id, lease_expires_at=lease))
            rid = uuid4()
            conn.execute(m.memberships.update().where(m.memberships.c.id == member["id"])
                         .values(reserved_units=m.memberships.c.reserved_units + 1))
            for key in sorted(keys):
                conn.execute(m.budget_buckets.update().where(m.budget_buckets.c.bucket_key == key)
                             .values(reserved_microusd=m.budget_buckets.c.reserved_microusd + upper))
            conn.execute(m.usage_reservations.insert().values(id=rid, run_id=run_id, owner_id=owner,
                membership_id=member["id"], units=1, cost_upper_bound_microusd=upper, state="reserved",
                price_version=self.settings.price_version if real else "fake-no-provider-cost", created_at=self.clock()))
            for key in sorted(keys):
                conn.execute(m.usage_buckets.insert().values(reservation_id=rid, bucket_key=key))
            conn.execute(m.usage_details.insert().values(reservation_id=rid, mode=run["mode"],
                model=self.settings.model_id if real else "fake-extraction-v1", input_bound=input_bound,
                output_limit=output_limit, input_price=input_price, output_price=output_price))
            return dict(self._prior(conn, run_id))

    def _locked_reservation(self, conn, owner, run_id):
        run = self._run(conn, owner, run_id, active=False)
        reservation = self._prior(conn, run_id)
        if not reservation:
            raise ApiError(ErrorCode.NOT_FOUND)
        conn.execute(sa.select(m.memberships.c.id).where(m.memberships.c.id == reservation["membership_id"])
                     .with_for_update()).one()
        detail = conn.execute(sa.select(m.usage_details).where(m.usage_details.c.reservation_id == reservation["id"])).mappings().first()
        if not detail:
            raise ApiError(ErrorCode.USAGE_CONFLICT)
        if detail["mode"] == "real":
            self._control(conn)
        keys = conn.execute(sa.select(m.usage_buckets.c.bucket_key).where(
            m.usage_buckets.c.reservation_id == reservation["id"]).order_by(m.usage_buckets.c.bucket_key)).scalars().all()
        for key in keys:
            conn.execute(sa.select(m.budget_buckets.c.bucket_key).where(m.budget_buckets.c.bucket_key == key)
                         .with_for_update()).one()
        return run, reservation, detail, keys

    def _release_slots(self, conn, owner, run_id):
        for scope in (f"account:{owner}", "global"):
            slots = conn.execute(sa.select(m.concurrency_slots).where(m.concurrency_slots.c.scope == scope)
                                 .order_by(m.concurrency_slots.c.slot_number).with_for_update()).mappings().all()
            for slot in slots:
                if slot["run_id"] == run_id:
                    conn.execute(m.concurrency_slots.update().where(m.concurrency_slots.c.scope == scope,
                        m.concurrency_slots.c.slot_number == slot["slot_number"]).values(run_id=None, lease_expires_at=None))

    def settle(self, owner, run_id, *, outcome, usage=None):
        """outcome is trusted orchestration state. Missing usage never implies a free call."""
        if outcome not in ("succeeded", "failed", "unknown", "cancelled"):
            raise ApiError(ErrorCode.SCHEMA_INVALID)
        if usage is not None:
            try:
                usage = TokenUsage.model_validate(usage.model_dump() if isinstance(usage, TokenUsage) else usage)
            except ValueError:
                raise ApiError(ErrorCode.SCHEMA_INVALID) from None
        digest = hashlib.sha256(json.dumps({"outcome": outcome, "usage": usage.model_dump() if usage else None}, sort_keys=True).encode()).hexdigest()
        with self.engine.begin() as conn:
            run, reservation, detail, keys = self._locked_reservation(conn, owner, run_id)
            if reservation["state"] in ("settled", "released", "estimated_spent"):
                if detail["settlement_hash"] != digest:
                    raise ApiError(ErrorCode.USAGE_CONFLICT)
                return dict(reservation)
            if outcome == "unknown":
                if detail["mode"] == "real" and run["provider_dispatched_at"] is None:
                    raise ApiError(ErrorCode.USAGE_CONFLICT)
                if reservation["state"] == "reserved":
                    conn.execute(m.usage_reservations.update().where(m.usage_reservations.c.id == reservation["id"]).values(state="retained_unknown"))
                    conn.execute(m.usage_details.update().where(m.usage_details.c.reservation_id == reservation["id"])
                                 .values(unknown_at=self.clock()))
                    rates.increment(conn, owner, "failure", self.clock())
                # No early slot release: a timed-out provider may still be running.
                if detail["unknown_at"] is None or self.clock() < detail["unknown_at"] + timedelta(hours=24):
                    return dict(self._prior(conn, run_id))
            real = detail["mode"] == "real"
            undispatched = run["provider_dispatched_at"] is None
            if real and outcome == "succeeded" and undispatched:
                raise ApiError(ErrorCode.USAGE_CONFLICT)
            if real and outcome == "cancelled" and not undispatched:
                raise ApiError(ErrorCode.USAGE_CONFLICT)
            if not real or (undispatched and outcome in ("failed", "cancelled")):
                actual, state = 0, "settled" if outcome == "succeeded" else "released"
            elif usage is None or outcome == "unknown":
                actual, state = reservation["cost_upper_bound_microusd"], "estimated_spent"
            else:
                actual = cost(usage.prompt_tokens, usage.completion_tokens, detail["input_price"], detail["output_price"])
                state = "settled"
            if actual > reservation["cost_upper_bound_microusd"]:
                conn.execute(m.usage_controls.update().where(m.usage_controls.c.key == "real_ai")
                             .values(halted=True, reason="ACTUAL_EXCEEDS_RESERVATION"))
            for key in keys:
                conn.execute(m.budget_buckets.update().where(m.budget_buckets.c.bucket_key == key).values(
                    reserved_microusd=m.budget_buckets.c.reserved_microusd - reservation["cost_upper_bound_microusd"],
                    spent_microusd=m.budget_buckets.c.spent_microusd + actual))
            conn.execute(m.memberships.update().where(m.memberships.c.id == reservation["membership_id"]).values(
                reserved_units=m.memberships.c.reserved_units - 1,
                consumed_units=m.memberships.c.consumed_units + (1 if outcome == "succeeded" else 0)))
            if outcome == "failed" and reservation["state"] != "retained_unknown":
                rates.increment(conn, owner, "failure", self.clock())
            conn.execute(m.usage_reservations.update().where(m.usage_reservations.c.id == reservation["id"])
                         .values(state=state, actual_microusd=actual))
            conn.execute(m.usage_details.update().where(m.usage_details.c.reservation_id == reservation["id"])
                         .values(outcome=outcome, settled_at=self.clock(), settlement_hash=digest))
            self._release_slots(conn, owner, run_id)
            return dict(self._prior(conn, run_id))

    def retain_unknown(self, owner, run_id):
        return self.settle(owner, run_id, outcome="unknown")

    def adjust(self, owner, run_id, *, adjustment_key, usage):
        """Internal trusted late usage correction, append-only and never a public refund endpoint."""
        if not isinstance(adjustment_key, str) or not 1 <= len(adjustment_key) <= 100:
            raise ApiError(ErrorCode.SCHEMA_INVALID)
        try:
            usage = TokenUsage.model_validate(usage.model_dump() if isinstance(usage, TokenUsage) else usage)
        except ValueError:
            raise ApiError(ErrorCode.SCHEMA_INVALID) from None
        with self.engine.begin() as conn:
            _, reservation, detail, keys = self._locked_reservation(conn, owner, run_id)
            if reservation["state"] not in ("settled", "estimated_spent") or detail["mode"] != "real":
                raise ApiError(ErrorCode.USAGE_CONFLICT)
            actual = cost(usage.prompt_tokens, usage.completion_tokens, detail["input_price"], detail["output_price"])
            previous = conn.execute(sa.select(m.usage_adjustments).where(m.usage_adjustments.c.reservation_id == reservation["id"],
                m.usage_adjustments.c.adjustment_key == adjustment_key)).mappings().first()
            if previous:
                if previous["actual_microusd"] != actual:
                    raise ApiError(ErrorCode.USAGE_CONFLICT)
                return dict(previous)
            corrections = conn.execute(sa.select(sa.func.coalesce(sa.func.sum(m.usage_adjustments.c.delta_microusd), 0)).where(
                m.usage_adjustments.c.reservation_id == reservation["id"])).scalar_one()
            delta = actual - (reservation["actual_microusd"] + corrections)
            for key in keys:
                conn.execute(m.budget_buckets.update().where(m.budget_buckets.c.bucket_key == key)
                             .values(spent_microusd=m.budget_buckets.c.spent_microusd + delta))
            if actual > reservation["cost_upper_bound_microusd"]:
                conn.execute(m.usage_controls.update().where(m.usage_controls.c.key == "real_ai")
                             .values(halted=True, reason="ACTUAL_EXCEEDS_RESERVATION"))
            row = dict(id=uuid4(), reservation_id=reservation["id"], adjustment_key=adjustment_key,
                       actual_microusd=actual, delta_microusd=delta, created_at=self.clock())
            conn.execute(m.usage_adjustments.insert().values(**row))
            return row

    def membership(self, token):
        with self.engine.begin() as conn:
            require_current_schema(conn)
            owner = self.identity.require_user(conn, token)
            try:
                member = self._member(conn, owner)
            except ApiError as exc:
                if exc.code != ErrorCode.MEMBERSHIP_REQUIRED:
                    raise
                return MembershipResponse(remaining=0, reserved=0, real_ai_allowed=False)
            remaining = member["granted_units"] - member["reserved_units"] - member["consumed_units"]
            allowed = remaining > 0
            try:
                self._real_configuration(owner)
                rates.check_failures(conn, owner, self.clock())
            except ApiError:
                allowed = False
            control = conn.execute(sa.select(m.usage_controls.c.halted).where(m.usage_controls.c.key == "real_ai")).scalar_one_or_none()
            allowed = allowed and not control
            # Read-only hint; atomic reserve remains authoritative, including concurrency and request cost.
            for key, limit in bucket_limits(self.settings, self.clock()).items():
                bucket = conn.execute(sa.select(m.budget_buckets).where(m.budget_buckets.c.bucket_key == key)).mappings().first()
                if limit <= 0 or (bucket and bucket["spent_microusd"] + bucket["reserved_microusd"] >= min(limit, bucket["limit_microusd"])):
                    allowed = False
            return MembershipResponse(valid_until=member["valid_until"], remaining=remaining,
                                      reserved=member["reserved_units"], real_ai_allowed=allowed)

    def check_export(self, token, packet_id):
        """MT-13 must invoke before rendering; membership expiry never blocks export."""
        with self.engine.begin() as conn:
            require_current_schema(conn)
            packet = self.identity.require_owner(conn, token, packet_id)
            rates.consume(conn, packet["owner_id"], "export", self.clock())
