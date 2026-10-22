"""MT-12 review APIs against seeded synthetic results; never invoke any model."""
from datetime import timedelta
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import UUID, uuid4
import pytest
import sqlalchemy as sa
from referral_review.persistence import models as m
from referral_review.errors import ApiError
from referral_review.reviews.contracts import HandoffDraftInput
from referral_review.packets.service import _hash
from test_identity import auth_client, sign_in
from test_packets import workspace, create, upload, save


@pytest.fixture
def review(workspace):
    client, identity, clock, transport, headers = workspace
    pid = create(workspace).json()["id"]
    did = upload(workspace, pid, "Synthetic Example")
    revision = save(workspace, pid, 0, [did]).json()["id"]
    owner = UUID(client.get("/auth/session").json()["user"]["id"])
    r = dict(workspace=workspace, client=client, identity=identity, clock=clock, transport=transport,
        pid=pid, did=did, revision=revision, owner=owner, headers=headers)
    r["rid"], r["fid"], r["eid"] = seed_result(r)
    return r


def seed_result(r, state="succeeded"):
    rid, fid, eid, fact = [uuid4() for _ in range(4)]
    with r["identity"].engine.begin() as conn:
        conn.execute(m.runs.insert().values(id=rid, packet_id=UUID(r["pid"]), owner_id=r["owner"],
            revision_id=UUID(r["revision"]), checklist_version="outpatient-referral-demo@1", mode="fake",
            state=state, input_hash="a" * 64, prompt_version="synthetic", schema_version="0.1.0",
            created_at=r["clock"][0], finished_at=r["clock"][0] if state == "succeeded" else None))
        page = conn.execute(sa.select(m.document_pages).where(m.document_pages.c.document_id == UUID(r["did"]))).mappings().one()
        conn.execute(m.evidence.insert().values(id=eid, run_id=rid, revision_id=UUID(r["revision"]),
            document_id=UUID(r["did"]), page_number=1, start_cp=0, end_cp=17, quote="Synthetic Example", text_hash=page["text_hash"]))
        conn.execute(m.facts.insert().values(id=fact, run_id=rid, field_key="patient.name", value_raw="Synthetic Example", assertion_status="stated"))
        conn.execute(m.fact_evidence.insert().values(fact_id=fact, evidence_id=eid, run_id=rid))
        conn.execute(m.findings.insert().values(id=fid, run_id=rid, rule_id="C01", checklist_version="outpatient-referral-demo@1",
            kind="identity_mismatch", field_keys=["patient.name"], message="Synthetic identity needs review"))
        conn.execute(m.finding_documents.insert().values(finding_id=fid, document_id=UUID(r["did"]), run_id=rid, revision_id=UUID(r["revision"])))
        conn.execute(m.finding_facts.insert().values(finding_id=fid, fact_id=fact, run_id=rid))
        conn.execute(m.finding_evidence.insert().values(finding_id=fid, evidence_id=eid, run_id=rid))
    return str(rid), str(fid), str(eid)


def write(r, path, body, method="post", key=None):
    return getattr(r["client"], method)(path, json=body, headers=r["headers"] | {"Idempotency-Key": key or uuid4().hex})


def resolve(r, version=0, action="resolve", **kw):
    return write(r, f"/runs/{r['rid']}/findings/{r['fid']}/resolutions",
        dict(expected_review_version=version, action=action, **kw))


def confirm(r, version=0, **kw):
    return write(r, f"/packets/{r['pid']}/confirm", dict(expected_review_version=version,
        revision_id=r["revision"], mode="assisted", run_id=r["rid"]) | kw)


def draft(r, version=0, **kw):
    return write(r, f"/packets/{r['pid']}/handoff-draft", dict(expected_revision=1,
        expected_review_version=version, mode="manual", fields={"note": "Synthetic reviewer note"}) | kw, "put")


def history(r, **params):
    return r["client"].get(f"/packets/{r['pid']}/review-history", params=params)


def test_open_block_reasons_reopen_and_immutable_overlay(review):
    r = review
    assert confirm(r).json()["error"]["code"] == "OPEN_FINDINGS"
    for action in ["dismiss", "defer"]:
        assert resolve(r, action=action, reason=" \n").status_code == 422
    response = resolve(r, corrected_value="Reviewer correction", linked_evidence_ids=[r["eid"]])
    assert response.status_code == 201, response.text
    assert response.json()["content"]["provenance"] == "Reviewer supplied"
    assert resolve(r).json()["error"]["current_review_version"] == 1
    assert resolve(r, 1, "reopen").json()["content"]["status"] == "open"
    assert confirm(r, 2).status_code == 409
    assert resolve(r, 2, "defer", reason="Need identity verification").status_code == 201
    snap = confirm(r, 3)
    assert snap.status_code == 201, snap.text
    payload = snap.json()["payload"]
    assert payload["warnings"][0] == "Identity unresolved"
    assert payload["status"] == "Reviewed — unresolved items remain"
    assert payload["result"]["facts"][0]["value_raw"] == "Synthetic Example"
    assert payload["result"]["evidence"][0]["quote"] == "Synthetic Example"
    assert payload["decisions"][r["fid"]]["content"]["corrected_value"] is None
    assert snap.json()["payload_hash"] == _hash(payload)
    assert len(history(r).json()["items"]) == 4


@pytest.mark.parametrize("action,warning", [("resolve", False), ("dismiss", True), ("defer", True)])
def test_identity_warning_only_cleared_by_resolution(review, action, warning):
    r = review
    assert resolve(r, action=action, reason="Synthetic decision").status_code == 201
    snap = confirm(r, 1).json()
    assert snap["payload"]["identity_unresolved"] is warning
    assert snap["has_unresolved"] is (action == "defer")


def test_manual_no_fake_run_provenance_and_snapshot_survives_edits(review):
    r = review
    assert draft(r).status_code == 200
    assert confirm(r, 1, mode="manual").status_code == 422  # run_id must be absent
    snap = confirm(r, 1, mode="manual", run_id=None)
    assert snap.status_code == 201, snap.text
    snap = snap.json()
    assert snap["run_id"] is None and snap["payload"]["result"] is None
    assert snap["payload"]["warnings"] == ["Not automatically checked"]
    assert snap["payload"]["handoff"]["fields"]["note"]["provenance"] == "Reviewer supplied"
    assert not snap["historical"]
    assert draft(r, 2, fields={"note": "Edited"}).status_code == 200
    later = r["client"].get(f"/packets/{r['pid']}/snapshots/{snap['id']}").json()
    assert later["historical"] and later["payload"] == snap["payload"] and later["payload_hash"] == snap["payload_hash"]
    drafts = [x for x in history(r).json()["items"] if x["kind"] == "draft"]
    assert {x["content"]["fields"]["note"]["value"] for x in drafts} == {"Edited", "Synthetic reviewer note"}
    with r["identity"].engine.begin() as conn:
        assert conn.execute(sa.select(sa.func.count()).select_from(m.usage_reservations)).scalar_one() == 0


def test_new_run_does_not_inherit_decisions_or_draft(review):
    r = review
    assert resolve(r).status_code == 201
    assert draft(r, 1, mode="assisted", run_id=r["rid"]).status_code == 200
    r["rid"], r["fid"], r["eid"] = seed_result(r)
    assert confirm(r, 2).json()["error"]["code"] == "OPEN_FINDINGS"
    assert resolve(r, 2).status_code == 201
    snap = confirm(r, 3).json()["payload"]
    assert snap["handoff"]["fields"] == {}
    assert len(snap["decisions"]) == 1


def test_source_change_blocks_writes_preserves_history(review):
    r = review
    assert draft(r).status_code == 200
    snap = confirm(r, 1, mode="manual", run_id=None).json()
    did = upload(r["workspace"], r["pid"], "Changed source")
    assert save(r["workspace"], r["pid"], 1, [did]).status_code == 201
    assert resolve(r, 2).json()["error"]["code"] == "STALE_RUN"
    assert draft(r, 2).json()["error"]["code"] == "REVISION_CONFLICT"
    assert confirm(r, 2).json()["error"]["code"] == "REVISION_CONFLICT"
    assert r["client"].get(f"/packets/{r['pid']}/handoff-draft").json()["stale"]
    assert r["client"].get(f"/packets/{r['pid']}/snapshots/{snap['id']}").json()["historical"]


@pytest.mark.parametrize("state", ["pending", "running", "failed", "cancelled", "outcome_unknown"])
def test_non_success_run_cannot_be_reviewed(review, state):
    r = review
    r["rid"], r["fid"], r["eid"] = seed_result(r, state)
    assert resolve(r).json()["error"]["code"] == "STALE_RUN"
    assert draft(r, mode="assisted", run_id=r["rid"]).json()["error"]["code"] == "STALE_RUN"
    assert confirm(r).json()["error"]["code"] == "STALE_RUN"


def test_idempotency_each_mutation_replays_original_and_rejects_changed_payload(review):
    r = review
    cases = [
        (f"/runs/{r['rid']}/findings/{r['fid']}/resolutions", "post", dict(expected_review_version=0, action="resolve")),
        (f"/packets/{r['pid']}/handoff-draft", "put", dict(expected_revision=1, expected_review_version=1, mode="manual", fields={"note": "First"})),
        (f"/packets/{r['pid']}/confirm", "post", dict(revision_id=r["revision"], expected_review_version=2, mode="manual"))]
    for path, method, body in cases:
        key = uuid4().hex
        first = write(r, path, body, method, key)
        assert first.status_code in {200, 201}, first.text
        assert write(r, path, body, method, key).json() == first.json()
        assert write(r, path, body | {"expected_review_version": 99}, method, key).json()["error"]["code"] == "IDEMPOTENCY_CONFLICT"
    assert len(history(r).json()["items"]) == 3


def test_history_cursor_validation_pagination_and_owner_scope(review):
    r = review
    for version in range(3):
        assert draft(r, version).status_code == 200
    page = history(r, limit=2).json()
    tail = history(r, limit=2, cursor=page["next_cursor"]).json()
    assert len({x["id"] for x in page["items"] + tail["items"]}) == 3 and tail["next_cursor"] is None
    assert history(r, cursor="tampered").status_code == 422
    assert history(r, limit=51).status_code == 422
    other_pid = create(r["workspace"]).json()["id"]
    assert r["client"].get(f"/packets/{other_pid}/review-history", params={"cursor": page["next_cursor"]}).status_code == 422
    snap = confirm(r, 3, mode="manual", run_id=None).json()
    r["transport"].subject = 54321
    sign_in(r["client"])
    r["headers"]["X-CSRF-Token"] = r["client"].get("/auth/session").json()["csrf_token"]
    assert history(r).status_code == 404
    assert resolve(r, 4).status_code == 404
    assert draft(r, 4).status_code == 404
    assert confirm(r, 4).status_code == 404
    assert r["client"].get(f"/packets/{r['pid']}/snapshots/{snap['id']}").status_code == 404


def test_foreign_evidence_finding_and_forged_provenance_rejected(review):
    r = review
    other_rid, other_fid, other_eid = seed_result(r)
    assert resolve(r, linked_evidence_ids=[other_eid]).status_code == 404
    assert resolve(r, provenance="Source evidence").status_code == 422
    assert draft(r, fields={"note": {"value": "x", "provenance": "Source evidence"}}).status_code == 422
    assert write(r, f"/runs/{r['rid']}/findings/{other_fid}/resolutions", dict(expected_review_version=0, action="resolve")).status_code == 404
    assert history(r).json()["items"] == []


def test_concurrent_same_version_keeps_one_draft(review):
    r = review
    service = r["client"].app.state.reviews
    token = r["client"].cookies.get(r["identity"].session_cookie)
    barrier = Barrier(2)
    def attempt(note):
        barrier.wait(timeout=10)
        try:
            return service.save_draft(token, UUID(r["pid"]), HandoffDraftInput(expected_revision=1,
                expected_review_version=0, mode="manual", fields={"note": note}), uuid4().hex).kind
        except ApiError as exc:
            return exc.code.value
    with ThreadPoolExecutor(2) as pool:
        outcomes = list(pool.map(attempt, ["First", "Second"]))
    assert sorted(outcomes) == ["REVIEW_CONFLICT", "draft"]
    assert len(history(r).json()["items"]) == 1


def test_snapshot_and_history_database_updates_are_rejected(review):
    r = review
    snap = confirm(r, mode="manual", run_id=None).json()
    for table, changes in [(m.review_snapshots, dict(payload={})), (m.review_events, dict(content={}))]:
        with pytest.raises(sa.exc.IntegrityError):
            with r["identity"].engine.begin() as conn:
                conn.execute(table.update().where(table.c.id == UUID(snap["id"])).values(**changes))


def test_deleted_and_expired_packets_hide_reviews(review):
    r = review
    assert draft(r).status_code == 200
    assert r["client"].put(f"/packets/{r['pid']}/handoff-draft", json={}).status_code == 403
    r["clock"][0] += timedelta(days=8)
    sign_in(r["client"])
    assert history(r).status_code == 404


@pytest.mark.parametrize("operation", ["resolution", "draft", "confirmation"])
def test_failed_review_transaction_rolls_back_version_content_and_key(review, monkeypatch, operation):
    r = review
    service = r["client"].app.state.reviews
    original = service._event
    def fail(*args, **kwargs):
        original(*args, **kwargs)
        raise RuntimeError("synthetic rollback")
    monkeypatch.setattr(service, "_event", fail)
    response = (resolve(r) if operation == "resolution" else draft(r) if operation == "draft"
                else confirm(r, mode="manual", run_id=None))
    assert response.status_code == 500
    with r["identity"].engine.begin() as conn:
        assert conn.execute(sa.select(m.packets.c.review_version).where(m.packets.c.id == UUID(r["pid"]))).scalar_one() == 0
        for table in [m.resolutions, m.review_events, m.handoff_drafts, m.review_snapshots]:
            assert conn.execute(sa.select(sa.func.count()).select_from(table)).scalar_one() == 0
        assert conn.execute(sa.select(sa.func.count()).select_from(m.idempotency).where(m.idempotency.c.operation.like("review:%"))).scalar_one() == 0


def test_tombstone_blocks_review_reads_and_writes(review):
    r = review
    snap = confirm(r, mode="manual", run_id=None).json()
    response = r["client"].delete(f"/packets/{r['pid']}", headers=r["headers"] | {"Idempotency-Key": uuid4().hex})
    assert response.status_code == 202
    assert history(r).status_code == 404
    assert draft(r, 1).status_code == 404
    assert resolve(r, 1).status_code == 404
    assert r["client"].get(f"/packets/{r['pid']}/snapshots/{snap['id']}").status_code == 404


def test_review_state_latest_decisions_and_historical_manifest_are_read_only(review):
    r = review
    path = f"/runs/{r['rid']}/review"
    initial = r["client"].get(path)
    assert initial.status_code == 200
    assert initial.json()["decisions"] == []
    assert initial.json()["revision"]["id"] == r["revision"]
    assert resolve(r, action="defer", reason="Check identity").status_code == 201
    assert resolve(r, 1, "resolve", corrected_value="Reviewed name", linked_evidence_ids=[r["eid"]]).status_code == 201
    state = r["client"].get(path).json()
    assert state["review_version"] == 2 and not state["stale"]
    assert len(state["decisions"]) == 1
    assert state["decisions"][0]["status"] == "resolved"
    assert state["decisions"][0]["corrected_value"] == "Reviewed name"
    assert r["client"].get(path).json() == state
    did = upload(r["workspace"], r["pid"], "New source")
    assert save(r["workspace"], r["pid"], 1, [did]).status_code == 201
    historical = r["client"].get(path).json()
    assert historical["stale"] and not historical["revision"]["is_current"]
    assert historical["revision"]["documents"][0]["id"] == r["did"]
    assert historical["decisions"] == state["decisions"]
    with r["identity"].engine.begin() as conn:
        assert conn.execute(sa.select(sa.func.count()).select_from(m.usage_reservations)).scalar_one() == 0
    assert r["client"].delete(f"/packets/{r['pid']}", headers=r["headers"] | {"Idempotency-Key": uuid4().hex}).status_code == 202
    assert r["client"].get(path).status_code == 404


def test_review_state_rejects_anonymous_and_other_owner(review):
    r = review
    path = f"/runs/{r['rid']}/review"
    r["client"].cookies.clear()
    assert r["client"].get(path).status_code == 401
    r["transport"].subject = 54321
    sign_in(r["client"])
    assert r["client"].get(path).status_code == 404
