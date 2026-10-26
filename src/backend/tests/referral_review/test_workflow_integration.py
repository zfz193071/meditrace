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
