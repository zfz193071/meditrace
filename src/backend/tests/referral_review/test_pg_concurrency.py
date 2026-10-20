"""Real two-connection races. Missing PostgreSQL is a skip, never a pass."""

from concurrent.futures import ThreadPoolExecutor
import os
from threading import Barrier
from uuid import uuid4

import pytest
import sqlalchemy as sa

from referral_review.persistence import models as m
from referral_review.persistence.database import transaction
from referral_review.persistence.migrations import HEAD, upgrade
from referral_review.persistence.repository import CapacityExceeded, RevisionConflict, save_revision
from referral_review.persistence.test_database import isolated_database, test_url as configured_test_url
from test_persistence import NOW, BUCKETS, seed, reserve


@pytest.fixture
def pg():
    if not os.getenv("TEST_DATABASE_URL"):
        pytest.skip("TEST_DATABASE_URL missing; real PostgreSQL races remain unverified")
    with isolated_database(configured_test_url()) as engine:
        with transaction(engine) as c:
            upgrade(c, HEAD)
        yield engine


def race(engine, operations):
    barrier = Barrier(2)

    def execute(operation):
        with transaction(engine) as c:
            # Establish two different server transactions/connections before release.
            c.exec_driver_sql("SELECT txid_current()")
            barrier.wait(timeout=10)
            try:
                operation(c)
                return "success"
            except (RevisionConflict, CapacityExceeded):
                return "conflict"

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(execute, operation) for operation in operations]
        return [future.result(timeout=30) for future in futures]


def test_two_transactions_cannot_overwrite_revision(pg):
    with transaction(pg) as c:
        graph = seed(c)
    def operation(c):
        save_revision(c, owner_id=graph["owner"], packet_id=graph["packet"], expected_revision=1, document_ids=[graph["document"]], now=NOW)
    assert sorted(race(pg, [operation, operation])) == ["conflict", "success"]
    with transaction(pg) as c:
        assert c.execute(sa.select(m.packets.c.current_revision)).scalar_one() == 2
        assert c.execute(sa.select(sa.func.count()).select_from(m.revisions)).scalar_one() == 2


def test_two_transactions_cannot_overdraw_one_membership(pg):
    with transaction(pg) as c:
        graph = seed(c, units=1, budget=1000)
        second_run = uuid4()
        original = dict(c.execute(sa.select(m.runs)).mappings().one())
        c.execute(m.runs.insert().values(**(original | {"id": second_run, "input_hash": "b" * 64})))
    assert sorted(race(pg, [lambda c: reserve(c, graph), lambda c: reserve(c, graph, run_id=second_run)])) == ["conflict", "success"]
    with transaction(pg) as c:
        assert c.execute(sa.select(m.memberships.c.reserved_units)).scalar_one() == 1
        assert c.execute(sa.select(sa.func.count()).select_from(m.usage_reservations)).scalar_one() == 1


def test_different_accounts_cannot_overdraw_shared_budget_with_reversed_keys(pg):
    with transaction(pg) as c:
        first, second = seed(c), seed(c)
    assert sorted(race(pg, [lambda c: reserve(c, first), lambda c: reserve(c, second, bucket_keys=list(reversed(BUCKETS)))])) == ["conflict", "success"]
    with transaction(pg) as c:
        assert c.execute(sa.select(m.budget_buckets.c.reserved_microusd)).scalars().all() == [60, 60]
        assert c.execute(sa.select(sa.func.sum(m.memberships.c.reserved_units))).scalar_one() == 1
        assert c.execute(sa.select(sa.func.count()).select_from(m.usage_reservations)).scalar_one() == 1
