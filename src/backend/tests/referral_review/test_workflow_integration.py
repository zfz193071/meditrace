"""Exercise the MT-22 packet-to-handoff lifecycle through the HTTP API with Fake only."""

from datetime import timedelta
from uuid import UUID, uuid4

import pytest
import sqlalchemy as sa
from fastapi.testclient import TestClient

from referral_review.app import create_app
from referral_review.documents import Documents
from referral_review.documents.storage import LocalStore
from referral_review.extraction import FakeAdapter
from referral_review.identity.service import Identity
from referral_review.persistence import models as m
from referral_review.runs import Runs
from test_identity import auth_client, sign_in
from test_pg_concurrency import pg
from test_handoff import export
from test_lifecycle import drain, remove
from test_packets import workspace, create, upload, save
from test_reviews import resolve, draft, confirm
from test_runs import review as running_review, new_run, post


@pytest.fixture
def postgres_running_review(pg, auth_client, tmp_path):
    _, base_identity, clock, _ = auth_client
    identity = Identity(pg, base_identity.settings, github=base_identity.github, clock=lambda: clock[0])
    documents = Documents(identity, LocalStore(str(tmp_path / "private-postgres")))
    with TestClient(create_app(base_identity.settings, identity=identity, documents=documents),
                    base_url=base_identity.settings.site_origin, follow_redirects=False) as client:
        sign_in(client)
        headers = {"Origin": identity.settings.site_origin,
                   "X-CSRF-Token": client.get("/auth/session").json()["csrf_token"]}
        postgres_workspace = (client, identity, clock, base_identity.github.http_adapter, headers)
        packet = create(postgres_workspace).json()
        document_id = upload(postgres_workspace, packet["id"], "Patient: Synthetic Example")
        revision_id = save(postgres_workspace, packet["id"], 0, [document_id]).json()["id"]
        owner = UUID(client.get("/auth/session").json()["user"]["id"])
        order_id = uuid4()
        with pg.begin() as connection:
            connection.execute(m.orders.insert().values(id=order_id, owner_id=owner, environment="test",
                price_id="synthetic", amount=100, currency="usd", state="paid", created_at=clock[0],
                paid_at=clock[0]))
            connection.execute(m.memberships.insert().values(owner_id=owner, source_order_id=order_id,
                environment="test", valid_from=clock[0], valid_until=clock[0] + timedelta(days=30),
                granted_units=20))
        adapter = FakeAdapter({"facts": [dict(field_key="patient.name", value_raw="Synthetic Example",
            value_normalized=None, assertion_status="stated", temporal_context=None,
            sources=[dict(document_id=document_id, page_number=1, quote="Patient: Synthetic Example")])]})
        service = Runs(identity, adapter_factory=lambda row, source: adapter)
        client.app.state.runs = service
        yield dict(workspace=postgres_workspace, client=client, identity=identity, clock=clock, headers=headers,
            pid=packet["id"], did=document_id, revision=revision_id, owner=owner,
            adapter=adapter, service=service)


def exercise_workflow(r):
    created = new_run(r)
    assert created.status_code == 201, created.text
    run_id = created.json()["id"]
    execution = post(r, run_id, "execute")
    assert execution.status_code == 200, execution.text
    run = execution.json()
    assert run["state"] == "succeeded" and run["mode"] == "fake"
    assert r["adapter"].calls == 1

    r["rid"] = run_id
    review_version = 0
    for finding in run["result"]["findings"]:
        r["fid"] = finding["id"]
        resolution = resolve(r, review_version, action="defer", reason="Synthetic integration review")
        assert resolution.status_code == 201, resolution.text
        review_version += 1

    draft_response = draft(r, review_version, mode="assisted", run_id=run_id,
                           fields={"handoff.summary": "Synthetic referral reviewed"})
    assert draft_response.status_code == 200, draft_response.text
    snapshot_response = confirm(r, review_version + 1)
    assert snapshot_response.status_code == 201, snapshot_response.text
    snapshot = snapshot_response.json()
    assert snapshot["payload"]["has_unresolved"] is True
    assert snapshot["payload"]["run_id"] == run_id

    text_export = export(r, snapshot["id"])
    assert text_export.status_code == 200, text_export.text
    assert "Synthetic referral reviewed" in text_export.text
    assert "unresolved" in text_export.text.lower()

    replacement_text = "Patient: Synthetic Example amendment"
    replacement = upload(r["workspace"], r["pid"], replacement_text)
    next_revision = save(r["workspace"], r["pid"], 1, [replacement])
    assert next_revision.status_code == 201, next_revision.text
    old_snapshot = r["client"].get(f"/packets/{r['pid']}/snapshots/{snapshot['id']}")
    assert old_snapshot.status_code == 200 and old_snapshot.json()["historical"] is True

    r["revision"] = next_revision.json()["id"]
    r["adapter"].output["facts"][0]["sources"][0].update(
        document_id=replacement, quote=replacement_text)
    rerun = new_run(r)
    assert rerun.status_code == 201, rerun.text
    rerun_result = post(r, rerun.json()["id"], "execute")
    assert rerun_result.status_code == 200, rerun_result.text
    assert rerun_result.json()["state"] == "succeeded"
    assert r["adapter"].calls == 2

    remove(r)
    assert r["client"].get(f"/packets/{r['pid']}").status_code == 404
    assert export(r, snapshot["id"]).status_code == 404
    assert drain(r)["backlog"] == 0


def test_packet_review_handoff_revision_and_delete_use_one_api_workflow(running_review):
    exercise_workflow(running_review)


def test_packet_review_handoff_revision_and_delete_use_postgres_api_workflow(postgres_running_review):
    exercise_workflow(postgres_running_review)


def prepare_reviewed_workflow(r):
    created = new_run(r)
    assert created.status_code == 201, created.text
    run_id = created.json()["id"]
    r["rid"] = run_id
    executed = post(r, run_id, "execute")
    assert executed.status_code == 200, executed.text
    findings = executed.json()["result"]["findings"]

    review_version = 0
    for finding in findings:
        r["fid"] = finding["id"]
        resolved = resolve(r, review_version, action="defer", reason="Synthetic ownership check")
        assert resolved.status_code == 201, resolved.text
        review_version += 1
    saved_draft = draft(r, review_version, mode="assisted", run_id=run_id,
                        fields={"handoff.summary": "Synthetic private summary"})
    assert saved_draft.status_code == 200, saved_draft.text
    confirmed = confirm(r, review_version + 1)
    assert confirmed.status_code == 201, confirmed.text
    return confirmed.json()


def protected_reads(r, snapshot_id):
    return [
        f"/packets/{r['pid']}",
        f"/packets/{r['pid']}/draft",
        f"/packets/{r['pid']}/revisions/1",
        f"/packets/{r['pid']}/runs/latest",
        f"/packets/{r['pid']}/documents/{r['did']}",
        f"/packets/{r['pid']}/documents/{r['did']}/pages/1",
        f"/packets/{r['pid']}/documents/{r['did']}/original",
        f"/runs/{r['rid']}",
        f"/runs/{r['rid']}/review",
        f"/packets/{r['pid']}/handoff-draft",
        f"/packets/{r['pid']}/snapshots/{snapshot_id}",
        f"/packets/{r['pid']}/review-history",
        f"/packets/{r['pid']}/snapshots/{snapshot_id}/handoff",
        f"/packets/{r['pid']}/snapshots/{snapshot_id}/export?format=txt",
        f"/packets/{r['pid']}/snapshots/{snapshot_id}/export?format=pdf",
    ]


def protected_writes(r, review_version):
    packet = f"/packets/{r['pid']}"
    run = f"/runs/{r['rid']}"
    context = dict(mode="assisted", run_id=r["rid"], expected_review_version=review_version)
    return [
        ("PATCH", packet, {"title": "Unauthorized replacement"}),
        ("POST", f"{packet}/documents", {"text": "Unauthorized synthetic source"}),
        ("PUT", f"{packet}/draft", dict(expected_draft_version=1, base_revision=1,
            selected_document_ids=[r["did"]], last_location="documents")),
        ("POST", f"{packet}/revisions", dict(expected_revision=1, document_ids=[])),
        ("POST", f"{packet}/runs", dict(revision_id=r["revision"],
            checklist_version="outpatient-referral-demo@1")),
        ("POST", f"{run}/execute", None),
        ("POST", f"{run}/cancel", None),
        ("POST", f"{run}/reconcile", None),
        ("POST", f"{run}/findings/{r['fid']}/resolutions",
            dict(expected_review_version=review_version, action="resolve")),
        ("PUT", f"{packet}/handoff-draft",
            context | dict(expected_revision=1, fields={"handoff.summary": "Unauthorized replacement"})),
        ("POST", f"{packet}/confirm", context | dict(revision_id=r["revision"])),
    ]


def business_state(r):
    # Compare values as well as row counts: rejection must not overwrite reviews,
    # consume quota, reserve storage, enqueue cleanup, or record a successful key.
    tables = (m.packets, m.packet_drafts, m.documents, m.document_pages,
        m.revisions, m.revision_documents, m.runs, m.review_events, m.review_snapshots,
        m.handoff_drafts, m.resolutions, m.resolution_evidence, m.memberships,
        m.usage_reservations, m.budget_buckets, m.storage_reservations,
        m.storage_buckets, m.cleanup_jobs, m.idempotency, m.usage_buckets,
        m.usage_details, m.concurrency_slots)
    with r["identity"].engine.begin() as connection:
        state = {table.name: [dict(row) for row in connection.execute(
            sa.select(table).order_by(*table.primary_key.columns)).mappings()] for table in tables}
    store = r["client"].app.state.documents.store
    state["private_objects"] = {path.name: path.read_bytes() for path in store.directory.iterdir()}
    return state


def assert_hidden(response):
    assert response.status_code == 404, f"{response.request.method} {response.request.url}: {response.text}"
    assert response.json()["error"]["code"] == "NOT_FOUND"
    assert response.headers["cache-control"] == "private, no-store"
    assert "Synthetic private summary" not in response.text
    assert "Synthetic Example" not in response.text


def assert_write_rejected_without_changes(r, method, path, body, status=404, code="NOT_FOUND"):
    before = business_state(r)
    calls = r["adapter"].calls
    response = r["client"].request(method, path, json=body,
        headers=r["headers"] | {"Idempotency-Key": uuid4().hex})
    assert response.status_code == status, f"{method} {path}: {response.text}"
    assert response.json()["error"]["code"] == code
    assert response.headers["cache-control"] == "private, no-store"
    assert business_state(r) == before, f"Rejected {method} {path} changed business state"
    assert r["adapter"].calls == calls


def exercise_resource_isolation(r):
    snapshot = prepare_reviewed_workflow(r)
    client, identity, _, transport, _ = r["workspace"]
    original_owner = client.get("/auth/session").json()["user"]["id"]
    client.cookies.clear()
    transport.subject = 67890
    sign_in(client)
    assert client.get("/auth/session").json()["user"]["id"] != original_owner
    r["headers"] = {"Origin": identity.settings.site_origin,
                    "X-CSRF-Token": client.get("/auth/session").json()["csrf_token"]}
    assert client.get("/packets").json()["items"] == []
    for path in protected_reads(r, snapshot["id"]):
        assert_hidden(client.get(path))
    for method, path, body in protected_writes(r, snapshot["review_version"]) + [
        ("DELETE", f"/packets/{r['pid']}", None)
    ]:
        assert_write_rejected_without_changes(r, method, path, body)
    assert r["adapter"].calls == 1


def test_workflow_resources_are_hidden_from_a_second_account(running_review):
    exercise_resource_isolation(running_review)


def test_postgres_workflow_resources_are_hidden_from_a_second_account(postgres_running_review):
    exercise_resource_isolation(postgres_running_review)


def exercise_inaccessible_workflow(r, reason):
    snapshot = prepare_reviewed_workflow(r)
    if reason == "deleted":
        remove(r)
    else:
        r["clock"][0] += timedelta(days=7)
        # Sessions expire too. Renew identity so the assertions exercise packet
        # expiry (404), not an expired session (401), before any maintenance runs.
        sign_in(r["client"])
        r["headers"]["X-CSRF-Token"] = r["client"].get("/auth/session").json()["csrf_token"]

    def check_access():
        assert r["client"].get("/packets").json()["items"] == []
        for path in protected_reads(r, snapshot["id"]):
            assert_hidden(r["client"].get(path))
        for method, path, body in protected_writes(r, snapshot["review_version"]):
            assert_write_rejected_without_changes(r, method, path, body)

    check_access()
    assert drain(r)["backlog"] == 0
    check_access()
    assert r["adapter"].calls == 1


@pytest.mark.parametrize("reason", ["deleted", "expired"])
def test_workflow_access_is_revoked_before_and_after_cleanup(running_review, reason):
    exercise_inaccessible_workflow(running_review, reason)


@pytest.mark.parametrize("reason", ["deleted", "expired"])
def test_postgres_workflow_access_is_revoked_before_and_after_cleanup(postgres_running_review, reason):
    exercise_inaccessible_workflow(postgres_running_review, reason)


def exercise_packet_resource_binding(r):
    first_snapshot = prepare_reviewed_workflow(r)
    first_run = r["client"].get(f"/runs/{r['rid']}").json()
    other = dict(r)
    other["pid"] = create(r["workspace"], "Other synthetic packet").json()["id"]
    other["did"] = upload(r["workspace"], other["pid"], "Patient: Synthetic Example")
    other["revision"] = save(r["workspace"], other["pid"], 0, [other["did"]]).json()["id"]
    r["adapter"].output["facts"][0]["sources"][0]["document_id"] = other["did"]
    other_snapshot = prepare_reviewed_workflow(other)

    # Both resources belong to the signed-in user. Binding must still be checked
    # against the packet/run in the route, not just the account's ownership.
    for path in [
        f"/packets/{other['pid']}/documents/{r['did']}",
        f"/packets/{other['pid']}/documents/{r['did']}/pages/1",
        f"/packets/{other['pid']}/documents/{r['did']}/original",
        f"/packets/{other['pid']}/snapshots/{first_snapshot['id']}",
        f"/packets/{other['pid']}/snapshots/{first_snapshot['id']}/handoff",
        f"/packets/{other['pid']}/snapshots/{first_snapshot['id']}/export?format=txt",
        f"/packets/{other['pid']}/snapshots/{first_snapshot['id']}/export?format=pdf",
    ]:
        assert_hidden(r["client"].get(path))

    packet = f"/packets/{other['pid']}"
    version = other_snapshot["review_version"]
    context = dict(mode="assisted", run_id=r["rid"], expected_review_version=version)
    resolution = dict(expected_review_version=version, action="resolve")
    for method, path, body in [
        ("PUT", f"{packet}/handoff-draft",
            context | dict(expected_revision=1, fields={"note": "Synthetic cross-packet input"})),
        ("POST", f"{packet}/confirm", context | dict(revision_id=other["revision"])),
        ("POST", f"/runs/{other['rid']}/findings/{r['fid']}/resolutions", resolution),
        ("POST", f"/runs/{other['rid']}/findings/{other['fid']}/resolutions",
            resolution | dict(linked_evidence_ids=[first_run["result"]["evidence"][0]["id"]])),
    ]:
        assert_write_rejected_without_changes(r, method, path, body)

    # Invalid member IDs in otherwise owned payloads use validation/conflict
    # errors, rather than the 404 used for inaccessible route resources.
    for method, path, body, status, code in [
        ("POST", f"{packet}/revisions", dict(expected_revision=1, document_ids=[r["did"]]),
            422, "SCHEMA_INVALID"),
        ("PUT", f"{packet}/draft", dict(expected_draft_version=1, base_revision=1,
            selected_document_ids=[r["did"]], last_location="documents"), 422, "SCHEMA_INVALID"),
        ("POST", f"{packet}/runs", dict(revision_id=r["revision"],
            checklist_version="outpatient-referral-demo@1"), 409, "SOURCE_CHANGED"),
        ("POST", f"{packet}/confirm", context | dict(run_id=other["rid"], revision_id=r["revision"]),
            409, "REVISION_CONFLICT"),
    ]:
        assert_write_rejected_without_changes(r, method, path, body, status, code)

    for source, snapshot in [(r, first_snapshot), (other, other_snapshot)]:
        current = r["client"].get(f"/packets/{source['pid']}/snapshots/{snapshot['id']}")
        assert current.status_code == 200 and current.json() == snapshot
        assert export(source, snapshot["id"]).status_code == 200
    assert r["adapter"].calls == 2


def test_workflow_resources_cannot_be_mixed_between_owned_packets(running_review):
    exercise_packet_resource_binding(running_review)


def test_postgres_workflow_resources_cannot_be_mixed_between_owned_packets(postgres_running_review):
    exercise_packet_resource_binding(postgres_running_review)
