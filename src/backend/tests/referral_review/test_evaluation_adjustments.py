"""Late usage preserves history and changes only the original budget buckets."""
from datetime import timedelta

import pytest
import sqlalchemy as sa

from referral_review.errors import ApiError
from referral_review.persistence import models as m
from referral_review.persistence.migrations import HEAD, upgrade
from test_evaluation_ledger import ledger, batch, attempt
from test_persistence import engine, empty_engine, NOW
from test_usage import TOKENS, values


def estimated(s, bid):
    row = attempt(s, bid)
    s.record_dispatch(bid, row["id"])
    return s.settle(bid, row["id"], outcome="failed")


def test_late_correction_preserves_estimate_prices_and_original_month(engine):
    now = [NOW]
    s = ledger(engine, now)
    bid = batch(s)
    original = estimated(s, bid)
    now[0] += timedelta(days=40)
    disabled = ledger(engine, now, REAL_AI_ENABLED=False, RR_MODEL_INPUT_MICROUSD_PER_MILLION_TOKENS=99999)
    correction = disabled.adjust(bid, original["id"], adjustment_key="late-response", usage=TOKENS)
    assert correction["actual_microusd"] == 2 and correction["delta_microusd"] == -1
    assert disabled.adjust(bid, original["id"], adjustment_key="late-response", usage=TOKENS) == correction
    assert values(engine, m.evaluation_attempts) == [original]
    assert values(engine, m.evaluation_batches)[0]["spent_microusd"] == 2
    buckets = values(engine, m.budget_buckets)
    assert {b["bucket_key"] for b in buckets} == {"day:2026-10-20", "month:2026-10"}
    assert all((b["reserved_microusd"], b["spent_microusd"]) == (0, 2) for b in buckets)
    assert len(values(engine, m.evaluation_adjustments)) == 1
    # A different token count that rounds to the same cost still conflicts.
    with pytest.raises(ApiError, match="USAGE_CONFLICT"):
        disabled.adjust(bid, original["id"], adjustment_key="late-response",
                        usage=dict(prompt_tokens=501, completion_tokens=500, total_tokens=1001))


def test_overrun_halts_and_older_replay_never_reverts_newer_correction(engine):
    s = ledger(engine)
    bid = batch(s)
    original = estimated(s, bid)
    first = s.adjust(bid, original["id"], adjustment_key="one", usage=dict(prompt_tokens=9000, completion_tokens=9000, total_tokens=18000))
    assert first["actual_microusd"] == 27
    assert values(engine, m.usage_controls)[0]["halted"]
    s.adjust(bid, original["id"], adjustment_key="two", usage=TOKENS)
    assert s.adjust(bid, original["id"], adjustment_key="one",
                    usage=dict(prompt_tokens=9000, completion_tokens=9000, total_tokens=18000)) == first
    assert values(engine, m.evaluation_batches)[0]["spent_microusd"] == 2
    assert values(engine, m.usage_controls)[0]["halted"]  # No automatic reopening.
    assert len(values(engine, m.evaluation_adjustments)) == 2
    with pytest.raises(ApiError, match="BUDGET_EXHAUSTED"):
        attempt(s, bid, "c" * 64)


@pytest.mark.parametrize("state", ["reserved", "dispatched", "retained_unknown", "released"])
def test_only_dispatched_terminal_attempts_allow_correction(engine, state):
    s = ledger(engine)
    bid = batch(s)
    row = attempt(s, bid)
    if state in ("dispatched", "retained_unknown"):
        s.record_dispatch(bid, row["id"])
    if state == "retained_unknown": s.settle(bid, row["id"], outcome="unknown")
    if state == "released": s.settle(bid, row["id"], outcome="cancelled")
    with pytest.raises(ApiError, match="USAGE_CONFLICT"):
        s.adjust(bid, row["id"], adjustment_key="one", usage=TOKENS)
    assert values(engine, m.evaluation_adjustments) == []


@pytest.mark.parametrize("cap", ["batch", "global"])
def test_correction_halts_when_previously_released_budget_was_reused(engine, cap):
    s = ledger(engine)
    bid = batch(s, "0.000005" if cap == "batch" else "0.000006")
    first = attempt(s, bid)
    s.record_dispatch(bid, first["id"])
    original = s.settle(bid, first["id"], outcome="succeeded", usage=TOKENS)
    if cap == "global":
        with engine.begin() as conn: conn.execute(m.budget_buckets.update().values(limit_microusd=5))
    pending = attempt(s, bid, "c" * 64)
    s.adjust(bid, first["id"], adjustment_key="correction",
             usage=dict(prompt_tokens=1000, completion_tokens=1000, total_tokens=2000))
    control = values(engine, m.usage_controls)[0]
    assert control["halted"] and control["reason"] == "ADJUSTMENT_EXCEEDS_BUDGET"
    with pytest.raises(ApiError, match="BUDGET_EXHAUSTED"):
        s.record_dispatch(bid, pending["id"])
    assert next(r for r in values(engine, m.evaluation_attempts) if r["id"] == first["id"]) == original
    assert values(engine, m.evaluation_batches)[0]["reserved_microusd"] == 3


def test_settled_correction_and_caller_rollback_are_atomic(engine):
    s = ledger(engine)
    bid = batch(s)
    row = attempt(s, bid)
    s.record_dispatch(bid, row["id"])
    original = s.settle(bid, row["id"], outcome="succeeded", usage=TOKENS)
    with pytest.raises(RuntimeError):
        with s._transaction() as conn:
            s.adjust(bid, row["id"], adjustment_key="one", usage=dict(prompt_tokens=0, completion_tokens=0, total_tokens=0), connection=conn)
            raise RuntimeError("injected")
    assert values(engine, m.evaluation_adjustments) == []
    assert values(engine, m.evaluation_batches)[0]["spent_microusd"] == 2
    correction = s.adjust(bid, row["id"], adjustment_key="one", usage=dict(prompt_tokens=0, completion_tokens=0, total_tokens=0))
    assert correction["delta_microusd"] == -2
    assert values(engine, m.evaluation_attempts) == [original]
    assert all(b["spent_microusd"] == 0 for b in values(engine, m.budget_buckets))


@pytest.mark.parametrize("operation", ["update", "delete"])
def test_adjustments_are_append_only_in_database(engine, operation):
    s = ledger(engine)
    bid = batch(s)
    original = estimated(s, bid)
    s.adjust(bid, original["id"], adjustment_key="one", usage=TOKENS)
    with pytest.raises(sa.exc.IntegrityError):
        with engine.begin() as conn:
            conn.execute(m.evaluation_adjustments.update().values(delta_microusd=0) if operation == "update"
                         else m.evaluation_adjustments.delete())
    assert values(engine, m.evaluation_adjustments)[0]["delta_microusd"] == -1


def test_additive_upgrade_from_slots_preserves_existing_rows(empty_engine):
    from uuid import uuid4
    bid = uuid4()
    with empty_engine.begin() as conn:
        upgrade(conn, "rr_0008")
        conn.execute(m.evaluation_batches.insert().values(id=bid, plan_hash="a" * 64, cap_microusd=10,
            model="synthetic", price_version="synthetic", input_price=1000, output_price=2000))
        upgrade(conn, HEAD)
    assert values(empty_engine, m.evaluation_batches)[0]["id"] == bid
    assert values(empty_engine, m.evaluation_adjustments) == []
