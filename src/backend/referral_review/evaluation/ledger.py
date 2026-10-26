"""Durable evaluation accounting, NOT authorization to call a provider.

Lock order: batch -> attempt -> global control -> sorted budget keys. Each
attempt has one immutable sample fingerprint and price snapshot via its batch.
The real CLI stays disabled until operator authorization, synthetic manifest
validation and recording/recovery are integrated with these shared slots.
"""
from contextlib import contextmanager
from datetime import timedelta
from decimal import Decimal, InvalidOperation, ROUND_FLOOR
import hashlib
import json
import re
from uuid import uuid4

import sqlalchemy as sa

from ..config import ConfigurationError
from ..errors import ApiError
from ..extraction.contracts import TokenUsage
from ..persistence import models as m
from ..persistence.migrations import require_current_schema
from ..schemas import ErrorCode
from ..usage import budget, rates, slots

TERMINAL = ("settled", "released", "estimated_spent")


def cap_microusd(value: str) -> int:
    """Parse explicit decimal dollars without rounding above the authorized cap."""
    if not isinstance(value, str) or len(value) > 100:
        raise ApiError(ErrorCode.SCHEMA_INVALID)
    try:
        amount = Decimal(value)
        if not amount.is_finite() or not Decimal("0.000001") <= amount <= Decimal(2**62) / 1_000_000:
            raise ValueError
        return int((amount * 1_000_000).to_integral_value(rounding=ROUND_FLOOR))
    except (InvalidOperation, ValueError, TypeError):
        raise ApiError(ErrorCode.SCHEMA_INVALID) from None


def fingerprint(value):
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value):
        raise ApiError(ErrorCode.SCHEMA_INVALID)


class EvaluationLedger:
    def __init__(self, engine, settings, clock=m.utcnow):
        self.engine, self.settings, self.clock = engine, settings, clock

    @contextmanager
    def _transaction(self, connection=None):
        if connection is not None:
            if not connection.in_transaction() or connection.engine is not self.engine:
                raise ValueError("Caller-owned transaction on the ledger engine required")
            require_current_schema(connection)
            yield connection
            return
        with self.engine.connect().execution_options(sqlite_immediate=True) as conn, conn.begin():
            require_current_schema(conn)
            yield conn

    def _configuration(self):
        try:
            self.settings.require_real_ai_configuration()
        except ConfigurationError:
            raise ApiError(ErrorCode.REAL_AI_NOT_ALLOWED) from None
        if len(self.settings.model_id) > 200 or len(self.settings.price_version) > 100:
            raise ApiError(ErrorCode.SCHEMA_INVALID)

    def _pricing(self):
        return dict(model=self.settings.model_id, price_version=self.settings.price_version,
                    input_price=self.settings.input_microusd_per_million,
                    output_price=self.settings.output_microusd_per_million)

    def _batch(self, conn, batch_id):
        row = conn.execute(sa.select(m.evaluation_batches).where(m.evaluation_batches.c.id == batch_id)
                           .with_for_update()).mappings().first()
        if not row:
            raise ApiError(ErrorCode.NOT_FOUND)
        return row

    def _same_pricing(self, batch):
        if any(batch[key] != value for key, value in self._pricing().items()):
            raise ApiError(ErrorCode.USAGE_CONFLICT)

    def open_batch(self, batch_id, *, plan_hash, max_cost_usd, connection=None):
        """Idempotent identity binds a cap and plan; it cannot raise an old cap."""
        fingerprint(plan_hash)
        cap = cap_microusd(max_cost_usd)
        self._configuration()
        with self._transaction(connection) as conn:
            rates.ensure(conn, m.evaluation_batches, dict(id=batch_id, plan_hash=plan_hash,
                cap_microusd=cap, created_at=self.clock(), **self._pricing()))
            batch = self._batch(conn, batch_id)
            if (batch["plan_hash"], batch["cap_microusd"]) != (plan_hash, cap):
                raise ApiError(ErrorCode.USAGE_CONFLICT)
            self._same_pricing(batch)
            return dict(batch)

    def reserve(self, batch_id, *, sample_hash, input_bound, output_limit=6000, connection=None):
        fingerprint(sample_hash)
        if (type(input_bound) is not int or not 0 < input_bound <= 16000
            or type(output_limit) is not int or not 0 < output_limit <= 6000):
            raise ApiError(ErrorCode.SCHEMA_INVALID)
        self._configuration()
        with self._transaction(connection) as conn:
            batch = self._batch(conn, batch_id)
            self._same_pricing(batch)
            previous = conn.execute(sa.select(m.evaluation_attempts).where(
                m.evaluation_attempts.c.batch_id == batch_id, m.evaluation_attempts.c.sample_hash == sample_hash)).mappings().first()
            if previous:
                if (previous["input_bound"], previous["output_limit"]) != (input_bound, output_limit):
                    raise ApiError(ErrorCode.USAGE_CONFLICT)
                return dict(previous)  # A terminal/unknown attempt is never reset.
            upper = budget.cost(input_bound, output_limit, batch["input_price"], batch["output_price"])
            if batch["reserved_microusd"] + batch["spent_microusd"] + upper > batch["cap_microusd"]:
                raise ApiError(ErrorCode.BUDGET_EXHAUSTED)
            now = self.clock()
            keys = budget.reserve(conn, self.settings, now, upper)
            attempt_id = uuid4()
            conn.execute(m.evaluation_batches.update().where(m.evaluation_batches.c.id == batch_id)
                         .values(reserved_microusd=m.evaluation_batches.c.reserved_microusd + upper))
            conn.execute(m.evaluation_attempts.insert().values(id=attempt_id, batch_id=batch_id,
                sample_hash=sample_hash, input_bound=input_bound, output_limit=output_limit,
                upper_microusd=upper, state="reserved", created_at=now, lease_expires_at=now + timedelta(seconds=240)))
            for key in sorted(keys):
                conn.execute(m.evaluation_buckets.insert().values(attempt_id=attempt_id, bucket_key=key))
            return self._read(conn, attempt_id)

    def _read(self, conn, attempt_id):
        return dict(conn.execute(sa.select(m.evaluation_attempts).where(
            m.evaluation_attempts.c.id == attempt_id)).mappings().one())

    def _locked(self, conn, batch_id, attempt_id):
        batch = self._batch(conn, batch_id)
        attempt = conn.execute(sa.select(m.evaluation_attempts).where(m.evaluation_attempts.c.id == attempt_id,
            m.evaluation_attempts.c.batch_id == batch_id).with_for_update()).mappings().first()
        if not attempt:
            raise ApiError(ErrorCode.NOT_FOUND)
        control = budget.control(conn)
        keys = conn.execute(sa.select(m.evaluation_buckets.c.bucket_key).where(
            m.evaluation_buckets.c.attempt_id == attempt_id).order_by(m.evaluation_buckets.c.bucket_key)).scalars().all()
        budget.lock_buckets(conn, keys)
        return batch, attempt, control, keys

    def record_dispatch(self, batch_id, attempt_id, *, connection=None):
        """Atomically claim a shared global slot and a one-way dispatch marker.

        Commit before transport; a crash after this marker must be cost-unknown,
        never retryable. Returning a reservation from reserve is insufficient.
        This is not operator/invitation/synthetic-input authorization.
        """
        self._configuration()
        with self._transaction(connection) as conn:
            batch, attempt, control, keys = self._locked(conn, batch_id, attempt_id)
            self._same_pricing(batch)
            if control["halted"]:
                raise ApiError(ErrorCode.BUDGET_EXHAUSTED)
            now = self.clock()
            # Reservations cannot authorize calls charged to a past day/month.
            if (attempt["state"] != "reserved" or attempt["lease_expires_at"] <= now
                or set(keys) != set(budget.bucket_limits(self.settings, now))):
                raise ApiError(ErrorCode.USAGE_CONFLICT)
            lease = slots.claim_evaluation(conn, attempt_id, now)
            conn.execute(m.evaluation_attempts.update().where(m.evaluation_attempts.c.id == attempt_id)
                         .values(state="dispatched", dispatched_at=now, lease_expires_at=lease))
            return self._read(conn, attempt_id)

    def settle(self, batch_id, attempt_id, *, outcome, usage=None, connection=None):
        if outcome not in ("succeeded", "failed", "cancelled", "unknown"):
            raise ApiError(ErrorCode.SCHEMA_INVALID)
        if usage is not None:
            try:
                usage = TokenUsage.model_validate(usage.model_dump() if isinstance(usage, TokenUsage) else usage)
            except ValueError:
                raise ApiError(ErrorCode.SCHEMA_INVALID) from None
        if usage is not None and outcome in ("unknown", "cancelled"):
            raise ApiError(ErrorCode.SCHEMA_INVALID)
        digest = hashlib.sha256(json.dumps({"outcome": outcome, "usage": usage.model_dump() if usage else None}, sort_keys=True).encode()).hexdigest()
        with self._transaction(connection) as conn:
            batch, attempt, _, keys = self._locked(conn, batch_id, attempt_id)
            if attempt["state"] in TERMINAL:
                if attempt["settlement_hash"] != digest:
                    raise ApiError(ErrorCode.USAGE_CONFLICT)
                return dict(attempt)
            now = self.clock()
            dispatched = attempt["dispatched_at"] is not None
            if (not dispatched and (outcome in ("succeeded", "unknown") or usage is not None)
                or dispatched and outcome == "cancelled"):
                raise ApiError(ErrorCode.USAGE_CONFLICT)
            if outcome == "unknown":
                if attempt["unknown_at"] is None:
                    conn.execute(m.evaluation_attempts.update().where(m.evaluation_attempts.c.id == attempt_id)
                                 .values(state="retained_unknown", unknown_at=now))
                    return self._read(conn, attempt_id)
                if now < attempt["unknown_at"] + timedelta(hours=24):
                    return dict(attempt)
            if not dispatched:
                actual, state = 0, "released"
            elif usage is None:
                actual, state = attempt["upper_microusd"], "estimated_spent"
            else:
                actual = budget.cost(usage.prompt_tokens, usage.completion_tokens, batch["input_price"], batch["output_price"])
                state = "settled"
            budget.settle(conn, keys, attempt["upper_microusd"], actual)
            conn.execute(m.evaluation_batches.update().where(m.evaluation_batches.c.id == batch_id).values(
                reserved_microusd=m.evaluation_batches.c.reserved_microusd - attempt["upper_microusd"],
                spent_microusd=m.evaluation_batches.c.spent_microusd + actual))
            conn.execute(m.evaluation_attempts.update().where(m.evaluation_attempts.c.id == attempt_id).values(
                state=state, outcome=outcome, actual_microusd=actual, settlement_hash=digest, settled_at=now,
                prompt_tokens=usage.prompt_tokens if usage else None,
                completion_tokens=usage.completion_tokens if usage else None))
            slots.release_evaluation(conn, attempt_id)
            return self._read(conn, attempt_id)

    def adjust(self, batch_id, attempt_id, *, adjustment_key, usage, connection=None):
        """Trusted absolute usage correction; never a public refund operation.

        Keep the original settlement and apply only the delta to its original
        day/month buckets. Replaying an older key never undoes a newer entry.
        Disabled dispatch/current pricing do not prevent reconciling old costs.
        """
        if not isinstance(adjustment_key, str) or not 1 <= len(adjustment_key) <= 100:
            raise ApiError(ErrorCode.SCHEMA_INVALID)
        try:
            usage = TokenUsage.model_validate(usage.model_dump() if isinstance(usage, TokenUsage) else usage)
        except ValueError:
            raise ApiError(ErrorCode.SCHEMA_INVALID) from None
        with self._transaction(connection) as conn:
            batch, attempt, _, keys = self._locked(conn, batch_id, attempt_id)
            if attempt["state"] not in ("settled", "estimated_spent") or attempt["dispatched_at"] is None:
                raise ApiError(ErrorCode.USAGE_CONFLICT)
            previous = conn.execute(sa.select(m.evaluation_adjustments).where(
                m.evaluation_adjustments.c.attempt_id == attempt_id,
                m.evaluation_adjustments.c.adjustment_key == adjustment_key)).mappings().first()
            if previous:
                if (previous["prompt_tokens"], previous["completion_tokens"]) != (usage.prompt_tokens, usage.completion_tokens):
                    raise ApiError(ErrorCode.USAGE_CONFLICT)
                return dict(previous)
            actual = budget.cost(usage.prompt_tokens, usage.completion_tokens, batch["input_price"], batch["output_price"])
            corrections = conn.execute(sa.select(sa.func.coalesce(sa.func.sum(m.evaluation_adjustments.c.delta_microusd), 0))
                .where(m.evaluation_adjustments.c.attempt_id == attempt_id)).scalar_one()
            delta = actual - (attempt["actual_microusd"] + corrections)
            for key in keys:
                conn.execute(m.budget_buckets.update().where(m.budget_buckets.c.bucket_key == key)
                    .values(spent_microusd=m.budget_buckets.c.spent_microusd + delta))
            conn.execute(m.evaluation_batches.update().where(m.evaluation_batches.c.id == batch_id)
                .values(spent_microusd=m.evaluation_batches.c.spent_microusd + delta))
            if actual > attempt["upper_microusd"]:
                conn.execute(m.usage_controls.update().where(m.usage_controls.c.key == "real_ai")
                    .values(halted=True, reason="ACTUAL_EXCEEDS_RESERVATION"))
            row = dict(id=uuid4(), attempt_id=attempt_id, adjustment_key=adjustment_key,
                prompt_tokens=usage.prompt_tokens, completion_tokens=usage.completion_tokens,
                actual_microusd=actual, delta_microusd=delta, created_at=self.clock())
            conn.execute(m.evaluation_adjustments.insert().values(**row))
            return row

    def recover(self, *, limit=100):
        """Bounded recovery only; never calls a provider or resets an attempt."""
        if type(limit) is not int or not 1 <= limit <= 100:
            raise ApiError(ErrorCode.SCHEMA_INVALID)
        with self._transaction() as conn:
            now = self.clock()
            due = conn.execute(sa.select(m.evaluation_attempts).where(
                sa.or_(sa.and_(m.evaluation_attempts.c.state.in_(("reserved", "dispatched")),
                               m.evaluation_attempts.c.lease_expires_at <= now),
                       sa.and_(m.evaluation_attempts.c.state == "retained_unknown",
                               m.evaluation_attempts.c.unknown_at <= now - timedelta(hours=24)))).order_by(
                    m.evaluation_attempts.c.lease_expires_at, m.evaluation_attempts.c.id).limit(limit)).mappings().all()
        results = []
        for row in due:
            # Settle re-locks/rechecks after the scan. A concurrent successful
            # settlement may win; never undo its committed accounting.
            try:
                results.append(self.settle(row["batch_id"], row["id"],
                    outcome="cancelled" if row["dispatched_at"] is None else "unknown"))
            except ApiError as exc:
                if exc.code != ErrorCode.USAGE_CONFLICT:
                    raise
        return results
