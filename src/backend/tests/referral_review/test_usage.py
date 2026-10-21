"""Isolated synthetic ledger tests. No credentials, model calls or production grant path."""
from datetime import timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest
import sqlalchemy as sa

from referral_review.config import Settings
from referral_review.errors import ApiError
from referral_review.persistence import models as m
from referral_review.usage import Usage
from referral_review.usage import rates
from test_persistence import engine, empty_engine, seed, NOW


def configuration(owners, **changes):
    return Settings(**(dict(RR_MODE="invited_real", REAL_AI_ENABLED=True, DEEPSEEK_API_KEY="synthetic",
        RR_MODEL_ID="synthetic-model", RR_MODEL_PRICE_VERSION="synthetic-v1", RR_REAL_AI_USER_IDS=list(owners),
        RR_MODEL_INPUT_MICROUSD_PER_MILLION_TOKENS=1000, RR_MODEL_OUTPUT_MICROUSD_PER_MILLION_TOKENS=2000,
        RR_DAILY_BUDGET_MICROUSD=1000, RR_MONTHLY_BUDGET_MICROUSD=2000) | changes))


def service(engine, owners, now=None, **changes):
    clock = now if now is not None else [NOW]
    return Usage(SimpleNamespace(engine=engine, settings=configuration(owners, **changes), clock=lambda: clock[0]))


def graph(engine, *, mode="real", units=20):
    with engine.begin() as conn:
        result = seed(conn, units=units, budget=1000)
        conn.execute(m.runs.update().where(m.runs.c.id == result["run"])
                     .values(mode=mode, model_requested="synthetic-model"))
    return result


def another_run(engine, g):
    with engine.begin() as conn:
        row = dict(conn.execute(sa.select(m.runs).where(m.runs.c.id == g["run"])).mappings().one())
        row.update(id=uuid4(), input_hash=uuid4().hex * 2, state="pending", provider_dispatched_at=None)
        conn.execute(m.runs.insert().values(**row))
    return row["id"]


def reserve(s, g, run=None):
    return s.reserve(g["owner"], run or g["run"], input_bound=1000, output_limit=1000)


def dispatch(engine, g):
    with engine.begin() as conn:
        conn.execute(m.runs.update().where(m.runs.c.id == g["run"]).values(provider_dispatched_at=NOW))


def values(engine, table):
    with engine.begin() as conn:
        return [dict(row) for row in conn.execute(sa.select(table)).mappings()]


TOKENS = {"prompt_tokens": 500, "completion_tokens": 500, "total_tokens": 1000}


def test_reservation_and_success_are_idempotent(engine):
    g = graph(engine)
    s = service(engine, [g["owner"]])
    first = reserve(s, g)
    assert first["cost_upper_bound_microusd"] == 3
    assert reserve(s, g)["id"] == first["id"]
    assert len(values(engine, m.usage_reservations)) == 1
    assert values(engine, m.memberships)[0]["reserved_units"] == 1
    dispatch(engine, g)
    final = s.settle(g["owner"], g["run"], outcome="succeeded", usage=TOKENS)
    assert final["actual_microusd"] == 2 and final["state"] == "settled"
    assert s.settle(g["owner"], g["run"], outcome="succeeded", usage=TOKENS) == final
    member = values(engine, m.memberships)[0]
    assert (member["reserved_units"], member["consumed_units"]) == (0, 1)
    assert all(b["reserved_microusd"] == 0 and b["spent_microusd"] == 2 for b in values(engine, m.budget_buckets))
    with pytest.raises(ApiError, match="USAGE_CONFLICT"):
        s.settle(g["owner"], g["run"], outcome="failed", usage=TOKENS)


@pytest.mark.parametrize("outcome,dispatched,usage,state,spent", [
    ("failed", True, TOKENS, "settled", 2), ("failed", False, None, "released", 0),
    ("failed", True, None, "estimated_spent", 3), ("cancelled", False, None, "released", 0),
    ("succeeded", True, None, "estimated_spent", 3),
])
def test_settlement_paths(engine, outcome, dispatched, usage, state, spent):
    g = graph(engine)
    s = service(engine, [g["owner"]])
    reserve(s, g)
    if dispatched: dispatch(engine, g)
    result = s.settle(g["owner"], g["run"], outcome=outcome, usage=usage)
    assert (result["state"], result["actual_microusd"]) == (state, spent)
    assert values(engine, m.memberships)[0]["consumed_units"] == (1 if outcome == "succeeded" else 0)
    assert all(slot["run_id"] is None for slot in values(engine, m.concurrency_slots))


def test_unknown_retains_budget_then_estimates_after_24h(engine):
    now = [NOW]
    g = graph(engine)
    s = service(engine, [g["owner"]], now)
    reserve(s, g)
    dispatch(engine, g)
    first = s.retain_unknown(g["owner"], g["run"])
    assert s.retain_unknown(g["owner"], g["run"]) == first
    assert first["state"] == "retained_unknown"
    assert values(engine, m.memberships)[0]["consumed_units"] == 0
    assert all(b["reserved_microusd"] == 3 and b["spent_microusd"] == 0 for b in values(engine, m.budget_buckets))
    now[0] += timedelta(hours=24)
    final = s.retain_unknown(g["owner"], g["run"])
    assert final["state"] == "estimated_spent"
    assert s.retain_unknown(g["owner"], g["run"]) == final
    assert values(engine, m.memberships)[0]["reserved_units"] == 0
    assert sum(r["count"] for r in values(engine, m.rate_limit_buckets) if r["action"] == "failure:86400") == 1


def test_unknown_can_recover_to_success_without_double_failure_count(engine):
    g = graph(engine)
    s = service(engine, [g["owner"]])
    reserve(s, g)
    dispatch(engine, g)
    s.retain_unknown(g["owner"], g["run"])
    result = s.settle(g["owner"], g["run"], outcome="succeeded", usage=TOKENS)
    assert result["state"] == "settled"
    assert values(engine, m.memberships)[0]["consumed_units"] == 1


def test_cross_day_price_change_and_append_only_adjustment(engine):
    now = [NOW]
    g = graph(engine)
    s = service(engine, [g["owner"]], now)
    reserve(s, g)
    dispatch(engine, g)
    now[0] += timedelta(days=35)
    s.settings = configuration([g["owner"]], RR_MODEL_INPUT_MICROUSD_PER_MILLION_TOKENS=999999,
                               RR_MODEL_PRICE_VERSION="synthetic-v2")
    result = s.settle(g["owner"], g["run"], outcome="failed")
    assert result["actual_microusd"] == 3
    change = s.adjust(g["owner"], g["run"], adjustment_key="trusted-usage-1", usage=TOKENS)
    assert change["delta_microusd"] == -1
    assert s.adjust(g["owner"], g["run"], adjustment_key="trusted-usage-1", usage=TOKENS) == change
    assert values(engine, m.usage_reservations)[0]["actual_microusd"] == 3
    assert {b["bucket_key"] for b in values(engine, m.budget_buckets)} == {"day:2026-10-20", "month:2026-10"}
    assert all(b["spent_microusd"] == 2 for b in values(engine, m.budget_buckets))


def test_above_estimate_halts_future_real_requests(engine):
    g = graph(engine)
    s = service(engine, [g["owner"]])
    reserve(s, g)
    dispatch(engine, g)
    s.settle(g["owner"], g["run"], outcome="failed", usage={"prompt_tokens": 10000, "completion_tokens": 10000, "total_tokens": 20000})
    assert values(engine, m.usage_controls)[0]["halted"] is True
    with pytest.raises(ApiError, match="BUDGET_EXHAUSTED"):
        reserve(s, g, another_run(engine, g))


@pytest.mark.parametrize("condition,code", [("invite", "REAL_AI_NOT_ALLOWED"), ("disabled", "REAL_AI_NOT_ALLOWED"),
    ("budget", "REAL_AI_NOT_ALLOWED"), ("price", "REAL_AI_NOT_ALLOWED"), ("expired", "MEMBERSHIP_REQUIRED"),
    ("revoked", "MEMBERSHIP_REQUIRED"), ("quota", "QUOTA_EXHAUSTED"), ("cancelled", "USAGE_CONFLICT")])
def test_authorization_fails_closed(engine, condition, code):
    g = graph(engine, units=0 if condition == "quota" else 20)
    changes = {}
    if condition == "disabled": changes["REAL_AI_ENABLED"] = False
    if condition == "budget": changes["RR_DAILY_BUDGET_MICROUSD"] = 0
    if condition == "price": changes["RR_MODEL_PRICE_VERSION"] = None
    s = service(engine, [] if condition == "invite" else [g["owner"]], **changes)
    with engine.begin() as conn:
        if condition == "expired": conn.execute(m.memberships.update().values(valid_from=NOW - timedelta(days=30), valid_until=NOW))
        if condition == "revoked": conn.execute(m.memberships.update().values(revoked_at=NOW))
        if condition == "cancelled": conn.execute(m.runs.update().values(state="cancelled"))
    with pytest.raises(ApiError, match=code): reserve(s, g)
    assert values(engine, m.usage_reservations) == []
    assert values(engine, m.memberships)[0]["reserved_units"] == 0


def test_fake_needs_membership_but_never_reserves_supplier_budget(engine):
    g = graph(engine, mode="fake")
    s = service(engine, [], RR_MODE="sandbox", REAL_AI_ENABLED=False, RR_DAILY_BUDGET_MICROUSD=0)
    reservation = reserve(s, g)
    assert reservation["cost_upper_bound_microusd"] == 0
    assert values(engine, m.usage_buckets) == []
    s.settle(g["owner"], g["run"], outcome="succeeded", usage=TOKENS)
    assert values(engine, m.memberships)[0]["consumed_units"] == 1
    assert all(b["spent_microusd"] == 0 for b in values(engine, m.budget_buckets))


def test_concurrency_limits_and_expired_slots(engine):
    now = [NOW]
    a, b, c = graph(engine), graph(engine), graph(engine)
    s = service(engine, [g["owner"] for g in (a, b, c)], now)
    reserve(s, a)
    with pytest.raises(ApiError, match="RUN_ACTIVE"): reserve(s, a, another_run(engine, a))
    reserve(s, b)
    with pytest.raises(ApiError, match="RUN_ACTIVE"): reserve(s, c)
    now[0] += timedelta(seconds=241)
    reserve(s, c)
    assert next(m for m in values(engine, m.memberships) if m["owner_id"] == c["owner"])["reserved_units"] == 1
    # Late settlement must not clear a slot already reassigned to another run.
    s.settle(a["owner"], a["run"], outcome="failed")
    assert any(slot["scope"] == "global" and slot["run_id"] == c["run"] for slot in values(engine, m.concurrency_slots))


def test_failed_reserve_attempts_persist_minute_and_hour_limits(engine):
    now = [NOW]
    g = graph(engine, units=0)
    s = service(engine, [g["owner"]], now)
    for _ in range(3):
        with pytest.raises(ApiError, match="QUOTA_EXHAUSTED"): reserve(s, g)
    with pytest.raises(ApiError, match="RATE_LIMITED"): reserve(s, g)
    for i in range(17):
        now[0] += timedelta(minutes=1)
        with pytest.raises(ApiError, match="QUOTA_EXHAUSTED"): reserve(s, g)
    now[0] += timedelta(minutes=1)
    with pytest.raises(ApiError, match="RATE_LIMITED"): reserve(s, g)


def test_failure_daily_cap_and_next_utc_day(engine):
    now = [NOW]
    g = graph(engine)
    s = service(engine, [g["owner"]], now)
    for _ in range(10):
        rid = another_run(engine, g)
        reserve(s, g, rid)
        s.settle(g["owner"], rid, outcome="failed")
        now[0] += timedelta(minutes=1)
    with pytest.raises(ApiError, match="RATE_LIMITED"): reserve(s, g)
    now[0] += timedelta(days=1)
    reserve(s, g)


def test_original_membership_settles_after_expiry_and_account_deletion(engine):
    g = graph(engine)
    s = service(engine, [g["owner"]])
    reserve(s, g)
    dispatch(engine, g)
    with engine.begin() as conn:
        conn.execute(m.users.update().values(disabled_at=NOW))
        conn.execute(m.packets.update().values(deleted_at=NOW))
        conn.execute(m.memberships.update().values(revoked_at=NOW))
    assert s.settle(g["owner"], g["run"], outcome="failed", usage=TOKENS)["actual_microusd"] == 2


def test_export_rate_limit_has_no_membership_dependency(engine):
    g = graph(engine, units=0)
    for _ in range(10):
        with engine.begin() as conn: rates.consume(conn, g["owner"], "export", NOW)
    with pytest.raises(ApiError, match="RATE_LIMITED"):
        with engine.begin() as conn: rates.consume(conn, g["owner"], "export", NOW)


def test_two_buckets_and_slots_roll_back_together(engine):
    g = graph(engine)
    s = service(engine, [g["owner"]])
    with engine.begin() as conn:
        conn.execute(m.budget_buckets.update().where(m.budget_buckets.c.bucket_key.like("month:%"))
                     .values(limit_microusd=2))
    with pytest.raises(ApiError, match="BUDGET_EXHAUSTED"): reserve(s, g)
    assert values(engine, m.usage_reservations) == []
    assert values(engine, m.concurrency_slots) == []
    assert values(engine, m.memberships)[0]["reserved_units"] == 0
    assert all(b["reserved_microusd"] == 0 for b in values(engine, m.budget_buckets))


def test_settlement_database_failure_rolls_back_and_retry_charges_once(engine):
    g = graph(engine)
    s = service(engine, [g["owner"]])
    reserve(s, g)
    dispatch(engine, g)
    def fail(conn, cursor, statement, parameters, context, executemany):
        if statement.startswith("UPDATE rr_usage_details"):
            raise RuntimeError("injected transaction failure")
    sa.event.listen(engine, "before_cursor_execute", fail)
    try:
        with pytest.raises(RuntimeError): s.settle(g["owner"], g["run"], outcome="succeeded", usage=TOKENS)
    finally:
        sa.event.remove(engine, "before_cursor_execute", fail)
    assert values(engine, m.usage_reservations)[0]["state"] == "reserved"
    assert values(engine, m.memberships)[0]["consumed_units"] == 0
    assert all(b["spent_microusd"] == 0 for b in values(engine, m.budget_buckets))
    s.settle(g["owner"], g["run"], outcome="succeeded", usage=TOKENS)
    assert values(engine, m.memberships)[0]["consumed_units"] == 1


def test_reserve_replay_requires_same_bounds_and_owner(engine):
    g = graph(engine)
    s = service(engine, [g["owner"]])
    reserve(s, g)
    with pytest.raises(ApiError, match="USAGE_CONFLICT"):
        s.reserve(g["owner"], g["run"], input_bound=999, output_limit=1000)
    other = graph(engine)
    with pytest.raises(ApiError, match="NOT_FOUND"):
        s.reserve(other["owner"], g["run"], input_bound=1000, output_limit=1000)


def test_integer_cost_rounds_up_and_rejects_float():
    from referral_review.usage.service import cost
    assert cost(1, 1, 1, 1) == 1
    assert cost(1000000, 1000000, 3, 5) == 8
    with pytest.raises(ApiError): cost(1.0, 0, 1, 1)
