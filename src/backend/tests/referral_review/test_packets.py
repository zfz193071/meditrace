"""MT-07 packet API through real session, SQLite and private text upload."""

from datetime import timedelta
from uuid import UUID, uuid4

import pytest
import sqlalchemy as sa

from referral_review.documents import Documents
from referral_review.documents.storage import LocalStore
from referral_review.persistence import models as m
from test_identity import auth_client, sign_in


@pytest.fixture
def workspace(auth_client, tmp_path):
    client, identity, clock, transport = auth_client
    sign_in(client)
    client.app.state.documents = Documents(identity, LocalStore(str(tmp_path / "private")))
    headers = {"Origin": identity.settings.site_origin,
               "X-CSRF-Token": client.get("/auth/session").json()["csrf_token"]}
    return client, identity, clock, transport, headers


def create(workspace, title="Synthetic referral", key=None, **changes):
    client, identity, _, _, _ = workspace
    headers = {"Origin": identity.settings.site_origin,
               "X-CSRF-Token": client.get("/auth/session").json()["csrf_token"]}
    return client.post("/packets", json={"title": title, "synthetic_data_ack": True} | changes,
        headers=headers | {"Idempotency-Key": key or uuid4().hex})


def upload(workspace, packet_id, text="Synthetic patient 😀"):
    client, identity, _, _, _ = workspace
    headers = {"Origin": identity.settings.site_origin,
               "X-CSRF-Token": client.get("/auth/session").json()["csrf_token"]}
    response = client.post(f"/packets/{packet_id}/documents", json={"text": text},
        headers=headers | {"Idempotency-Key": uuid4().hex})
    assert response.status_code == 201, response.text
    assert response.json()["parse_status"] == "ready"
    return response.json()["id"]


def save(workspace, packet_id, expected, document_ids, key=None):
    client, identity, _, _, _ = workspace
    headers = {"Origin": identity.settings.site_origin,
               "X-CSRF-Token": client.get("/auth/session").json()["csrf_token"]}
    return client.post(f"/packets/{packet_id}/revisions",
        json={"expected_revision": expected, "document_ids": document_ids},
        headers=headers | {"Idempotency-Key": key or uuid4().hex})


def test_create_requires_ack_csrf_and_idempotency_then_lists_stably(workspace):
    client, _, _, _, headers = workspace
    assert client.post("/packets", json={"title": "Sensitive"}).status_code == 403
    assert create(workspace, synthetic_data_ack=False).status_code == 422
    first = create(workspace, "  合成😀  ", key="packet-key-1")
    assert first.status_code == 201, first.text
    assert first.json()["title"] == "合成😀" and first.json()["state"] == "empty"
    assert first.json()["synthetic_data_ack"] is True
    assert create(workspace, "合成😀", key="packet-key-1").json() == first.json()
    assert create(workspace, "Different", key="packet-key-1").status_code == 409
    second = create(workspace).json()
    third = create(workspace).json()
    seen = []
    cursor = None
    while True:
        result = client.get("/packets", params={"limit": 2, **({"cursor": cursor} if cursor else {})})
        assert result.status_code == 200, result.text
        seen.extend(item["id"] for item in result.json()["items"])
        cursor = result.json()["next_cursor"]
        if cursor is None:
            break
    assert len(seen) == len(set(seen)) == 3
    assert set(seen) == {first.json()["id"], second["id"], third["id"]}
    assert client.get("/packets", params={"cursor": "tampered"}).status_code == 422
    assert client.get("/packets", params={"limit": 51}).status_code == 422


def test_ten_packet_cap_is_owner_scoped_and_expiry_blocks_reads(workspace):
    client, _, clock, _, _ = workspace
    ids = [create(workspace).json()["id"] for _ in range(10)]
    assert create(workspace).json()["error"]["code"] == "PACKET_LIMIT"
    clock[0] += timedelta(days=7)
    sign_in(client)
    assert client.get(f"/packets/{ids[0]}").status_code == 404
    assert client.get("/packets").json()["items"] == []


def test_revision_rejects_stale_or_foreign_and_preserves_history(workspace):
    client, identity, _, transport, _ = workspace
    pid = create(workspace).json()["id"]
    first, second = upload(workspace, pid, "First referral 😀"), upload(workspace, pid, "Replacement referral")
    one = save(workspace, pid, 0, [first], key="revision-key-1")
    assert one.status_code == 201, one.text
    assert one.json()["revision_number"] == 1 and one.json()["is_current"]
    manifest = one.json()["manifest_hash"]
    assert save(workspace, pid, 0, [second]).json()["error"] == {
        "code": "REVISION_CONFLICT", "message": "Packet revision changed; refresh before saving.",
        "retryable": False, "current_revision": 1,
    }
    assert save(workspace, pid, 0, [first], key="revision-key-1").json() == one.json()
    assert save(workspace, pid, 1, [first]).status_code == 422
    assert save(workspace, pid, 1, [first, first]).status_code == 422
    assert save(workspace, pid, 1, [str(uuid4())]).status_code == 422
    original_token = client.cookies.get(identity.session_cookie)
    client.cookies.clear()
    transport.subject = 67890
    sign_in(client)
    foreign_pid = create(workspace).json()["id"]
    foreign_doc = upload(workspace, foreign_pid)
    client.cookies.clear()
    client.cookies.set(identity.session_cookie, original_token)
    assert save(workspace, pid, 1, [foreign_doc]).status_code == 422
    assert client.get(f"/packets/{foreign_pid}").status_code == 404
    two = save(workspace, pid, 1, [second])
    assert two.status_code == 201 and two.json()["revision_number"] == 2
    old = client.get(f"/packets/{pid}/revisions/1").json()
    assert old["manifest_hash"] == manifest and old["documents"][0]["id"] == first
    assert old["is_current"] is False
    assert client.get(f"/packets/{pid}/documents/{first}/pages/1").status_code == 200
    removed = save(workspace, pid, 2, [])
    assert removed.status_code == 201 and removed.json()["documents"] == []
    detail = client.get(f"/packets/{pid}").json()
    assert detail["current_document_ids"] == [] and detail["state"] == "empty"


def test_draft_survives_logout_login_and_only_ids_enter_redirect(workspace):
    client, identity, _, _, headers = workspace
    pid = create(workspace).json()["id"]
    did = upload(workspace, pid)
    url = f"/packets/{pid}/draft"
    payload = {"expected_draft_version": 0, "base_revision": 0,
               "selected_document_ids": [did], "last_location": "documents"}
    first = client.put(url, json=payload, headers=headers | {"Idempotency-Key": "draft-key-1"})
    assert first.status_code == 200 and first.json()["draft_version"] == 1
    assert client.put(url, json=payload, headers=headers | {"Idempotency-Key": "draft-key-1"}).json() == first.json()
    assert client.put(url, json=payload, headers=headers | {"Idempotency-Key": "draft-key-2"}).json()["error"]["code"] == "DRAFT_CONFLICT"
    assert client.post("/auth/logout", headers=headers).status_code == 204
    assert client.get(url).status_code == 401
    return_path = f"/workspace/packets/{pid}"
    signed_in = sign_in(client, return_path)
    assert signed_in.headers["location"] == return_path
    assert "Synthetic patient" not in signed_in.headers["location"]
    assert client.get(url).json()["selected_document_ids"] == [did]
    assert client.get(f"/packets/{pid}").json()["draft"]["draft_version"] == 1


def test_draft_and_title_enforce_owner_version_and_safe_metadata(workspace):
    client, identity, _, transport, headers = workspace
    pid = create(workspace).json()["id"]
    did = upload(workspace, pid)
    url = f"/packets/{pid}/draft"
    payload = {"expected_draft_version": 0, "base_revision": 0,
               "selected_document_ids": [did], "last_location": "documents"}
    assert client.put(url, json=payload | {"selected_document_ids": [did, did]},
        headers=headers | {"Idempotency-Key": uuid4().hex}).status_code == 422
    assert client.put(url, json=payload | {"selected_document_ids": [str(uuid4())]},
        headers=headers | {"Idempotency-Key": uuid4().hex}).status_code == 422
    assert client.patch(f"/packets/{pid}", json={"title": "control\ninside"},
        headers=headers | {"Idempotency-Key": uuid4().hex}).status_code == 422
    renamed = client.patch(f"/packets/{pid}", json={"title": "Updated synthetic"},
        headers=headers | {"Idempotency-Key": "title-key-1"})
    assert renamed.status_code == 200 and renamed.json()["title"] == "Updated synthetic"
    assert client.get(f"/packets/{pid}").json()["current_revision"] == 0
    original_token = client.cookies.get(identity.session_cookie)
    client.cookies.clear()
    transport.subject = 67890
    sign_in(client)
    assert client.get(url).status_code == 404
    assert client.get(f"/packets/{pid}").status_code == 404
    assert client.get("/packets").json()["items"] == []
    client.cookies.clear()
    client.cookies.set(identity.session_cookie, original_token)
    assert client.put(url, json=payload, headers=headers | {"Idempotency-Key": uuid4().hex}).status_code == 200
    save(workspace, pid, 0, [did])
    stale = client.put(url, json=payload | {"expected_draft_version": 1},
        headers=headers | {"Idempotency-Key": uuid4().hex})
    assert stale.status_code == 409 and stale.json()["error"]["current_revision"] == 1


def test_tombstone_blocks_all_reads_and_enqueues_cleanup(workspace):
    client, identity, _, _, headers = workspace
    pid = create(workspace).json()["id"]
    did = upload(workspace, pid)
    response = client.delete(f"/packets/{pid}", headers=headers | {"Idempotency-Key": "delete-key-1"})
    assert response.status_code == 202 and response.json()["status"] == "pending_cleanup"
    assert client.get(f"/packets/{pid}").status_code == 404
    assert client.get(f"/packets/{pid}/documents/{did}/original").status_code == 404
    assert client.get(f"/packets/{pid}/draft").status_code == 404
    assert client.get("/packets").json()["items"] == []
    assert client.delete(f"/packets/{pid}", headers=headers | {"Idempotency-Key": "delete-key-1"}).status_code == 202
    with identity.engine.begin() as conn:
        jobs = conn.execute(sa.select(m.cleanup_jobs).where(m.cleanup_jobs.c.entity_id == UUID(pid),
            m.cleanup_jobs.c.kind == "packet")).mappings().all()
        assert len(jobs) == 1 and jobs[0]["state"] == "pending"


def test_revision_rejects_unready_and_combined_page_limit(workspace):
    client, identity, clock, _, _ = workspace
    pid = create(workspace).json()["id"]
    owner = UUID(client.get("/auth/session").json()["user"]["id"])
    ready_ids = []
    with identity.engine.begin() as conn:
        for index in range(2):
            did = uuid4()
            ready_ids.append(str(did))
            conn.execute(m.documents.insert().values(id=did, packet_id=UUID(pid), owner_id=owner,
                kind="pdf", filename=f"fixture-{index}.pdf", sha256="a" * 64,
                storage_key=f"synthetic/{did}", byte_size=100, parse_status="ready",
                parser_version="pypdf-6.21.1/text-v1", page_count=13, created_at=clock[0]))
            conn.execute(m.document_pages.insert(), [dict(document_id=did, page_number=page,
                normalized_text="A", text_hash="5" * 64, parse_quality="ready") for page in range(1, 14)])
        bad = uuid4()
        conn.execute(m.documents.insert().values(id=bad, packet_id=UUID(pid), owner_id=owner,
            kind="pdf", filename="unreadable.pdf", sha256="a" * 64,
            storage_key=f"synthetic/{bad}", byte_size=100, parse_status="rejected",
            parser_version="pypdf-6.21.1/text-v1", page_count=1,
            parse_error_code="PDF_UNREADABLE_PAGE", parse_error_page=1, created_at=clock[0]))
    assert save(workspace, pid, 0, [str(bad)]).status_code == 422
    over = save(workspace, pid, 0, ready_ids)
    assert over.status_code == 409 and over.json()["error"]["code"] == "PACKET_INPUT_LIMIT"
    assert client.get(f"/packets/{pid}").json()["current_revision"] == 0
