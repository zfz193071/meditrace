"""Isolated transactional orchestration and durable Fake crash/replay coverage."""
import asyncio
from datetime import timedelta
import json
from pathlib import Path
import stat
import sys
from uuid import uuid4

import pytest
import sqlalchemy as sa

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "evals/referral-review"))
from referral_eval import planning as p, runner
from referral_eval.coordinator import EvaluationSession, recover_recordings, replay_recordings
from referral_eval.journal import Journal
from referral_review.extraction.adapters import FakeAdapter
from referral_review.errors import ApiError
from referral_review.persistence import models as m
from test_persistence import engine, empty_engine, NOW
from test_usage import configuration, values


@pytest.fixture
def setup(engine, tmp_path):
    owner = uuid4()
    with engine.begin() as conn:
        conn.execute(m.users.insert().values(id=owner, github_subject=str(owner), display_name="Synthetic", created_at=NOW))
    settings = configuration([owner], RR_ENVIRONMENT="test")
    plan = p.build_plan(batch_id=uuid4(), operator_id=owner, split="dev", output=tmp_path / "recordings",
        model=settings.model_id, price_version=settings.price_version, input_price=1000, output_price=2000,
        max_cost_usd="0.01", packet_keys=["dev-04", "dev-05"])
    approval = dict(approved_sha256=plan.sha256, approved_max_cost_usd="0.01", operator_id=owner)
    now = [NOW]
    return plan, settings, approval, now


def session(engine, setup, **kw):
    plan, settings, approval, now = setup
    return EvaluationSession(engine, settings, plan, approval=approval, clock=lambda: now[0], **kw)


def recover(engine, setup, settings=None):
    plan, configured, _, now = setup
    return recover_recordings(engine, settings or configured, plan, clock=lambda: now[0])


def fake():
    return FakeAdapter({"facts": []})


def test_commit_before_transport_single_dispatch_and_keyless_replay(engine, setup, monkeypatch):
    adapter = fake()
    complete = adapter.complete
    async def observed(request):
        assert values(engine, m.evaluation_attempts)[0]["state"] == "dispatched"
        assert values(engine, m.evaluation_batches)[0]["reserved_microusd"] > 0
        assert values(engine, m.evaluation_slots)[0]["attempt_id"] is not None
        return await complete(request)
    monkeypatch.setattr(adapter, "complete", observed)
    with session(engine, setup) as run:
        result = asyncio.run(run.execute("dev-04", adapter))
        repeated = asyncio.run(run.execute("dev-04", adapter))
    assert adapter.calls == 1 and repeated["repeated"]
    assert result["total"] == 2 and result["real_measurement"] is False
    assert [s["state"] for s in result["samples"]] == ["settled", "not_started"]
    assert values(engine, m.evaluation_batches)[0]["reserved_microusd"] == 0
    assert values(engine, m.memberships) == []
    root = Path(setup[0].output)
    assert stat.S_IMODE(root.stat().st_mode) == 0o700
    assert all(stat.S_IMODE(f.stat().st_mode) == 0o600 for f in root.iterdir())
    async def forbidden(*args): raise AssertionError("No adapter during replay")
    monkeypatch.setattr(FakeAdapter, "complete", forbidden)
    replay = asyncio.run(replay_recordings(setup[0]))
    assert replay["origin"] == "fake" and replay["provider"] == "replay"
    assert replay["summary"]["packets_total"] == 2
    assert replay["summary"]["successful"] == replay["summary"]["failed"] == 1
    assert replay["summary"]["facts"]["fn"] > 0


def test_dispatch_failure_rolls_back_operator_batch_budget_and_slots(engine, setup, monkeypatch):
    adapter = fake()
    with session(engine, setup) as run:
        dispatch = run.ledger.record_dispatch
        def fail(*args, **kwargs):
            dispatch(*args, **kwargs)
            raise RuntimeError("injected after marker")
        monkeypatch.setattr(run.ledger, "record_dispatch", fail)
        with pytest.raises(RuntimeError): asyncio.run(run.execute("dev-04", adapter))
    assert adapter.calls == 0
    for table in (m.evaluation_batches, m.evaluation_attempts, m.budget_buckets, m.evaluation_slots):
        assert values(engine, table) == []


@pytest.mark.parametrize("change", ["disabled", "invite", "price", "approval", "implementation"])
def test_each_dispatch_rechecks_operator_plan_and_configuration(engine, setup, monkeypatch, change):
    adapter = fake()
    with session(engine, setup) as run:
        if change == "disabled":
            with engine.begin() as conn: conn.execute(m.users.update().values(disabled_at=NOW))
        if change == "invite": run.settings = configuration([], RR_ENVIRONMENT="test")
        if change == "price": run.settings = configuration([setup[0].operator_id], RR_ENVIRONMENT="test", RR_MODEL_PRICE_VERSION="changed")
        if change == "approval": run.approval["approved_sha256"] = "0" * 64
        if change == "implementation": monkeypatch.setattr(p, "implementation_hash", lambda: "0" * 64)
        with pytest.raises((ValueError, ApiError)): asyncio.run(run.execute("dev-04", adapter))
    assert adapter.calls == 0 and values(engine, m.evaluation_attempts) == []


def test_recording_survives_failed_settlement_and_recovers_after_revocation(engine, setup, monkeypatch):
    adapter = fake()
    with session(engine, setup) as run:
        def fail(*args, **kw): raise RuntimeError("crash before settlement")
        monkeypatch.setattr(run.ledger, "settle", fail)
        with pytest.raises(RuntimeError): asyncio.run(run.execute("dev-04", adapter))
    assert (Path(setup[0].output) / "dev-04.json").exists()
    assert values(engine, m.evaluation_attempts)[0]["state"] == "dispatched"
    with engine.begin() as conn: conn.execute(m.users.update().values(disabled_at=NOW))
    disabled = configuration([], RR_ENVIRONMENT="test", REAL_AI_ENABLED=False,
                             RR_MODEL_INPUT_MICROUSD_PER_MILLION_TOKENS=99999)
    result = recover(engine, setup, disabled)
    assert result["samples"][0]["state"] == "settled"
    assert recover(engine, setup, disabled) == result
    assert adapter.calls == 1


def test_missing_recording_retains_unknown_and_never_redispatches(engine, setup, monkeypatch):
    adapter = fake()
    with session(engine, setup) as run:
        def fail(*args): raise OSError("disk failure")
        monkeypatch.setattr(run.journal, "write", fail)
        with pytest.raises(OSError): asyncio.run(run.execute("dev-04", adapter))
    assert recover(engine, setup)["samples"][0]["state"] == "dispatched"
    with session(engine, setup, resume=True) as run:
        assert asyncio.run(run.execute("dev-04", adapter))["repeated"]
    setup[3][0] += timedelta(seconds=241)
    assert recover(engine, setup)["samples"][0]["state"] == "retained_unknown"
    setup[3][0] += timedelta(hours=24)
    assert recover(engine, setup)["samples"][0]["state"] == "estimated_spent"
    assert adapter.calls == 1


@pytest.mark.parametrize("scenario,expected", [("invalid_json", "settled"), ("usage_missing", "estimated_spent"),
                                                ("truncated", "settled"), ("timeout", "retained_unknown")])
def test_failure_and_unknown_usage_are_recorded_without_fabricated_zero(engine, setup, scenario, expected):
    adapter = FakeAdapter({"facts": []}, scenario=scenario)
    with session(engine, setup) as run:
        result = asyncio.run(run.execute("dev-04", adapter))
    assert result["samples"][0]["state"] == expected
    assert result["samples"][0]["recorded"]
    if scenario == "timeout":
        assert result["samples"][0]["simulated_microusd"] is None
    else:
        assert result["samples"][0]["simulated_microusd"] > 0
    assert recover(engine, setup)["samples"][0]["state"] == expected


def test_cancelled_transport_records_unknown_then_propagates_cancellation(engine, setup, monkeypatch):
    adapter = fake()
    async def cancel(*args): raise asyncio.CancelledError
    monkeypatch.setattr(adapter, "complete", cancel)
    with session(engine, setup) as run:
        with pytest.raises(asyncio.CancelledError): asyncio.run(run.execute("dev-04", adapter))
    assert recover(engine, setup)["samples"][0]["state"] == "retained_unknown"


def test_closed_session_and_live_adapter_cannot_write_dispatch(engine, setup):
    class Live:
        mode = "real"
        async def complete(self, request): raise AssertionError("No network")
    with session(engine, setup) as run:
        with pytest.raises(ValueError, match="disabled"): asyncio.run(run.execute("dev-04", Live()))
    with pytest.raises(ValueError, match="closed"): asyncio.run(run.execute("dev-04", fake()))
    assert values(engine, m.evaluation_batches) == []


def test_non_test_configuration_cannot_even_create_journal(engine, setup):
    plan, settings, approval, now = setup
    settings = settings.model_copy(update={"environment": "development"})
    with pytest.raises(ValueError, match="isolated test"):
        EvaluationSession(engine, settings, plan, approval=approval)
    assert not Path(plan.output).exists()


def test_journal_lock_conflicting_plan_and_corruption_fail_closed(engine, setup, monkeypatch):
    with session(engine, setup) as run:
        with pytest.raises(BlockingIOError): Journal(setup[0], resume=True)
        def fail(*args, **kw): raise RuntimeError("settlement interrupted")
        monkeypatch.setattr(run.ledger, "settle", fail)
        with pytest.raises(RuntimeError): asyncio.run(run.execute("dev-04", fake()))
    changed = setup[0].model_copy(update={"operator_id": uuid4()})
    with pytest.raises(ValueError, match="different plan"): Journal(changed, resume=True)
    path = Path(setup[0].output) / "dev-04.json"
    data = json.loads(path.read_text())
    data["record"]["usage"]["prompt_tokens"] += 1
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="checksum"): recover(engine, setup)
    assert values(engine, m.evaluation_attempts)[0]["state"] == "dispatched"


def test_journal_rejects_links_and_overwrite(engine, setup, tmp_path):
    with session(engine, setup) as run:
        root = Path(setup[0].output)
        outside = tmp_path / "outside"
        outside.write_text("synthetic private sentinel")
        (root / "dev-04.json").symlink_to(outside)
        with pytest.raises(OSError): run.journal.read("dev-04.json")
        with pytest.raises(ValueError): run.journal.read("../outside")
        with pytest.raises(ValueError, match="immutable"): run.journal.write("binding.json", {"changed": True})
    assert outside.read_text() == "synthetic private sentinel"


def test_late_usage_does_not_overwrite_final_estimate_or_recover_other_batch(engine, setup, monkeypatch):
    from test_evaluation_ledger import ledger, batch, attempt
    other = ledger(engine, setup[3])
    other_batch = batch(other)
    other_row = attempt(other, other_batch)
    other.record_dispatch(other_batch, other_row["id"])
    with session(engine, setup) as run:
        settle = run.ledger.settle
        def fail(*args, **kw): raise RuntimeError("settlement interrupted")
        monkeypatch.setattr(run.ledger, "settle", fail)
        with pytest.raises(RuntimeError): asyncio.run(run.execute("dev-04", fake()))
        own = next(r for r in values(engine, m.evaluation_attempts) if r["batch_id"] == setup[0].batch_id)
        setup[3][0] += timedelta(seconds=241)
        settle(setup[0].batch_id, own["id"], outcome="unknown")
        setup[3][0] += timedelta(hours=24)
        estimate = settle(setup[0].batch_id, own["id"], outcome="unknown")
    result = recover(engine, setup)
    assert result["samples"][0]["late_usage_pending"] is True
    rows = {r["id"]: r for r in values(engine, m.evaluation_attempts)}
    assert rows[own["id"]] == estimate
    assert rows[other_row["id"]]["state"] == "dispatched"


def test_receipt_identity_is_checked_even_with_valid_checksum(engine, setup, monkeypatch):
    with session(engine, setup) as run:
        def fail(*args, **kw): raise RuntimeError("settlement interrupted")
        monkeypatch.setattr(run.ledger, "settle", fail)
        with pytest.raises(RuntimeError): asyncio.run(run.execute("dev-04", fake()))
    path = Path(setup[0].output) / "dev-04.json"
    data = json.loads(path.read_text())
    data["record"]["attempt_id"] = str(uuid4())
    data["sha256"] = p.digest(data["record"])
    path.write_bytes(p.canonical(data))
    with pytest.raises(ValueError, match="match ledger"): recover(engine, setup)
    assert values(engine, m.evaluation_attempts)[0]["state"] == "dispatched"
