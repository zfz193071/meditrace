"""Request-bound run API using synthetic sources and in-process Fake/Mock adapters only."""
import asyncio
from datetime import timedelta
from threading import Event
from concurrent.futures import ThreadPoolExecutor
from uuid import UUID, uuid4

import pytest
import sqlalchemy as sa

from referral_review.extraction import FakeAdapter
from referral_review.persistence import models as m
from referral_review.runs import Runs
from test_identity import auth_client, sign_in
from test_packets import workspace, create, upload, save


@pytest.fixture
def review(workspace):
    client, identity, clock, _, headers = workspace
    pid = create(workspace).json()["id"]
    did = upload(workspace, pid, "Patient: Synthetic Example")
    revision = save(workspace, pid, 0, [did]).json()["id"]
    owner = UUID(client.get("/auth/session").json()["user"]["id"])
    order = uuid4()
    with identity.engine.begin() as conn:
        conn.execute(m.orders.insert().values(id=order, owner_id=owner, environment="test", price_id="synthetic",
            amount=100, currency="usd", state="paid", created_at=clock[0], paid_at=clock[0]))
        conn.execute(m.memberships.insert().values(owner_id=owner, source_order_id=order, environment="test",
            valid_from=clock[0], valid_until=clock[0] + timedelta(days=30), granted_units=20))
    adapter = FakeAdapter({"facts": [dict(field_key="patient.name", value_raw="Synthetic Example", value_normalized=None,
        assertion_status="stated", temporal_context=None,
        sources=[dict(document_id=did, page_number=1, quote="Patient: Synthetic Example")])]})
    client.app.state.runs = Runs(identity, adapter_factory=lambda row, source: adapter)
    return dict(workspace=workspace, client=client, identity=identity, clock=clock, headers=headers,
                pid=pid, did=did, revision=revision, owner=owner, adapter=adapter, service=client.app.state.runs)


def new_run(r, *, key=None, **body):
    return r["client"].post(f"/packets/{r['pid']}/runs", headers=r["headers"] | {"Idempotency-Key": key or uuid4().hex},
        json=dict(revision_id=r["revision"], checklist_version="outpatient-referral-demo@1") | body)


def post(r, rid, action):
    return r["client"].post(f"/runs/{rid}/{action}", headers=r["headers"] | {"Idempotency-Key": uuid4().hex})


def rows(r, table):
    with r["identity"].engine.begin() as conn:
        return [dict(row) for row in conn.execute(sa.select(table)).mappings()]


def token(r):
    return r["client"].cookies.get(r["identity"].session_cookie)


def test_create_deduplicates_keys_and_active_content_get_never_dispatches(review):
    r = review
    first = new_run(r, key="run-key-001")
    assert first.status_code == 201, first.text
    rid = first.json()["id"]
    assert new_run(r, key="run-key-001").json() == first.json()
    assert new_run(r).json()["id"] == rid
    assert new_run(r, key="run-key-001", checklist_version="other").status_code == 409
    assert new_run(r, mode="real").status_code == 422
    assert new_run(r, checklist_version="other").status_code == 422
    for _ in range(3):
        result = r["client"].get(f"/runs/{rid}")
        assert result.json()["state"] == "pending" and result.json()["result"] is None
    assert r["adapter"].calls == 0
    assert rows(r, m.usage_reservations) == []


def test_success_result_graph_and_ledger_commit_once(review):
    r = review
    rid = new_run(r).json()["id"]
    response = post(r, rid, "execute")
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["state"] == "succeeded", data
    assert data["mode"] == "fake" and data["phase"] == "complete"
    assert data["model_reported"] == "fake-extraction-v1"
    assert data["result"]["facts"][0]["value_raw"] == "Synthetic Example"
    assert data["result"]["evidence"][0]["document_id"] == r["did"]
    assert len(data["result"]["findings"]) == 6
    assert rows(r, m.memberships)[0]["consumed_units"] == 1
    assert r["client"].get(f"/runs/{rid}").json() == data
    assert post(r, rid, "execute").json() == data
    assert post(r, rid, "reconcile").json() == data
    assert r["adapter"].calls == 1
    # A new requested run after a terminal outcome has independent missing-finding IDs.
    second = new_run(r).json()["id"]
    assert second != rid
    assert post(r, second, "execute").json()["state"] == "succeeded"
    assert r["adapter"].calls == 2


def test_pending_cancel_expiry_and_csrf(review):
    r = review
    rid = new_run(r).json()["id"]
    assert r["client"].post(f"/runs/{rid}/execute").status_code == 403
    assert post(r, rid, "cancel").json()["state"] == "cancelled"
    assert post(r, rid, "execute").json()["state"] == "cancelled"
    rid = new_run(r).json()["id"]
    r["clock"][0] += timedelta(minutes=31)
    assert r["client"].get(f"/runs/{rid}").json()["state"] == "pending"
    assert post(r, rid, "reconcile").json()["error_code"] == "PENDING_EXPIRED"
    assert r["adapter"].calls == 0


def test_permission_failures_leave_no_reservation_or_dispatch(review):
    r = review
    rid = new_run(r).json()["id"]
    with r["identity"].engine.begin() as conn:
        conn.execute(m.memberships.update().values(revoked_at=r["clock"][0]))
    assert post(r, rid, "execute").status_code == 403
    assert rows(r, m.usage_reservations) == []
    assert r["adapter"].calls == 0
    r["workspace"][3].subject = 999
    sign_in(r["client"])
    headers = {"Origin": r["identity"].settings.site_origin, "X-CSRF-Token": r["client"].get("/auth/session").json()["csrf_token"]}
    assert r["client"].get(f"/runs/{rid}").status_code == 404
    for action in ("execute", "cancel", "reconcile"):
        assert r["client"].post(f"/runs/{rid}/{action}", headers=headers | {"Idempotency-Key": uuid4().hex}).status_code == 404


@pytest.mark.parametrize("stage", ["before_reserve", "after_reserve"])
def test_claim_fault_rolls_back_reservation_and_state(review, stage):
    r = review
    rid = UUID(new_run(r).json()["id"])
    def fault(current):
        if current == stage: raise RuntimeError("simulated transaction failure")
    r["service"].fault = fault
    r["service"]._attempt(token(r), rid)
    with pytest.raises(RuntimeError): r["service"]._claim(token(r), rid)
    assert rows(r, m.runs)[0]["state"] == "pending"
    assert rows(r, m.usage_reservations) == []
    assert rows(r, m.memberships)[0]["reserved_units"] == 0
    assert r["adapter"].calls == 0


@pytest.mark.parametrize("dispatched", [False, True])
def test_crash_after_claim_or_marker_reconciles_without_retry(review, dispatched):
    r = review
    rid = UUID(new_run(r).json()["id"])
    r["service"]._attempt(token(r), rid)
    assert r["service"]._claim(token(r), rid)
    if dispatched: r["service"]._dispatch(token(r), rid)
    assert post(r, rid, "execute").status_code == 202
    assert post(r, rid, "cancel").status_code == 409
    r["clock"][0] += timedelta(seconds=241)
    assert r["client"].get(f"/runs/{rid}").json()["state"] == "running"
    result = post(r, rid, "reconcile").json()
    assert result["state"] == ("outcome_unknown" if dispatched else "failed")
    assert post(r, rid, "execute").json() == result
    assert r["adapter"].calls == 0
    assert rows(r, m.usage_reservations)[0]["state"] == ("retained_unknown" if dispatched else "released")
    if dispatched:
        r["clock"][0] += timedelta(hours=24)
        assert post(r, rid, "reconcile").json()["state"] == "outcome_unknown"
        assert rows(r, m.memberships)[0]["reserved_units"] == 0


@pytest.mark.parametrize("stage", ["after_response", "before_result_commit"])
def test_response_or_commit_failure_never_exposes_partial_success(review, stage):
    r = review
    rid = new_run(r).json()["id"]
    def fault(current):
        if current == stage: raise RuntimeError("sensitive-content-must-not-leak")
    r["service"].fault = fault
    response = post(r, rid, "execute")
    assert response.status_code == 200, response.text
    assert response.json()["state"] == "outcome_unknown"
    assert response.json()["result"] is None
    assert "sensitive" not in response.text
    assert rows(r, m.facts) == rows(r, m.findings) == rows(r, m.evidence) == []
    assert rows(r, m.memberships)[0]["consumed_units"] == 0
    post(r, rid, "execute")
    assert r["adapter"].calls == 1


@pytest.mark.parametrize("scenario,state", [("invalid_json", "failed"), ("false_quote", "failed"),
    ("truncated", "failed"), ("timeout", "outcome_unknown"), ("usage_missing", "succeeded")])
def test_adapter_failures_and_missing_usage(review, scenario, state):
    r = review
    r["adapter"].scenario = scenario
    rid = new_run(r).json()["id"]
    response = post(r, rid, "execute")
    assert response.status_code == 200, response.text
    assert response.json()["state"] == state, response.text
    assert (response.json()["result"] is not None) == (state == "succeeded")
    post(r, rid, "execute")
    assert r["adapter"].calls == 1


def test_revisions_stale_before_call_and_change_during_call(review):
    r = review
    rid = new_run(r).json()["id"]
    did2 = upload(r["workspace"], r["pid"], "Synthetic second document")
    save(r["workspace"], r["pid"], 1, [did2])
    assert post(r, rid, "execute").status_code == 409
    assert r["adapter"].calls == 0
    assert r["client"].get(f"/runs/{rid}").json()["stale"] is True


def test_source_deleted_during_call_discards_result_but_settles(review):
    r = review
    rid = new_run(r).json()["id"]
    def fault(stage):
        if stage == "after_response":
            with r["identity"].engine.begin() as conn:
                conn.execute(m.packets.update().values(deleted_at=r["clock"][0]))
    r["service"].fault = fault
    assert post(r, rid, "execute").status_code == 404
    assert rows(r, m.runs)[0]["error_code"] == "SOURCE_DELETED"
    assert rows(r, m.facts) == []
    assert rows(r, m.usage_reservations)[0]["state"] == "released"
    assert rows(r, m.memberships)[0]["consumed_units"] == 0


def test_two_service_instances_dispatch_only_once(review):
    r = review
    rid = UUID(new_run(r).json()["id"])
    started, release = Event(), Event()
    original = r["adapter"].complete
    async def complete(request):
        started.set()
        await asyncio.to_thread(release.wait, 5)
        return await original(request)
    r["adapter"].complete = complete
    other = Runs(r["identity"], adapter_factory=lambda row, source: r["adapter"])
    with ThreadPoolExecutor(max_workers=1) as pool:
        first = pool.submit(lambda: asyncio.run(r["service"].execute(token(r), rid)))
        assert started.wait(5)
        try:
            second = asyncio.run(other.execute(token(r), rid))
            assert second.state == "running"
            assert other.get(token(r), rid).state == "running"
        finally:
            release.set()
        assert first.result(timeout=10).state == "succeeded"
    assert r["adapter"].calls == 1


def test_application_timeout_is_unknown_and_never_retried(review, monkeypatch):
    from referral_review.runs import service
    r = review
    rid = new_run(r).json()["id"]
    calls = []
    async def slow(request):
        calls.append(request)
        await asyncio.sleep(3)
    r["adapter"].complete = slow
    monkeypatch.setattr(service, "APPLICATION_TIMEOUT", 0.5)
    response = post(r, rid, "execute")
    assert response.status_code == 200, response.text
    assert response.json()["state"] == "outcome_unknown"
    post(r, rid, "execute")
    assert len(calls) == 1


def test_membership_revoked_between_claim_and_dispatch_blocks_call(review):
    r = review
    rid = new_run(r).json()["id"]
    def revoke(stage):
        if stage == "after_claim_commit":
            with r["identity"].engine.begin() as conn:
                conn.execute(m.memberships.update().values(revoked_at=r["clock"][0]))
    r["service"].fault = revoke
    assert post(r, rid, "execute").status_code == 403
    assert r["adapter"].calls == 0
    assert rows(r, m.runs)[0]["provider_dispatched_at"] is None
    assert rows(r, m.usage_reservations)[0]["state"] == "released"


def test_source_revised_during_call_preserves_old_result_as_stale(review):
    r = review
    rid = new_run(r).json()["id"]
    def revise(stage):
        if stage == "after_response":
            from referral_review.persistence.repository import save_revision
            with r["identity"].engine.begin() as conn:
                save_revision(conn, owner_id=r["owner"], packet_id=UUID(r["pid"]), expected_revision=1,
                    document_ids=[], now=r["clock"][0])
    r["service"].fault = revise
    response = post(r, rid, "execute")
    assert response.status_code == 200, response.text
    assert response.json()["state"] == "succeeded" and response.json()["stale"] is True
    assert response.json()["result"]["revision_id"] == r["revision"]


def test_real_http_mock_uses_authorized_reservation_and_settles(review):
    import httpx
    import json
    from referral_review.extraction import DeepSeekAdapter
    r = review
    settings = r["identity"].settings.model_copy(update=dict(mode="invited_real", real_ai_enabled=True,
        real_ai_user_ids=(r["owner"],), model_id="configured-model", price_version="test-prices",
        input_microusd_per_million=1000, output_microusd_per_million=2000,
        daily_budget_microusd=1000, monthly_budget_microusd=2000))
    from pydantic import SecretStr
    settings = settings.model_copy(update={"deepseek_key": SecretStr("synthetic-test-key")})
    r["identity"].settings = settings
    calls = []
    def respond(request):
        # Network seam observes a COMMITTED marker and reservation before accepting the request.
        assert rows(r, m.runs)[0]["provider_dispatched_at"] is not None
        assert rows(r, m.usage_reservations)[0]["state"] == "reserved"
        calls.append(request)
        return httpx.Response(200, json=dict(id="synthetic-request", model="reported-model",
            usage=dict(prompt_tokens=500, completion_tokens=500, total_tokens=1000),
            choices=[dict(finish_reason="stop", message=dict(role="assistant", content=json.dumps(r["adapter"].output)))]))
    r["client"].app.state.runs = Runs(r["identity"], adapter_factory=lambda row, source:
        DeepSeekAdapter(settings.deepseek_key, transport=httpx.MockTransport(respond)))
    rid = new_run(r).json()["id"]
    result = post(r, rid, "execute")
    assert result.status_code == 200, result.text
    assert result.json()["mode"] == "real" and result.json()["state"] == "succeeded"
    assert rows(r, m.usage_reservations)[0]["actual_microusd"] == 2
    assert result.json()["model_reported"] == "reported-model"
    assert post(r, rid, "execute").json() == result.json()
    assert len(calls) == 1


def test_late_response_after_lease_recovery_commits_without_redispatch(review):
    r = review
    rid = UUID(new_run(r).json()["id"])
    started, release = Event(), Event()
    original = r["adapter"].complete
    async def complete(request):
        started.set()
        await asyncio.to_thread(release.wait, 5)
        return await original(request)
    r["adapter"].complete = complete
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(lambda: asyncio.run(r["service"].execute(token(r), rid)))
        assert started.wait(5)
        try:
            r["clock"][0] += timedelta(seconds=241)
            assert r["service"].reconcile(token(r), rid).state == "outcome_unknown"
            assert asyncio.run(r["service"].execute(token(r), rid)).state == "outcome_unknown"
        finally:
            release.set()
        assert future.result(timeout=10).state == "succeeded"
    assert r["adapter"].calls == 1
    assert rows(r, m.memberships)[0]["consumed_units"] == 1


def test_default_sandbox_is_explicit_empty_simulation_not_inferred_facts(review):
    r = review
    r["client"].app.state.runs = Runs(r["identity"])
    rid = new_run(r).json()["id"]
    response = post(r, rid, "execute")
    assert response.json()["state"] == "succeeded"
    assert response.json()["mode"] == "fake"
    assert response.json()["result"]["facts"] == []
    assert len(response.json()["result"]["findings"]) == 7


def test_preflight_blocks_oversized_complete_model_input_without_reserving(review):
    r = review
    did = upload(r["workspace"], r["pid"], "🧪" * 4000)
    r["revision"] = save(r["workspace"], r["pid"], 1, [did]).json()["id"]
    response = new_run(r)
    assert response.status_code == 413, response.text
    assert rows(r, m.runs) == [] and rows(r, m.usage_reservations) == []
    assert r["adapter"].calls == 0


def test_operation_keys_bind_action_to_one_run(review):
    r = review
    first = new_run(r).json()["id"]
    headers = r["headers"] | {"Idempotency-Key": "same-execute-key"}
    assert r["client"].post(f"/runs/{first}/execute", headers=headers).json()["state"] == "succeeded"
    assert r["client"].post(f"/runs/{first}/execute", headers=headers).json()["state"] == "succeeded"
    second = new_run(r).json()["id"]
    assert r["client"].post(f"/runs/{second}/execute", headers=headers).status_code == 409
    assert r["adapter"].calls == 1


def test_deadline_during_commit_rolls_back_thread_work(review, monkeypatch):
    import time
    from referral_review.runs import service
    r = review
    rid = new_run(r).json()["id"]
    monkeypatch.setattr(service, "APPLICATION_TIMEOUT", 0.5)
    def delay(stage):
        if stage == "before_result_commit": time.sleep(0.7)
    r["service"].fault = delay
    response = post(r, rid, "execute")
    assert response.status_code == 200, response.text
    assert response.json()["state"] == "outcome_unknown"
    assert rows(r, m.facts) == []
    assert rows(r, m.memberships)[0]["consumed_units"] == 0
    assert r["adapter"].calls == 1
