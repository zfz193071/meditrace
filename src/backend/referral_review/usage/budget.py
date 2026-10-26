"""Shared financial primitives for workspace and evaluation ledgers.

Caller owns the transaction and any preceding domain locks. Lock order is the
real_ai control row, then sorted UTC bucket keys. No dispatch permission is
granted here; reservations only account for potential spend.
"""
from datetime import timezone

import sqlalchemy as sa

from ..errors import ApiError
from ..persistence import models as m
from ..persistence.repository import require_transaction
from ..schemas import ErrorCode
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


def control(conn):
    require_transaction(conn)
    rates.ensure(conn, m.usage_controls, {"key": "real_ai", "halted": False})
    return conn.execute(sa.select(m.usage_controls).where(m.usage_controls.c.key == "real_ai")
                        .with_for_update()).mappings().one()


def lock_buckets(conn, keys):
    require_transaction(conn)
    for key in sorted(keys):
        conn.execute(sa.select(m.budget_buckets.c.bucket_key).where(m.budget_buckets.c.bucket_key == key)
                     .with_for_update()).one()


def reserve(conn, settings, now, upper):
    if type(upper) is not int or not 0 < upper <= 2**62:
        raise ApiError(ErrorCode.SCHEMA_INVALID)
    if control(conn)["halted"]:
        raise ApiError(ErrorCode.BUDGET_EXHAUSTED)
    keys = bucket_limits(settings, now)
    for key, limit in sorted(keys.items()):
        rates.ensure(conn, m.budget_buckets, {"bucket_key": key, "limit_microusd": limit})
        bucket = conn.execute(sa.select(m.budget_buckets).where(m.budget_buckets.c.bucket_key == key)
                              .with_for_update()).mappings().one()
        if limit <= 0 or bucket["reserved_microusd"] + bucket["spent_microusd"] + upper > min(limit, bucket["limit_microusd"]):
            raise ApiError(ErrorCode.BUDGET_EXHAUSTED)
    for key in sorted(keys):
        conn.execute(m.budget_buckets.update().where(m.budget_buckets.c.bucket_key == key)
                     .values(reserved_microusd=m.budget_buckets.c.reserved_microusd + upper))
    return keys


def settle(conn, keys, upper, actual):
    """Caller has locked control/buckets and verified a nonterminal reservation."""
    require_transaction(conn)
    if actual > upper:
        conn.execute(m.usage_controls.update().where(m.usage_controls.c.key == "real_ai")
                     .values(halted=True, reason="ACTUAL_EXCEEDS_RESERVATION"))
    for key in sorted(keys):
        conn.execute(m.budget_buckets.update().where(m.budget_buckets.c.bucket_key == key).values(
            reserved_microusd=m.budget_buckets.c.reserved_microusd - upper,
            spent_microusd=m.budget_buckets.c.spent_microusd + actual))
