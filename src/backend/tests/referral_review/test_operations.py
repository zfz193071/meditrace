"""MT-19 drills: real state machines, synthetic data, no model/payment network."""
from datetime import timedelta
import json
from uuid import UUID, uuid4

import pytest
import sqlalchemy as sa
from pydantic import SecretStr

from referral_review.operations import readiness
from referral_review.persistence import models as m
from referral_review.persistence.migrations import HEAD
from test_identity import auth_client, sign_in
from test_packets import workspace
from test_runs import review, new_run, post, rows, token
from test_billing import billing, create as checkout, rows as billing_rows


def operator(identity):
    identity.settings = identity.settings.model_copy(update={"maintenance_token": SecretStr("operator" * 8)})
    return {"Authorization": "Bearer " + "operator" * 8}


def database_snapshot(engine):
    with engine.connect() as conn:
        return {table.name: [dict(row) for row in conn.execute(sa.select(table)).mappings()]
                for table in m.metadata.sorted_tables}


def test_readiness_and_operator_queries_are_read_only(review):
    r = review
    rid = new_run(r).json()["id"]
    headers = operator(r["identity"])
    before = database_snapshot(r["identity"].engine)
    sql = []
    def capture(conn, cursor, statement, parameters, context, many):
        sql.append(statement)
    sa.event.listen(r["identity"].engine, "before_cursor_execute", capture)
    try:
        for _ in range(2):
            response = r["client"].get("/readiness")
            assert response.status_code == 200, response.text
            assert response.json()["schema_version"] == HEAD
            assert set(response.json()["checks"].values()) == {"ready"}
            response = r["client"].get("/internal/operations", params={"run_id": rid}, headers=headers)
            assert response.status_code == 200, response.text
            assert response.json()["runs"][0]["state"] == "pending"
            assert len(response.json()["budgets"]) == 2
    finally:
        sa.event.remove(r["identity"].engine, "before_cursor_execute", capture)
    assert not any(query.lstrip().split()[0].upper() in {"INSERT", "UPDATE", "DELETE", "CREATE", "ALTER", "DROP"} for query in sql)
    assert before == database_snapshot(r["identity"].engine)
    assert r["adapter"].calls == 0


@pytest.mark.parametrize("failure", ["database", "version", "table", "checklist"])
def test_readiness_faults_fail_closed_without_secrets(auth_client, monkeypatch, caplog, failure):
    client, identity, _, _ = auth_client
    sentinel = "patient-credential-sentinel"
    if failure == "database":
        def fail():
            raise RuntimeError(sentinel)
        monkeypatch.setattr(identity.engine, "connect", fail)
    elif failure == "checklist":
        monkeypatch.setattr(readiness, "checklist_ready", lambda: False)
    else:
        with identity.engine.begin() as conn:
            if failure == "version":
                conn.execute(sa.text("UPDATE rr_alembic_version SET version_num=:value"), {"value": sentinel})
            else:
                conn.exec_driver_sql("DROP TABLE rr_usage_adjustments")
    response = client.get("/readiness")
    assert response.status_code == 503 and response.json()["status"] == "not_ready"
    assert sentinel not in response.text + caplog.text


def test_readiness_without_identity_can_inspect_existing_database(auth_client, tmp_path):
    _, identity, _, _ = auth_client
    settings = identity.settings.model_copy(update={"database_url": SecretStr(str(identity.engine.url))})
    assert readiness.probe(settings).status == "ready"
    missing = tmp_path / "must-not-create.db"
    settings = settings.model_copy(update={"database_url": SecretStr("sqlite:///" + str(missing))})
    assert readiness.probe(settings).status == "not_ready" and not missing.exists()


@pytest.mark.parametrize("method", ["GET", "POST"])
def test_operator_requires_bearer_not_session_or_query(auth_client, method):
    client, identity, _, _ = auth_client
    sign_in(client)
    good = operator(identity)
    before = database_snapshot(identity.engine)
    for headers in ({}, {"Authorization": "Bearer wrong"}, {"X-Maintenance-Token": "operator" * 8},
                    [("Authorization", good["Authorization"]), ("Authorization", good["Authorization"])]):
        response = client.request(method, "/internal/operations", headers=headers,
            json={"action": "reconcile", "apply": True, "run_id": str(uuid4())} if method == "POST" else None)
        assert response.status_code == 403
    assert client.get("/internal/operations", params={"token": "operator" * 8}).status_code == 403
    assert client.get("/internal/operations", params={"token": "wrong"}, headers=good).status_code == 422
    assert before == database_snapshot(identity.engine)


def test_run_request_log_and_ledger_correlation_and_redaction(review, caplog):
    r = review
    created = new_run(r)
    rid = created.json()["id"]
    response = post(r, rid, "execute")
    assert response.status_code == 200
    request_id = response.headers["X-Request-ID"]
    headers = operator(r["identity"])
    status = r["client"].get("/internal/operations", params={"request_id": request_id}, headers=headers).json()
    run = status["runs"][0]
    assert run["run_id"] == rid and run["state"] == "succeeded"
    assert run["reservation_id"] == str(rows(r, m.usage_reservations)[0]["id"])
    assert {a["action"] for a in status["audit"]} >= {"run:execute", "run:reserved", "run:dispatched", "run:complete"}
    logs = [json.loads(record.message) for record in caplog.records if record.name == "meditrace.referral.telemetry"]
    complete = next(row for row in logs if row.get("run_id") == rid and row["phase"] == "complete")
    assert complete["request_id"] == request_id and complete["duration_ms"] >= 0
    assert complete["estimated_microusd"] == complete["actual_microusd"] == 0
    sentinel = "secret-raw-document-sentinel"
    with r["identity"].engine.begin() as conn:
        conn.execute(m.runs.update().where(m.runs.c.id == UUID(rid)).values(
            model_reported=sentinel, model_requested=sentinel, provider_request_id=sentinel, error_code=sentinel,
            usage={"prompt_tokens": sentinel, "completion_tokens": 1, "total_tokens": sentinel, "source": sentinel}))
    from referral_review.operations.telemetry import observe
    observe(r["identity"].engine, UUID(rid), "complete")
    response = r["client"].get("/internal/operations", params={"run_id": rid}, headers=headers)
    assert response.status_code == 200 and response.json()["runs"][0]["error_code"] == "UNCLASSIFIED"
    assert sentinel not in response.text + caplog.text
    assert "Synthetic Example" not in "".join(record.message for record in caplog.records if record.name.startswith("meditrace.referral"))


@pytest.mark.parametrize("dispatched", [False, True])
@pytest.mark.parametrize("real", [False, True])
def test_operator_recovery_never_redispatches_and_preserves_unknown(review, dispatched, real):
    r = review
    if real:
        from referral_review.runs import Runs
        r["identity"].settings = r["identity"].settings.model_copy(update=dict(mode="invited_real", real_ai_enabled=True,
            real_ai_user_ids=(r["owner"],), model_id="configured-model", price_version="test-prices",
            deepseek_key=SecretStr("synthetic-test-key"), input_microusd_per_million=1000,
            output_microusd_per_million=2000, daily_budget_microusd=1000, monthly_budget_microusd=2000))
        r["service"] = r["client"].app.state.runs = Runs(r["identity"])
    rid = UUID(new_run(r).json()["id"])
    r["service"]._claim(token(r), rid)
    if dispatched:
        r["service"]._dispatch(token(r), rid)
    r["clock"][0] += timedelta(minutes=5)
    headers = operator(r["identity"])
    body = dict(action="reconcile", run_id=str(rid))
    client = r["client"]
    assert client.post("/internal/operations", headers=headers, json=body).status_code == 422
    for _ in range(2):
        response = client.post("/internal/operations", headers=headers, json=body | {"apply": True})
        assert response.status_code == 200, response.text
        result = response.json()["runs"][0]
        assert result["state"] == ("outcome_unknown" if dispatched else "failed")
        assert result["usage_state"] == ("retained_unknown" if dispatched else "released")
    if dispatched:
        r["clock"][0] += timedelta(hours=25)
        response = client.post("/internal/operations", headers=headers, json=body | {"apply": True})
        assert response.json()["runs"][0]["usage_state"] == ("estimated_spent" if real else "released")
        assert response.json()["runs"][0]["state"] == "outcome_unknown"
        if real:
            result = response.json()["runs"][0]
            assert result["actual_microusd"] is None
            assert result["booked_microusd"] == result["estimated_microusd"] > 0
            assert all(bucket["reserved_microusd"] == 0 and bucket["spent_microusd"] == result["booked_microusd"]
                       for bucket in rows(r, m.budget_buckets))
            from referral_review.usage import Usage
            Usage(r["identity"]).adjust(r["owner"], rid, adjustment_key="synthetic-provider-proof",
                usage=dict(prompt_tokens=500, completion_tokens=500, total_tokens=1000))
            result = client.get("/internal/operations", headers=headers, params={"run_id": str(rid)}).json()["runs"][0]
            assert result["actual_microusd"] == result["booked_microusd"] == 2
            assert result["adjustment_count"] == 1
    assert r["adapter"].calls == 0


def test_cleanup_retry_selected_job_requires_exhausted_ack_and_keeps_live_lease(review):
    r = review
    headers = operator(r["identity"])
    job_id = uuid4()
    with r["identity"].engine.begin() as conn:
        conn.execute(m.cleanup_jobs.insert().values(id=job_id, kind="packet", entity_id=uuid4(),
            state="failed", attempt_count=10, next_attempt_at=r["clock"][0]))
    body = dict(action="retry_cleanup", job_id=str(job_id), apply=True)
    client = r["client"]
    assert client.post("/internal/operations", headers=headers, json=body).status_code == 409
    response = client.post("/internal/operations", headers=headers, json=body | {"retry_exhausted": True})
    assert response.status_code == 200
    assert not any(row["id"] == job_id for row in rows(r, m.cleanup_jobs))
    with r["identity"].engine.begin() as conn:
        conn.execute(m.cleanup_jobs.insert().values(id=job_id, kind="packet", entity_id=uuid4(),
            state="running", attempt_count=1, next_attempt_at=r["clock"][0] + timedelta(minutes=5)))
    before = database_snapshot(r["identity"].engine)
    assert client.post("/internal/operations", headers=headers, json=body).status_code == 409
    assert before == database_snapshot(r["identity"].engine)


def test_operator_retries_recorded_payment_idempotently(billing):
    b = billing
    assert checkout(b).status_code == 200
    sid = billing_rows(b, m.orders)[0]["checkout_session_id"]
    b[2].paid(sid)
    with b[1].engine.begin() as conn:
        conn.execute(m.billing_events.insert().values(stripe_event_id="evt_retry1", event_type="checkout.session.completed",
            object_id=sid, state="failed", received_at=b[3][0]))
    headers = operator(b[1].identity)
    for _ in range(2):
        response = b[0].post("/internal/operations", headers=headers,
            json=dict(action="retry_payment", event_id="evt_retry1", apply=True))
        assert response.status_code == 200, response.text
    assert len(billing_rows(b, m.memberships)) == 1
    assert billing_rows(b, m.billing_events)[0]["state"] == "processed"


def test_operator_retries_real_local_object_after_storage_failure(review, monkeypatch):
    from referral_review.lifecycle import Lifecycle
    from referral_review.documents.storage import StorageUnavailable
    r = review
    documents = r["client"].app.state.documents
    original = documents.store.delete
    def fail(key):
        raise StorageUnavailable()
    monkeypatch.setattr(documents.store, "delete", fail)
    assert r["client"].delete(f"/packets/{r['pid']}", headers=r["headers"] |
        {"Idempotency-Key": uuid4().hex}).status_code == 202
    lifecycle = Lifecycle(r["identity"], documents)
    for _ in range(2):
        lifecycle.maintain()
        r["clock"][0] += timedelta(seconds=6)
    job = next(row for row in rows(r, m.cleanup_jobs) if row["kind"] == "object")
    assert job["state"] == "failed" and list(documents.store.directory.iterdir())
    assert rows(r, m.storage_reservations)[0]["state"] == "cleanup_pending"
    monkeypatch.setattr(documents.store, "delete", original)
    response = r["client"].post("/internal/operations", headers=operator(r["identity"]),
        json=dict(action="retry_cleanup", job_id=str(job["id"]), apply=True))
    assert response.status_code == 200, response.text
    assert list(documents.store.directory.iterdir()) == []
    assert rows(r, m.storage_reservations)[0]["state"] == "released"
    assert all(row["reserved_bytes"] == row["stored_bytes"] == 0 for row in rows(r, m.storage_buckets))


def test_alerts_report_financial_and_persistent_failures_without_identifiers(auth_client):
    client, identity, clock, _ = auth_client
    headers = operator(identity)
    with identity.engine.begin() as conn:
        conn.execute(m.usage_controls.insert().values(key="real_ai", halted=True, reason="secret-sentinel"))
        conn.execute(m.budget_buckets.insert().values(bucket_key="day:2026-10-20", limit_microusd=1, spent_microusd=2))
        conn.execute(m.rate_limit_buckets.insert().values(scope="secret-sentinel", action="failure:86400", count=10, window_start=clock[0]))
        conn.execute(m.billing_events.insert().values(stripe_event_id="evt_secret", object_id="secret-sentinel",
            event_type="secret-sentinel", state="failed", received_at=clock[0]))
    response = client.get("/internal/operations", headers=headers)
    assert response.status_code == 200
    for key in ("financial_halt", "budget_overrun", "persistent_failures", "payment_failures"):
        assert response.json()["alerts"][key] == 1
    assert "secret-sentinel" not in response.text
