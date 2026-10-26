"""Exercise the MT-22 packet-to-handoff lifecycle through the HTTP API with Fake only."""

from test_handoff import export
from test_lifecycle import drain, remove
from test_identity import auth_client
from test_packets import workspace, upload, save
from test_reviews import resolve, draft, confirm
from test_runs import review as running_review, new_run, post


def test_packet_review_handoff_revision_and_delete_use_one_api_workflow(running_review):
    r = running_review
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
