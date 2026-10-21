"""Real multi-process PostgreSQL races; never use production DATABASE_URL or SQLite."""
import multiprocessing
import os

import pytest
import sqlalchemy as sa

from referral_review.errors import ApiError
from referral_review.persistence import models as m
from referral_review.persistence.database import create_engine
from referral_review.persistence.migrations import HEAD, upgrade
from referral_review.persistence.test_database import isolated_database, test_url as configured_test_url
from test_usage import graph, another_run, service, values, dispatch, TOKENS

_BARRIER = None


def initialize(barrier):
    global _BARRIER
    _BARRIER = barrier


def execute(payload):
    url, schema, owners, owner, run, operation = payload
    engine = create_engine(url, schema=schema)
    try:
        ledger = service(engine, owners)
        _BARRIER.wait(timeout=20)
        try:
            if operation == "settle":
                ledger.settle(owner, run, outcome="succeeded", usage=TOKENS)
            else:
                ledger.reserve(owner, run, input_bound=1000, output_limit=1000)
            return "success"
        except ApiError as exc:
            return exc.code.value
    finally:
        engine.dispose()


@pytest.fixture
def pg():
    if not os.getenv("TEST_DATABASE_URL"):
        pytest.skip("TEST_DATABASE_URL missing; multi-process PostgreSQL ledger not verified")
    with isolated_database(configured_test_url()) as engine:
        with engine.begin() as conn: upgrade(conn, HEAD)
        yield engine


def race(engine, pairs, operation="reserve"):
    with engine.begin() as conn:
        schema = conn.execute(sa.text("select current_schema()")).scalar_one()
    owners = list({owner for owner, _ in pairs})
    ctx = multiprocessing.get_context("spawn")
    barrier = ctx.Barrier(len(pairs))
    with ctx.Pool(len(pairs), initializer=initialize, initargs=(barrier,)) as pool:
        tasks = [(engine.url.render_as_string(hide_password=False), schema, owners, owner, run, operation) for owner, run in pairs]
        return pool.map_async(execute, tasks).get(timeout=60)


@pytest.mark.parametrize("constraint,expected", [("account", 1), ("global", 2), ("budget", 1), ("quota", 1)])
def test_processes_cannot_overdraw(pg, constraint, expected):
    if constraint in ("account", "quota"):
        g = graph(pg, units=1 if constraint == "quota" else 20)
        pairs = [(g["owner"], g["run"])] + [(g["owner"], another_run(pg, g)) for _ in range(2)]
    else:
        graphs = [graph(pg) for _ in range(3)]
        pairs = [(g["owner"], g["run"]) for g in graphs]
    if constraint == "budget":
        with pg.begin() as conn: conn.execute(m.budget_buckets.update().values(limit_microusd=3))
    results = race(pg, pairs)
    assert results.count("success") == expected
    assert len(values(pg, m.usage_reservations)) == expected
    assert sum(row["reserved_units"] for row in values(pg, m.memberships)) == expected
    for bucket in values(pg, m.budget_buckets):
        assert bucket["reserved_microusd"] == expected * 3
        assert bucket["reserved_microusd"] <= bucket["limit_microusd"]


def test_process_replays_and_settlement_never_double_charge(pg):
    g = graph(pg)
    pairs = [(g["owner"], g["run"])] * 3
    assert race(pg, pairs) == ["success"] * 3
    assert len(values(pg, m.usage_reservations)) == 1
    dispatch(pg, g)
    assert race(pg, pairs, "settle") == ["success"] * 3
    assert values(pg, m.memberships)[0]["consumed_units"] == 1
    assert all(b["spent_microusd"] == 2 and b["reserved_microusd"] == 0 for b in values(pg, m.budget_buckets))
