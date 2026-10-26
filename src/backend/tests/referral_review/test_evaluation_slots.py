"""Shared dispatch capacity and lease recovery, with no provider calls."""
from datetime import timedelta
from uuid import uuid4

import pytest
import sqlalchemy as sa

from referral_review.errors import ApiError
from referral_review.persistence import models as m
from referral_review.persistence.migrations import HEAD, upgrade
from referral_review.usage import slots
from test_persistence import engine, empty_engine, NOW, seed
from test_evaluation_ledger import ledger, batch, attempt
from test_usage import graph, service, reserve, values, TOKENS


def evaluate(s, bid, sample=None):
    row = attempt(s, bid, sample or uuid4().hex * 2)
    s.record_dispatch(bid, row["id"])
    return row


def active_holders(engine, now):
    workspace = {s["slot_number"] for s in values(engine, m.concurrency_slots)
                 if s["scope"] == "global" and s["run_id"] is not None and s["lease_expires_at"] > now}
    evaluation = {s["slot_number"] for s in values(engine, m.evaluation_slots)
                  if s["attempt_id"] is not None and s["lease_expires_at"] > now}
    assert not workspace & evaluation
    return len(workspace) + len(evaluation)


def test_two_evaluations_block_a_third_until_settlement(engine):
    s = ledger(engine)
    bid = batch(s, "0.000100")
    first = evaluate(s, bid)
    evaluate(s, bid)
    waiting = attempt(s, bid, "d" * 64)
    before = values(engine, m.budget_buckets)
    with pytest.raises(ApiError, match="RUN_ACTIVE"):
        s.record_dispatch(bid, waiting["id"])
    assert next(r for r in values(engine, m.evaluation_attempts) if r["id"] == waiting["id"])["state"] == "reserved"
    assert values(engine, m.budget_buckets) == before
    assert active_holders(engine, NOW) == 2
    s.settle(bid, first["id"], outcome="succeeded", usage=TOKENS)
    s.record_dispatch(bid, waiting["id"])
    assert active_holders(engine, NOW) == 2


@pytest.mark.parametrize("mode", ["real", "fake"])
@pytest.mark.parametrize("evaluation_first", [True, False])
def test_workspace_and_evaluation_share_capacity_in_both_orders(engine, mode, evaluation_first):
    a, b = graph(engine, mode=mode), graph(engine, mode=mode)
    w = service(engine, [a["owner"], b["owner"]])
    s = ledger(engine)
    bid = batch(s)
    if not evaluation_first: reserve(w, a)
    row = evaluate(s, bid)
    if evaluation_first: reserve(w, a)
    before = values(engine, m.budget_buckets)
    with pytest.raises(ApiError, match="RUN_ACTIVE"): reserve(w, b)
    assert values(engine, m.budget_buckets) == before
    assert next(r for r in values(engine, m.memberships) if r["owner_id"] == b["owner"])["reserved_units"] == 0
    assert active_holders(engine, NOW) == 2
    s.settle(bid, row["id"], outcome="failed", usage=TOKENS)
    reserve(w, b)
    assert active_holders(engine, NOW) == 2


def test_two_workspace_runs_block_evaluation_without_marking_dispatch(engine):
    a, b = graph(engine), graph(engine)
    w = service(engine, [a["owner"], b["owner"]])
    reserve(w, a)
    reserve(w, b)
    s = ledger(engine)
    bid = batch(s)
    row = attempt(s, bid)
    with pytest.raises(ApiError, match="RUN_ACTIVE"): s.record_dispatch(bid, row["id"])
    assert values(engine, m.evaluation_attempts)[0]["dispatched_at"] is None
    w.settle(a["owner"], a["run"], outcome="cancelled")
    s.record_dispatch(bid, row["id"])
    assert active_holders(engine, NOW) == 2


@pytest.mark.parametrize("replacement", ["workspace", "evaluation"])
def test_unknown_keeps_slot_until_expiry_and_late_settlement_preserves_replacement(engine, replacement):
    now = [NOW]
    s = ledger(engine, now)
    bid = batch(s, "0.000100")
    old = evaluate(s, bid)
    other = evaluate(s, bid)
    s.settle(bid, old["id"], outcome="unknown")
    now[0] += timedelta(seconds=239)
    waiting = attempt(s, bid, "d" * 64)
    with pytest.raises(ApiError, match="RUN_ACTIVE"): s.record_dispatch(bid, waiting["id"])
    assert active_holders(engine, now[0]) == 2
    now[0] += timedelta(seconds=1)
    if replacement == "workspace":
        g = graph(engine)
        reserve(service(engine, [g["owner"]], now), g)
    else:
        s.record_dispatch(bid, waiting["id"])
    evaluate(s, bid)
    assert active_holders(engine, now[0]) == 2
    s.settle(bid, old["id"], outcome="failed", usage=TOKENS)
    # Old workspace/evaluation occupants can coexist only as expired history;
    # neither old completion nor recovery may release the new live occupant.
    s.settle(bid, other["id"], outcome="failed", usage=TOKENS)
    assert active_holders(engine, now[0]) == 2
    assert s.recover() == []


def test_dispatch_lease_starts_at_claim_not_financial_reservation(engine):
    now = [NOW]
    s = ledger(engine, now)
    bid = batch(s)
    row = attempt(s, bid)
    now[0] += timedelta(seconds=100)
    dispatched = s.record_dispatch(bid, row["id"])
    assert dispatched["lease_expires_at"] == now[0] + slots.LEASE
    now[0] = NOW + timedelta(seconds=240)
    assert s.recover() == []
    assert active_holders(engine, now[0]) == 1
    now[0] += timedelta(seconds=100)
    assert s.recover()[0]["state"] == "retained_unknown"
    assert all(b["reserved_microusd"] == 3 for b in values(engine, m.budget_buckets))
    assert active_holders(engine, now[0]) == 0


def test_late_workspace_settlement_cannot_release_evaluation_holder(engine):
    now = [NOW]
    g = graph(engine)
    w = service(engine, [g["owner"]], now)
    reserve(w, g)
    now[0] += slots.LEASE
    s = ledger(engine, now)
    bid = batch(s)
    row = evaluate(s, bid)
    w.settle(g["owner"], g["run"], outcome="failed")
    assert active_holders(engine, now[0]) == 1
    assert any(r["attempt_id"] == row["id"] for r in values(engine, m.evaluation_slots))


def test_marker_failure_rolls_back_claim_and_settlement_failure_rolls_back_money(engine, monkeypatch):
    s = ledger(engine)
    bid = batch(s)
    row = attempt(s, bid)
    def fail(*args, **kwargs): raise RuntimeError("synthetic failure")
    with monkeypatch.context() as patch:
        patch.setattr(m.evaluation_attempts, "update", fail)
        with pytest.raises(RuntimeError, match="synthetic failure"): s.record_dispatch(bid, row["id"])
    assert values(engine, m.evaluation_slots) == []
    assert values(engine, m.concurrency_slots) == []
    assert values(engine, m.evaluation_attempts)[0]["state"] == "reserved"
    s.record_dispatch(bid, row["id"])
    with monkeypatch.context() as patch:
        patch.setattr(slots, "release_evaluation", fail)
        with pytest.raises(RuntimeError, match="synthetic failure"):
            s.settle(bid, row["id"], outcome="succeeded", usage=TOKENS)
    assert values(engine, m.evaluation_attempts)[0]["state"] == "dispatched"
    assert values(engine, m.evaluation_batches)[0]["spent_microusd"] == 0
    assert all(b["reserved_microusd"] == 3 for b in values(engine, m.budget_buckets))
    assert active_holders(engine, NOW) == 1


def test_upgrade_preserves_occupied_workspace_slots(empty_engine):
    with empty_engine.begin() as conn:
        upgrade(conn, "rr_0007")
        g = seed(conn)
        conn.execute(m.concurrency_slots.insert().values(scope="global", slot_number=0,
            run_id=g["run"], lease_expires_at=NOW + slots.LEASE))
        before = dict(conn.execute(sa.select(m.concurrency_slots)).mappings().one())
        upgrade(conn, HEAD)
        assert dict(conn.execute(sa.select(m.concurrency_slots)).mappings().one()) == before
    s = ledger(empty_engine)
    bid = batch(s)
    evaluate(s, bid)
    waiting = attempt(s, bid, "c" * 64)
    with pytest.raises(ApiError, match="RUN_ACTIVE"): s.record_dispatch(bid, waiting["id"])
    assert active_holders(empty_engine, NOW) == 2
