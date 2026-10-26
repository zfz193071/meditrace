"""Financial state tests only. No model client, transport, secrets or grants."""
from datetime import timedelta
from uuid import uuid4

import pytest
import sqlalchemy as sa

from referral_review.errors import ApiError
from referral_review.evaluation.ledger import EvaluationLedger, cap_microusd
from referral_review.persistence import models as m
from referral_review.persistence.migrations import HEAD, upgrade
from test_persistence import engine, empty_engine, NOW, seed
from test_usage import configuration, graph, service, reserve as workspace_reserve, values, TOKENS

PLAN = "a" * 64
SAMPLE = "b" * 64


def ledger(engine, now=None, **changes):
    now = now if now is not None else [NOW]
    return EvaluationLedger(engine, configuration([uuid4()], **changes), lambda: now[0])


def batch(s, cap="0.000006"):
    bid = uuid4()
    s.open_batch(bid, plan_hash=PLAN, max_cost_usd=cap)
    return bid


def attempt(s, bid, sample=SAMPLE):
    return s.reserve(bid, sample_hash=sample, input_bound=1000, output_limit=1000)


@pytest.mark.parametrize("cap", [None, 1, True, "0", "-1", "NaN", "Infinity", "1e100", "1e-100", "invalid"])
def test_invalid_cap_is_rejected(cap):
    with pytest.raises(ApiError, match="SCHEMA_INVALID"):
        cap_microusd(cap)


def test_cap_rounds_down_not_above_authorization():
    assert cap_microusd("0.000001999") == 1
    assert cap_microusd("1.12") == 1_120_000


def test_batch_identity_cannot_raise_cap_or_change_plan(engine):
    s = ledger(engine)
    bid = batch(s)
    old = values(engine, m.evaluation_batches)[0]
    assert s.open_batch(bid, plan_hash=PLAN, max_cost_usd="0.000006") == old
    for cap, plan in [("1", PLAN), ("0.000006", "c" * 64)]:
        with pytest.raises(ApiError, match="USAGE_CONFLICT"):
            s.open_batch(bid, plan_hash=plan, max_cost_usd=cap)
    assert values(engine, m.evaluation_batches) == [old]


def test_independent_cap_and_shared_budget_idempotency(engine):
    s = ledger(engine)
    bid = batch(s, "0.000003")
    first = attempt(s, bid)
    assert attempt(s, bid) == first
    with pytest.raises(ApiError, match="USAGE_CONFLICT"):
        s.reserve(bid, sample_hash=SAMPLE, input_bound=1001, output_limit=1000)
    with pytest.raises(ApiError, match="BUDGET_EXHAUSTED"):
        attempt(s, bid, "c" * 64)
    assert len(values(engine, m.evaluation_attempts)) == 1
    assert all(b["reserved_microusd"] == 3 for b in values(engine, m.budget_buckets))
    assert values(engine, m.memberships) == []  # No fabricated account/order/quota.
    s.record_dispatch(bid, first["id"])
    with pytest.raises(ApiError, match="USAGE_CONFLICT"):
        s.record_dispatch(bid, first["id"])
    result = s.settle(bid, first["id"], outcome="succeeded", usage=TOKENS)
    assert result["state"] == "settled" and result["actual_microusd"] == 2
    assert result["prompt_tokens"] == result["completion_tokens"] == 500
    assert s.settle(bid, first["id"], outcome="succeeded", usage=TOKENS) == result
    assert attempt(s, bid) == result  # Replay does not reset an attempt.
    assert all((b["reserved_microusd"], b["spent_microusd"]) == (0, 2) for b in values(engine, m.budget_buckets))
    with pytest.raises(ApiError, match="USAGE_CONFLICT"):
        s.settle(bid, first["id"], outcome="failed", usage=TOKENS)


@pytest.mark.parametrize("evaluation_first", [False, True])
def test_evaluation_and_workspace_share_the_same_budget(engine, evaluation_first):
    g = graph(engine)
    with engine.begin() as conn:
        conn.execute(m.budget_buckets.update().values(limit_microusd=3))
    s, w = ledger(engine), service(engine, [g["owner"]])
    bid = batch(s)
    first, second = (lambda: attempt(s, bid)), (lambda: workspace_reserve(w, g))
    if not evaluation_first:
        first, second = second, first
    first()
    with pytest.raises(ApiError, match="BUDGET_EXHAUSTED"):
        second()
    assert all(b["reserved_microusd"] == 3 for b in values(engine, m.budget_buckets))
    assert len(values(engine, m.evaluation_attempts)) == int(evaluation_first)
    assert values(engine, m.memberships)[0]["reserved_units"] == int(not evaluation_first)


@pytest.mark.parametrize("outcome,dispatched,usage,state,spent", [
    ("cancelled", False, None, "released", 0), ("failed", False, None, "released", 0),
    ("failed", True, TOKENS, "settled", 2), ("failed", True, None, "estimated_spent", 3),
    ("succeeded", True, None, "estimated_spent", 3),
])
def test_settlement_paths(engine, outcome, dispatched, usage, state, spent):
    s = ledger(engine)
    bid = batch(s)
    row = attempt(s, bid)
    if dispatched:
        s.record_dispatch(bid, row["id"])
    final = s.settle(bid, row["id"], outcome=outcome, usage=usage)
    assert (final["state"], final["actual_microusd"]) == (state, spent)
    assert all((b["reserved_microusd"], b["spent_microusd"]) == (0, spent) for b in values(engine, m.budget_buckets))
    assert (values(engine, m.evaluation_batches)[0]["reserved_microusd"], values(engine, m.evaluation_batches)[0]["spent_microusd"]) == (0, spent)


def test_crash_recovery_releases_only_undispatched_and_retains_unknown(engine):
    now = [NOW]
    s = ledger(engine, now)
    bid = batch(s)
    undispatched, dispatched = attempt(s, bid), attempt(s, bid, "c" * 64)
    s.record_dispatch(bid, dispatched["id"])
    assert s.recover() == []
    now[0] += timedelta(seconds=240)
    assert {row["state"] for row in s.recover()} == {"released", "retained_unknown"}
    assert s.recover() == []  # Waiting unknown rows cannot starve other due work.
    assert all(b["reserved_microusd"] == 3 and b["spent_microusd"] == 0 for b in values(engine, m.budget_buckets))
    with pytest.raises(ApiError, match="USAGE_CONFLICT"):
        s.record_dispatch(bid, undispatched["id"])
    now[0] += timedelta(hours=24)
    result = s.recover()
    assert len(result) == 1 and result[0]["state"] == "estimated_spent"
    assert s.recover() == []
    assert all(b["reserved_microusd"] == 0 and b["spent_microusd"] == 3 for b in values(engine, m.budget_buckets))


def test_unknown_can_settle_after_config_change_against_original_buckets(engine):
    now = [NOW]
    s = ledger(engine, now)
    bid = batch(s)
    row = attempt(s, bid)
    s.record_dispatch(bid, row["id"])
    old = s.settle(bid, row["id"], outcome="unknown")
    assert s.settle(bid, row["id"], outcome="unknown") == old
    now[0] += timedelta(days=35)
    s.settings = configuration([], REAL_AI_ENABLED=False, RR_MODEL_INPUT_MICROUSD_PER_MILLION_TOKENS=999999)
    result = s.settle(bid, row["id"], outcome="failed", usage=TOKENS)
    assert result["actual_microusd"] == 2
    assert {b["bucket_key"] for b in values(engine, m.budget_buckets)} == {"day:2026-10-20", "month:2026-10"}


def test_actual_overrun_halts_both_ledgers_without_hiding_spend(engine):
    g = graph(engine)
    s = ledger(engine)
    bid = batch(s)
    row = attempt(s, bid)
    s.record_dispatch(bid, row["id"])
    result = s.settle(bid, row["id"], outcome="failed",
        usage={"prompt_tokens": 10000, "completion_tokens": 10000, "total_tokens": 20000})
    assert result["actual_microusd"] == 30
    assert values(engine, m.usage_controls)[0]["halted"] is True
    with pytest.raises(ApiError, match="BUDGET_EXHAUSTED"):
        workspace_reserve(service(engine, [g["owner"]]), g)
    with pytest.raises(ApiError, match="BUDGET_EXHAUSTED"):
        attempt(s, batch(s, "1"))


@pytest.mark.parametrize("change", ["expired", "midnight", "halted", "price", "disabled"])
def test_dispatch_marker_checks_current_constraints(engine, change):
    now = [NOW + timedelta(hours=23, minutes=59)]
    s = ledger(engine, now)
    bid = batch(s)
    row = attempt(s, bid)
    if change == "expired": now[0] += timedelta(seconds=240)
    if change == "midnight": now[0] += timedelta(minutes=1)
    if change == "halted":
        with engine.begin() as conn: conn.execute(m.usage_controls.update().values(halted=True))
    if change == "price": s.settings = configuration([uuid4()], RR_MODEL_PRICE_VERSION="new")
    if change == "disabled": s.settings = configuration([uuid4()], REAL_AI_ENABLED=False)
    with pytest.raises(ApiError): s.record_dispatch(bid, row["id"])
    assert values(engine, m.evaluation_attempts)[0]["state"] == "reserved"


def test_invalid_state_usage_and_cross_batch_are_rejected(engine):
    s = ledger(engine)
    bid = batch(s)
    row = attempt(s, bid)
    for outcome, usage in [("succeeded", TOKENS), ("unknown", None), ("failed", TOKENS),
                           ("cancelled", TOKENS), ("failed", {"prompt_tokens": -1})]:
        with pytest.raises(ApiError): s.settle(bid, row["id"], outcome=outcome, usage=usage)
    with pytest.raises(ApiError, match="NOT_FOUND"):
        s.record_dispatch(batch(s), row["id"])
    s.record_dispatch(bid, row["id"])
    with pytest.raises(ApiError): s.settle(bid, row["id"], outcome="cancelled")
    assert all(b["reserved_microusd"] == 3 for b in values(engine, m.budget_buckets))


def test_shared_reservation_rolls_back_if_attempt_insert_fails(engine, monkeypatch):
    s = ledger(engine)
    bid = batch(s)
    def fail(*args, **kwargs): raise RuntimeError("synthetic failure")
    monkeypatch.setattr(m.evaluation_attempts, "insert", fail)
    with pytest.raises(RuntimeError, match="synthetic failure"): attempt(s, bid)
    assert values(engine, m.evaluation_attempts) == []
    assert values(engine, m.budget_buckets) == []
    assert values(engine, m.evaluation_batches)[0]["reserved_microusd"] == 0


def test_upgrade_from_previous_head_preserves_existing_ledger(empty_engine):
    with empty_engine.begin() as conn:
        upgrade(conn, "rr_0006")
        g = seed(conn)
        before = dict(conn.execute(sa.select(m.memberships).where(m.memberships.c.id == g["member"])).mappings().one())
        upgrade(conn, HEAD)
        after = dict(conn.execute(sa.select(m.memberships).where(m.memberships.c.id == g["member"])).mappings().one())
        assert before == after
        assert conn.execute(sa.select(sa.func.count()).select_from(m.evaluation_batches)).scalar_one() == 0


def test_caller_transaction_owns_all_financial_and_dispatch_writes(engine):
    s = ledger(engine)
    bid = uuid4()
    with pytest.raises(RuntimeError):
        with s._transaction() as conn:
            s.open_batch(bid, plan_hash=PLAN, max_cost_usd="0.01", connection=conn)
            row = s.reserve(bid, sample_hash=SAMPLE, input_bound=1000, output_limit=1000, connection=conn)
            s.record_dispatch(bid, row["id"], connection=conn)
            s.settle(bid, row["id"], outcome="succeeded", usage=TOKENS, connection=conn)
            raise RuntimeError("caller rolls back everything")
    for table in (m.evaluation_batches, m.evaluation_attempts, m.evaluation_buckets, m.evaluation_slots, m.budget_buckets):
        assert values(engine, table) == []
    with engine.connect() as conn:
        with pytest.raises(ValueError, match="Caller-owned transaction"):
            s.open_batch(bid, plan_hash=PLAN, max_cost_usd="0.01", connection=conn)
