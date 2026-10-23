"""MT-18 deletion/expiry/fault tests using only synthetic data and local storage."""
from datetime import timedelta
from uuid import UUID, uuid4

import pytest
import sqlalchemy as sa
from pydantic import SecretStr

from referral_review.lifecycle import Lifecycle
from referral_review.documents.storage import StorageUnavailable
from referral_review.persistence import models as m
from test_identity import auth_client, sign_in
from test_packets import workspace, create, upload, save
from test_reviews import review, resolve, draft, confirm
from test_runs import review as running_review, new_run, post, rows, token


def lifecycle(r):
    return Lifecycle(r["identity"], r["client"].app.state.documents)


def remove(r):
    result = r["client"].delete(f"/packets/{r['pid']}", headers=r["headers"] | {"Idempotency-Key": uuid4().hex})
    assert result.status_code == 202, result.text


def drain(r, limit=200):
    for _ in range(8):
        result = lifecycle(r).maintain(limit)
        if result["backlog"] == 0:
            return result
        r["clock"][0] += timedelta(seconds=6)
    pytest.fail(f"Cleanup did not drain: {result}")


def test_full_history_purge_and_all_reads_blocked_immediately(review):
    r = review
    assert resolve(r, corrected_value="Synthetic correction", linked_evidence_ids=[r["eid"]]).status_code == 201
    assert draft(r, 1, mode="assisted", run_id=r["rid"]).status_code == 200
    sid = confirm(r, 2).json()["id"]
    second = upload(r["workspace"], r["pid"], "Synthetic second version")
    assert save(r["workspace"], r["pid"], 1, [second]).status_code == 201
    other = create(r["workspace"]).json()["id"]
    other_doc = upload(r["workspace"], other, "Unrelated synthetic source")
    remove(r)
    paths = [f"/packets/{r['pid']}", f"/packets/{r['pid']}/revisions/1",
        f"/packets/{r['pid']}/documents/{r['did']}", f"/packets/{r['pid']}/documents/{r['did']}/pages/1",
        f"/packets/{r['pid']}/documents/{r['did']}/original", f"/runs/{r['rid']}", f"/runs/{r['rid']}/review",
        f"/packets/{r['pid']}/review-history", f"/packets/{r['pid']}/handoff-draft",
        f"/packets/{r['pid']}/snapshots/{sid}", f"/packets/{r['pid']}/snapshots/{sid}/handoff",
        f"/packets/{r['pid']}/snapshots/{sid}/export?format=txt"]
    for path in paths:
        response = r["client"].get(path)
        assert response.status_code == 404, (path, response.text)
        assert response.headers["cache-control"] == "private, no-store"
    assert drain(r)["backlog"] == 0
    for table in (m.document_pages, m.documents):
        assert len(rows(r, table)) == 1  # Other packet survives.
    for table in (m.revisions, m.revision_documents, m.runs, m.evidence, m.facts, m.fact_evidence,
                  m.findings, m.finding_documents, m.finding_evidence, m.finding_facts,
                  m.resolutions, m.resolution_evidence, m.handoff_drafts, m.review_snapshots, m.review_events):
        assert rows(r, table) == [], table.name
    assert r["client"].get(f"/packets/{other}/documents/{other_doc}/original").status_code == 200
    store = r["client"].app.state.documents.store
    assert len(list(store.directory.iterdir())) == 1


def test_expiry_and_orphans_do_not_need_user_visits(review):
    r = review
    orphan = upload(r["workspace"], r["pid"], "Synthetic unused upload")
    r["clock"][0] += timedelta(hours=24)
    drain(r)
    assert r["client"].get(f"/packets/{r['pid']}/documents/{orphan}").status_code == 404
    assert r["client"].get(f"/packets/{r['pid']}/documents/{r['did']}/original").status_code == 200
    r["clock"][0] += timedelta(days=6)
    drain(r)
    assert rows(r, m.packets) == [] and rows(r, m.documents) == []


def test_blob_failure_retains_quota_and_retry_cap_alerts(review, monkeypatch):
    r = review
    store = r["client"].app.state.documents.store
    original = store.delete
    monkeypatch.setattr(store, "delete", lambda key: (_ for _ in ()).throw(StorageUnavailable()))
    remove(r)
    for _ in range(11):
        result = lifecycle(r).maintain()
        r["clock"][0] += timedelta(hours=2)
    assert result["exhausted"] == 1 and result["backlog"] > 0
    assert rows(r, m.document_pages) == [] and rows(r, m.review_snapshots) == []
    assert rows(r, m.storage_reservations)[0]["state"] == "cleanup_pending"
    assert all(b["reserved_bytes"] > 0 for b in rows(r, m.storage_buckets))
    monkeypatch.setattr(store, "delete", original)
    assert r["client"].app.state.documents.reconcile(retry_exhausted=True)["cleaned"] == 1
    drain(r)
    assert rows(r, m.documents) == []
    assert all(b["reserved_bytes"] == b["stored_bytes"] == 0 for b in rows(r, m.storage_buckets))


def test_database_failure_rolls_back_and_keeps_durable_job(review, monkeypatch):
    r = review
    remove(r)
    service = lifecycle(r)
    original = service._scrub
    def fail(conn, packet):
        original(conn, packet)
        raise RuntimeError("private-sentinel-must-not-be-logged")
    monkeypatch.setattr(service, "_scrub", fail)
    service.maintain()
    job = next(j for j in rows(r, m.cleanup_jobs) if j["kind"] == "packet")
    assert job["state"] == "failed" and job["last_error_code"] == "PURGE_FAILED"
    assert len(rows(r, m.facts)) == 1  # Whole scrub rolled back, access remains blocked.
    r["clock"][0] += timedelta(minutes=6)
    drain(r)
    assert rows(r, m.packets) == []


def test_delete_succeeded_but_database_commit_failed_keeps_quota_until_retry(review, monkeypatch):
    r = review
    remove(r)
    lifecycle(r).maintain()  # Queue immutable ready source for object deletion.
    documents = r["client"].app.state.documents
    original = documents._buckets
    calls = 0
    def fail_commit(conn, owner):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("synthetic database outage after successful object deletion")
        return original(conn, owner)
    monkeypatch.setattr(documents, "_buckets", fail_commit)
    with pytest.raises(RuntimeError):
        documents.cleanup(UUID(r["did"]))
    assert list(documents.store.directory.iterdir()) == []
    assert all(row["reserved_bytes"] > 0 for row in rows(r, m.storage_buckets))
    monkeypatch.setattr(documents, "_buckets", original)
    r["clock"][0] += timedelta(minutes=11)
    drain(r)
    assert all(row["reserved_bytes"] == row["stored_bytes"] == 0 for row in rows(r, m.storage_buckets))


def test_delete_while_execute_in_flight_discards_result_and_settles(running_review):
    r = running_review
    rid = new_run(r).json()["id"]
    def deleted(stage):
        if stage == "after_response":
            lifecycle(r).packets.delete(token(r), UUID(r["pid"]), uuid4().hex)
            lifecycle(r).maintain()
            assert rows(r, m.document_pages) == []
    r["service"].fault = deleted
    assert post(r, rid, "execute").status_code == 404
    assert rows(r, m.facts) == []
    assert rows(r, m.usage_reservations)[0]["state"] == "released"
    drain(r)
    assert rows(r, m.runs) == []
    assert rows(r, m.usage_reservations)[0]["run_id"] is None
    assert r["adapter"].calls == 1


def test_deleted_real_run_still_records_provider_cost(running_review):
    import httpx
    import json
    from referral_review.extraction import DeepSeekAdapter
    from referral_review.runs import Runs
    r = running_review
    settings = r["identity"].settings.model_copy(update=dict(mode="invited_real", real_ai_enabled=True,
        real_ai_user_ids=(r["owner"],), model_id="configured-model", price_version="test-prices",
        deepseek_key=SecretStr("synthetic-test-key"), input_microusd_per_million=1000,
        output_microusd_per_million=2000, daily_budget_microusd=1000, monthly_budget_microusd=2000))
    r["identity"].settings = settings
    def respond(request):
        lifecycle(r).packets.delete(token(r), UUID(r["pid"]), uuid4().hex)
        return httpx.Response(200, json=dict(id="synthetic-request", model="reported-model",
            usage=dict(prompt_tokens=500, completion_tokens=500, total_tokens=1000),
            choices=[dict(finish_reason="stop", message=dict(role="assistant", content=json.dumps(r["adapter"].output)))]))
    r["client"].app.state.runs = Runs(r["identity"], adapter_factory=lambda row, source:
        DeepSeekAdapter(settings.deepseek_key, transport=httpx.MockTransport(respond)))
    rid = new_run(r).json()["id"]
    assert post(r, rid, "execute").status_code == 404
    assert rows(r, m.facts) == []
    drain(r)
    reservation = rows(r, m.usage_reservations)[0]
    assert reservation["actual_microusd"] == 2 and reservation["state"] == "settled"
    assert reservation["owner_id"] is None and reservation["run_id"] is None
    assert all(b["spent_microusd"] == 2 and b["reserved_microusd"] == 0 for b in rows(r, m.budget_buckets))


def test_abandoned_run_recovery_retains_then_settles_unknown(running_review):
    r = running_review
    rid = UUID(new_run(r).json()["id"])
    r["service"]._claim(token(r), rid)
    r["service"]._dispatch(token(r), rid)
    remove(r)
    r["clock"][0] += timedelta(minutes=5)
    lifecycle(r).maintain()
    assert rows(r, m.usage_reservations)[0]["state"] == "retained_unknown"
    assert rows(r, m.document_pages) == []
    r["clock"][0] += timedelta(hours=24)
    drain(r)
    assert rows(r, m.runs) == [] and rows(r, m.packets) == []
    assert rows(r, m.usage_reservations)[0]["state"] == "released"
    assert r["adapter"].calls == 0


def test_delete_during_export_recheck_rejects_bytes(review, monkeypatch):
    from referral_review.handoff import service as handoff_service
    r = review
    assert resolve(r).status_code == 201
    sid = confirm(r, 1).json()["id"]
    original = handoff_service.pdf.bounded
    def deleted(data):
        remove(r)
        drain(r)
        return original(data)
    monkeypatch.setattr(handoff_service.pdf, "bounded", deleted)
    result = r["client"].get(f"/packets/{r['pid']}/snapshots/{sid}/export?format=txt")
    assert result.status_code == 404 and "Synthetic Example" not in result.text


def test_account_confirmation_revokes_all_sessions_and_anonymizes_ledger(running_review):
    r = running_review
    rid = new_run(r).json()["id"]
    assert post(r, rid, "execute").status_code == 200
    old_token = token(r)
    sign_in(r["client"])
    headers = r["headers"] | {"X-CSRF-Token": r["client"].get("/auth/session").json()["csrf_token"], "Idempotency-Key": uuid4().hex}
    assert r["client"].request("DELETE", "/account", json={"confirmation": "DELETE"}).status_code == 403
    assert r["client"].request("DELETE", "/account", headers=headers, json={"confirmation": "yes"}).status_code == 422
    response = r["client"].request("DELETE", "/account", headers=headers, json={"confirmation": "DELETE"})
    assert response.status_code == 202 and response.json()["state"] == "cleanup_pending"
    assert r["identity"].session(old_token).user is None
    assert r["client"].get("/auth/session").json()["user"] is None
    drain(r)
    assert rows(r, m.users) == rows(r, m.sessions) == rows(r, m.packets) == []
    assert rows(r, m.orders)[0]["owner_id"] is None
    assert rows(r, m.memberships)[0]["owner_id"] is None
    assert rows(r, m.usage_reservations)[0]["owner_id"] is None
    sign_in(r["client"])
    assert r["client"].get("/auth/session").json()["user"]["id"] != str(r["owner"])
    assert r["client"].get("/membership").json()["remaining"] == 0


def test_maintenance_auth_without_billing_and_bounded_cursor(review):
    r = review
    r["identity"].settings = r["identity"].settings.model_copy(update={"maintenance_token": SecretStr("operator-only-token")})
    client = r["client"]
    assert client.post("/internal/maintenance").status_code == 403
    assert client.post("/internal/maintenance", headers=r["headers"]).status_code == 403
    assert client.post("/internal/maintenance", headers={"Authorization": "Bearer wrong"}).status_code == 403
    remove(r)
    response = client.post("/internal/maintenance", json={"limit": 1}, headers={"Authorization": "Bearer operator-only-token"})
    assert response.status_code == 200, response.text
    assert response.json()["processed"] <= 1 and response.json()["cursor"] == "continue"
    assert "object_key" not in response.text and str(r["owner"]) not in response.text
    drain(r, limit=2)


def test_retention_removes_old_audit_and_payment_identifiers(running_review):
    r = running_review
    with r["identity"].engine.begin() as conn:
        conn.execute(m.audit_events.insert().values(actor_id=r["owner"], action="test", request_id=uuid4(), created_at=r["clock"][0]))
        conn.execute(m.orders.update().values(checkout_session_id="cs_test_old"))
        conn.execute(m.billing_events.insert().values(stripe_event_id="evt_old", event_type="checkout.session.completed",
            object_id="cs_test_old", state="processed", received_at=r["clock"][0]))
    r["clock"][0] += timedelta(days=91)
    drain(r)
    assert rows(r, m.audit_events) == rows(r, m.billing_events) == []
    order = rows(r, m.orders)[0]
    assert order["checkout_session_id"] is None and order["owner_id"] is None
    assert order["amount"] == 100


def test_upload_lease_prevents_delete_before_inflight_write_finishes(review):
    r = review
    service = r["client"].app.state.documents
    pending = service.begin(token(r), UUID(r["pid"]), "text", "upload-lease-test")
    remove(r)
    lifecycle(r).maintain()
    assert next(x for x in rows(r, m.storage_reservations) if x["document_id"] == pending.document_id)["state"] == "reserved"
    service.store.write(pending.key, b"Synthetic late write", "text/plain")
    r["clock"][0] += timedelta(minutes=11)
    drain(r)
    assert rows(r, m.documents) == [] and list(service.store.directory.iterdir()) == []
