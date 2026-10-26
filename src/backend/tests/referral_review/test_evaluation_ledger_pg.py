"""Separate processes and connections compete for evaluation/workspace budgets."""
import multiprocessing
from datetime import timedelta
from uuid import uuid4

import pytest
import sqlalchemy as sa

from referral_review.errors import ApiError
from referral_review.persistence import models as m
from referral_review.persistence.database import create_engine
from referral_review.usage import rates
from referral_review.schemas import ErrorCode
from test_evaluation_ledger import ledger, batch, attempt, SAMPLE
from test_usage import graph, service, values, TOKENS
from test_usage_pg import pg
from test_persistence import NOW
from test_evaluation_slots import active_holders, evaluate

_BARRIER = None


def initialize(barrier):
    global _BARRIER
    _BARRIER = barrier


def execute(payload):
    url, schema, now, operation, bid, sample, owner, run = payload
    engine = create_engine(url, schema=schema)
    try:
        s = ledger(engine, [now])
        _BARRIER.wait(timeout=20)
        try:
            if operation in ("guarded_dispatch", "rollback_guarded_dispatch"):
                with s._transaction() as conn:
                    rates.lock_user(conn, owner)
                    s.open_batch(bid, plan_hash="a" * 64, max_cost_usd="0.01", connection=conn)
                    row = s.reserve(bid, sample_hash=sample, input_bound=1000, output_limit=1000, connection=conn)
                    s.record_dispatch(bid, row["id"], connection=conn)
                    if operation == "rollback_guarded_dispatch":
                        raise ApiError(ErrorCode.USAGE_CONFLICT)
            elif operation == "workspace":
                service(engine, [owner], [now]).reserve(owner, run, input_bound=1000, output_limit=1000)
            elif operation == "dispatch":
                s.record_dispatch(bid, run)
            elif operation == "settle":
                s.settle(bid, run, outcome="succeeded", usage=TOKENS)
            elif operation == "adjust":
                s.adjust(bid, run, adjustment_key=sample, usage=TOKENS)
            else:
                attempt(s, bid, sample)
            return "success"
        except ApiError as exc:
            return exc.code.value
    finally:
        engine.dispose()


def race(engine, tasks, *, now=NOW):
    with engine.connect() as conn:
        schema = conn.execute(sa.text("select current_schema()")).scalar_one()
    ctx = multiprocessing.get_context("spawn")
    with ctx.Pool(len(tasks), initializer=initialize, initargs=(ctx.Barrier(len(tasks)),)) as pool:
        return pool.map_async(execute, [(engine.url.render_as_string(hide_password=False), schema, now, *task)
                                       for task in tasks]).get(timeout=60)


@pytest.mark.parametrize("shared_batch", [False, True])
def test_processes_cannot_exceed_evaluation_or_global_cap(pg, shared_batch):
    s = ledger(pg)
    bids = [batch(s, "0.000003") for _ in range(3)]
    if not shared_batch:
        with pg.begin() as conn:
            for key in ("day:2026-10-20", "month:2026-10"):
                conn.execute(m.budget_buckets.insert().values(bucket_key=key, limit_microusd=3))
    tasks = [("reserve", bids[0] if shared_batch else bids[i], uuid4().hex * 2, None, None) for i in range(3)]
    result = race(pg, tasks)
    assert result.count("success") == 1 and result.count("BUDGET_EXHAUSTED") == 2
    assert len(values(pg, m.evaluation_attempts)) == 1
    assert all(b["reserved_microusd"] == 3 for b in values(pg, m.budget_buckets))


def test_workspace_and_evaluation_processes_share_budget(pg):
    g = graph(pg)
    s = ledger(pg)
    bid = batch(s)
    with pg.begin() as conn:
        conn.execute(m.budget_buckets.update().values(limit_microusd=3))
    result = race(pg, [("reserve", bid, SAMPLE, None, None), ("workspace", None, None, g["owner"], g["run"])])
    assert sorted(result) == ["BUDGET_EXHAUSTED", "success"]
    assert len(values(pg, m.evaluation_attempts)) + len(values(pg, m.usage_reservations)) == 1
    assert all(b["reserved_microusd"] == 3 for b in values(pg, m.budget_buckets))


def test_process_replays_claim_once_and_settle_once(pg):
    s = ledger(pg)
    bid = batch(s)
    assert race(pg, [("reserve", bid, SAMPLE, None, None)] * 3) == ["success"] * 3
    rows = values(pg, m.evaluation_attempts)
    assert len(rows) == 1
    task = (bid, None, None, rows[0]["id"])
    result = race(pg, [("dispatch", *task)] * 3)
    assert result.count("success") == 1 and result.count("USAGE_CONFLICT") == 2
    assert race(pg, [("settle", *task)] * 3) == ["success"] * 3
    assert all(b["reserved_microusd"] == 0 and b["spent_microusd"] == 2 for b in values(pg, m.budget_buckets))
    assert values(pg, m.evaluation_batches)[0]["spent_microusd"] == 2


@pytest.mark.parametrize("same_key", [True, False])
def test_concurrent_adjustments_change_budget_once(pg, same_key):
    s = ledger(pg)
    bid = batch(s)
    row = attempt(s, bid)
    s.record_dispatch(bid, row["id"])
    original = s.settle(bid, row["id"], outcome="failed")
    tasks = [("adjust", bid, "one" if same_key else str(i), None, row["id"]) for i in range(3)]
    assert race(pg, tasks) == ["success"] * 3
    assert values(pg, m.evaluation_attempts) == [original]
    assert len(values(pg, m.evaluation_adjustments)) == (1 if same_key else 3)
    assert sum(r["delta_microusd"] for r in values(pg, m.evaluation_adjustments)) == -1
    assert all(b["spent_microusd"] == 2 for b in values(pg, m.budget_buckets))
    assert values(pg, m.evaluation_batches)[0]["spent_microusd"] == 2


@pytest.mark.parametrize("mode", ["real", "fake"])
def test_workspace_and_evaluation_processes_share_two_dispatch_slots(pg, mode):
    graphs = [graph(pg, mode=mode) for _ in range(2)]
    s = ledger(pg)
    tasks = [("workspace", None, None, g["owner"], g["run"]) for g in graphs]
    for _ in range(2):
        bid = batch(s)
        row = attempt(s, bid)
        tasks.append(("dispatch", bid, None, None, row["id"]))
    result = race(pg, tasks)
    assert result.count("success") == result.count("RUN_ACTIVE") == 2
    assert active_holders(pg, NOW) == 2
    workspace_winners = len(values(pg, m.usage_reservations))
    evaluation_winners = sum(r["state"] == "dispatched" for r in values(pg, m.evaluation_attempts))
    assert workspace_winners + evaluation_winners == 2
    assert all(b["reserved_microusd"] == 6 + (3 * workspace_winners if mode == "real" else 0)
               for b in values(pg, m.budget_buckets))


def test_expired_evaluation_completion_racing_new_claim_preserves_live_lease(pg):
    now = [NOW]
    s = ledger(pg, now)
    old_batch = batch(s)
    old = evaluate(s, old_batch)
    s.settle(old_batch, old["id"], outcome="unknown")
    now[0] += timedelta(seconds=240)
    new_batch = batch(s)
    new = attempt(s, new_batch)
    result = race(pg, [("settle", old_batch, None, None, old["id"]),
                       ("dispatch", new_batch, None, None, new["id"])], now=now[0])
    assert result == ["success", "success"]
    assert active_holders(pg, now[0]) == 1
    assert any(r["attempt_id"] == new["id"] for r in values(pg, m.evaluation_slots))


@pytest.mark.parametrize("rollback", [False, True])
def test_user_guard_and_composed_transaction_commit_once_across_processes(pg, rollback):
    g = graph(pg)
    bid = uuid4()
    other = "rollback_guarded_dispatch" if rollback else "guarded_dispatch"
    result = race(pg, [("guarded_dispatch", bid, SAMPLE, g["owner"], None),
                       (other, bid, SAMPLE, g["owner"], None)])
    assert sorted(result) == ["USAGE_CONFLICT", "success"]
    assert len(values(pg, m.evaluation_attempts)) == 1
    assert values(pg, m.evaluation_attempts)[0]["state"] == "dispatched"
    assert values(pg, m.evaluation_batches)[0]["reserved_microusd"] == 3
    assert all(b["reserved_microusd"] == 3 for b in values(pg, m.budget_buckets))
    assert active_holders(pg, NOW) == 1
