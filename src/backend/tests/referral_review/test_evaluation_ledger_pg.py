"""Separate processes and connections compete for evaluation/workspace budgets."""
import multiprocessing
from uuid import uuid4

import pytest
import sqlalchemy as sa

from referral_review.errors import ApiError
from referral_review.persistence import models as m
from referral_review.persistence.database import create_engine
from test_evaluation_ledger import ledger, batch, attempt, SAMPLE
from test_usage import graph, service, values, TOKENS
from test_usage_pg import pg

_BARRIER = None


def initialize(barrier):
    global _BARRIER
    _BARRIER = barrier


def execute(payload):
    url, schema, operation, bid, sample, owner, run = payload
    engine = create_engine(url, schema=schema)
    try:
        s = ledger(engine)
        _BARRIER.wait(timeout=20)
        try:
            if operation == "workspace":
                service(engine, [owner]).reserve(owner, run, input_bound=1000, output_limit=1000)
            elif operation == "dispatch":
                s.record_dispatch(bid, run)
            elif operation == "settle":
                s.settle(bid, run, outcome="succeeded", usage=TOKENS)
            else:
                attempt(s, bid, sample)
            return "success"
        except ApiError as exc:
            return exc.code.value
    finally:
        engine.dispose()


def race(engine, tasks):
    with engine.connect() as conn:
        schema = conn.execute(sa.text("select current_schema()")).scalar_one()
    ctx = multiprocessing.get_context("spawn")
    with ctx.Pool(len(tasks), initializer=initialize, initargs=(ctx.Barrier(len(tasks)),)) as pool:
        return pool.map_async(execute, [(engine.url.render_as_string(hide_password=False), schema, *task)
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
