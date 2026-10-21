"""Real identity + isolated SQL + private local storage; no provider calls."""

from datetime import timedelta
import hashlib
from pathlib import Path
from uuid import UUID, uuid4

import pytest
import sqlalchemy as sa
from sqlalchemy.exc import OperationalError

from referral_review.documents import Documents
from referral_review.documents.storage import LocalStore, MAX_BYTES, StorageUnavailable, object_key
from referral_review.persistence import models as m
from test_identity import auth_client, sign_in

PDF = b"%PDF-1.7\nSynthetic malformed fixture.\n%%EOF\n"


@pytest.fixture
def docs(auth_client, tmp_path):
    client, identity, clock, transport = auth_client
    sign_in(client)
    owner_id = UUID(client.get("/auth/session").json()["user"]["id"])
    packet_id = uuid4()
    with identity.engine.begin() as conn:
        conn.execute(m.packets.insert().values(id=packet_id, owner_id=owner_id, title="Synthetic packet",
            created_at=clock[0], updated_at=clock[0], expires_at=clock[0] + timedelta(days=7)))
    documents = Documents(identity, LocalStore(str(tmp_path / "private")))
    client.app.state.documents = documents
    headers = {"Origin": identity.settings.site_origin,
               "X-CSRF-Token": client.get("/auth/session").json()["csrf_token"]}
    return client, documents, packet_id, headers, clock, transport


def send(docs, body=PDF, *, filename="Synthetic.pdf", mime="application/pdf", key=None, headers=None):
    client, _, packet_id, auth, *_ = docs
    return client.post(f"/packets/{packet_id}/documents", files={"file": (filename, body, mime)},
                       headers=auth | {"Idempotency-Key": key or uuid4().hex} | (headers or {}))


def balances(documents):
    with documents.engine.begin() as conn:
        return conn.execute(sa.select(m.storage_buckets.c.reserved_bytes, m.storage_buckets.c.stored_bytes)).all()


def test_pdf_boundary_private_download_integrity_and_metadata(docs):
    body = PDF + b" " * (MAX_BYTES - len(PDF))
    response = send(docs, body)
    assert response.status_code == 201, response.text
    data = response.json()
    assert data["byte_size"] == MAX_BYTES
    assert data["sha256"] == hashlib.sha256(body).hexdigest()
    assert data["parse_status"] == "rejected"
    assert data["parser_version"] == "pypdf-6.21.1/text-v1"
    assert data["parse_error_code"] == "PDF_DAMAGED"
    assert "storage_key" not in data and "owner_id" not in data
    client, documents, packet_id, *_ = docs
    original = client.get(f"/packets/{packet_id}/documents/{data['id']}/original")
    assert original.status_code == 200 and original.content == body
    assert original.headers["cache-control"] == "private, no-store"
    assert original.headers["x-content-type-options"] == "nosniff"
    assert original.headers["content-disposition"].startswith("attachment;")
    assert "location" not in original.headers
    assert balances(documents) == [(0, MAX_BYTES), (0, MAX_BYTES)]
    files = list(documents.store.directory.iterdir())
    assert len(files) == 1 and "Synthetic" not in files[0].name
    assert files[0].stat().st_mode & 0o777 == 0o600
    assert documents.store.directory.stat().st_mode & 0o777 == 0o700


@pytest.mark.parametrize("filename,mime,body,code", [
    ("large.pdf", "application/pdf", b"%PDF-1.7\n" + b" " * MAX_BYTES, "FILE_TOO_LARGE"),
    ("archive.pdf", "application/pdf", b"PK\x03\x04zip", "FILE_UNSUPPORTED"),
    ("image.pdf", "image/png", PDF, "FILE_UNSUPPORTED"),
    ("../escape.pdf", "application/pdf", PDF, "FILE_UNSUPPORTED"),
    ("%2e%2e%2fescape.pdf", "application/pdf", PDF, "FILE_UNSUPPORTED"),
    ("https://example.test/file.pdf", "application/pdf", PDF, "FILE_UNSUPPORTED"),
    ("file.exe", "application/pdf", PDF, "FILE_UNSUPPORTED"),
    ("blank.pdf", "application/pdf", b"", "FILE_UNSUPPORTED"),
])
def test_invalid_files_release_reservation_without_objects(docs, filename, mime, body, code):
    response = send(docs, body, filename=filename, mime=mime)
    assert response.json()["error"]["code"] == code
    assert balances(docs[1]) == [(0, 0), (0, 0)]
    assert not docs[1].store.directory.exists()


def test_declared_length_does_not_bypass_actual_stream_limit(docs):
    response = send(docs, b"%PDF-1.7\n" + b" " * (MAX_BYTES + 20_000), headers={"Content-Length": "1"})
    assert response.status_code == 413
    response = send(docs, headers={"Content-Length": "1"})
    assert response.status_code == 422
    assert balances(docs[1]) == [(0, 0), (0, 0)]


def test_no_length_chunked_input_and_unicode_text_limit(docs):
    client, documents, pid, headers, *_ = docs
    text = "😀" * 10_000
    response = client.post(f"/packets/{pid}/documents", json={"text": text, "filename": "合成.txt"},
                           headers=headers | {"Idempotency-Key": uuid4().hex})
    assert response.status_code == 201, response.text
    original = client.get(f"/packets/{pid}/documents/{response.json()['id']}/original")
    assert original.text == text and response.json()["byte_size"] == 40_000
    invalid = client.post(f"/packets/{pid}/documents", json={"text": text + "a"},
                         headers=headers | {"Idempotency-Key": uuid4().hex})
    assert invalid.status_code == 422
    assert balances(documents) == [(0, 40_000), (0, 40_000)]
    boundary = "synthetic-boundary"
    raw = (f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="s.pdf"\r\n'
           'Content-Type: application/pdf\r\n\r\n').encode() + PDF + f"\r\n--{boundary}--\r\n".encode()
    streamed = client.post(f"/packets/{pid}/documents", content=iter([raw[:50], raw[50:]]),
        headers=headers | {"Idempotency-Key": uuid4().hex, "Content-Type": f"multipart/form-data; boundary={boundary}"})
    assert streamed.status_code == 201, streamed.text


def test_text_page_is_normalized_addressable_and_packet_limit_is_atomic(docs):
    client, documents, pid, headers, *_ = docs
    def upload(text):
        return client.post(f"/packets/{pid}/documents", json={"text": text},
                           headers=headers | {"Idempotency-Key": uuid4().hex})
    first = upload("李😀é\r\nAé")
    assert first.status_code == 201 and first.json()["parse_status"] == "ready"
    did = first.json()["id"]
    page = client.get(f"/packets/{pid}/documents/{did}/pages/1")
    assert page.status_code == 200
    assert page.json()["normalized_text"] == "李😀é\nAé"
    assert page.json()["text_hash"] == hashlib.sha256("李😀é\nAé".encode()).hexdigest()
    assert client.get(f"/packets/{pid}/documents/{did}/pages/2").status_code == 404
    for _ in range(2):
        assert upload("A" * 10_000).json()["parse_status"] == "ready"
    rejected = upload("B" * 10_000)
    assert rejected.status_code == 201
    assert rejected.json()["parse_status"] == "rejected"
    assert rejected.json()["parse_error_code"] == "PACKET_TEXT_LIMIT"
    with documents.engine.begin() as conn:
        assert conn.execute(sa.select(sa.func.count()).select_from(m.document_pages)).scalar_one() == 3
    assert client.get(f"/packets/{pid}/documents/{did}/pages/1").status_code == 200


def test_pdf_page_route_and_unreadable_page_fail_closed(docs):
    client, _, pid, *_ = docs
    root = Path(__file__).resolve().parents[4] / "fixtures/referral-review"
    good = send(docs, (root / "test/test-14/sources/document-2.pdf").read_bytes()).json()
    assert good["parse_status"] == "ready" and good["page_count"] == 2
    assert client.get(f"/packets/{pid}/documents/{good['id']}/pages/2").json()["parse_quality"] == "ready"
    scan = send(docs, (root / "dev/dev-10/sources/document-2.pdf").read_bytes()).json()
    assert scan["parse_status"] == "rejected" and scan["parse_error_page"] == 1
    assert client.get(f"/packets/{pid}/documents/{scan['id']}/pages/1").json()["parse_quality"] == "unreadable"


def test_idempotency_reuses_document_and_rejects_changed_payload(docs):
    first = send(docs, key="repeat-key").json()
    second = send(docs, key="repeat-key")
    assert second.status_code == 201 and second.json() == first
    assert send(docs, PDF + b"changed", key="repeat-key").status_code == 409
    assert balances(docs[1]) == [(0, len(PDF)), (0, len(PDF))]
    assert len(list(docs[1].store.directory.iterdir())) == 1


def test_file_count_and_account_global_quota_include_inflight(docs):
    client, documents, pid, *_ = docs
    token = client.cookies.get(documents.identity.session_cookie)
    uploads = [documents.begin(token, pid, "pdf", f"upload-{i:02}") for i in range(5)]
    assert send(docs).json()["error"]["code"] == "DOCUMENT_LIMIT"
    assert balances(documents) == [(5 * MAX_BYTES, 0), (5 * MAX_BYTES, 0)]
    for upload in uploads:
        documents.abort(upload, object_attempted=False)
    # A different cap can only make persisted buckets more restrictive.
    documents.global_bytes = MAX_BYTES - 1
    assert send(docs).json()["error"]["code"] == "STORAGE_LIMIT"
    assert balances(documents) == [(0, 0), (0, 0)]
    documents.global_bytes = 1024**3
    with documents.engine.begin() as conn:
        conn.execute(m.storage_buckets.update().where(m.storage_buckets.c.scope != "global").values(limit_bytes=MAX_BYTES-1))
    assert send(docs).json()["error"]["code"] == "STORAGE_LIMIT"
    assert balances(documents) == [(0, 0), (0, 0)]


def test_cross_account_unknown_deleted_expired_and_anonymous_are_hidden(docs):
    client, documents, pid, _, clock, transport = docs
    data = send(docs).json()
    url = f"/packets/{pid}/documents/{data['id']}"
    token = client.cookies.get(documents.identity.session_cookie)
    client.cookies.clear()
    assert client.get(url + "/original").status_code == 401
    transport.subject = 67890
    sign_in(client)
    for suffix in ("", "/original", "/pages/1"):
        denied = client.get(url + suffix)
        missing = client.get(f"/packets/{uuid4()}/documents/{uuid4()}" + suffix)
        assert denied.status_code == missing.status_code == 404
        assert denied.json()["error"] == missing.json()["error"]
    client.cookies.clear()
    client.cookies.set(documents.identity.session_cookie, token)
    assert client.get(url).status_code == 200
    with documents.engine.begin() as conn:
        conn.execute(m.packets.update().where(m.packets.c.id == pid).values(deleted_at=clock[0]))
    assert client.get(url + "/original").status_code == 404
    with documents.engine.begin() as conn:
        conn.execute(m.packets.update().where(m.packets.c.id == pid).values(deleted_at=None))
    clock[0] += timedelta(days=7)
    sign_in(client)  # fresh session, expired source remains hidden
    assert client.get(url).status_code == 404


def test_mutation_csrf_and_url_input_are_rejected_before_reservation(docs):
    client, documents, pid, headers, *_ = docs
    assert client.post(f"/packets/{pid}/documents", files={"file": ("s.pdf", PDF, "application/pdf")}).status_code == 403
    assert balances(documents) == []
    assert client.post(f"/packets/{pid}/documents", json={"url": "https://private.invalid"},
        headers=headers | {"Idempotency-Key": uuid4().hex}).status_code == 422
    assert balances(documents) == [(0, 0), (0, 0)]


def test_blob_write_failure_is_compensated_and_can_be_retried_with_new_key(docs, monkeypatch):
    documents = docs[1]
    real_write = documents.store.write
    def fail(*args):
        raise StorageUnavailable()
    monkeypatch.setattr(documents.store, "write", fail)
    assert send(docs).status_code == 503
    assert balances(documents) == [(0, 0), (0, 0)]
    monkeypatch.setattr(documents.store, "write", real_write)
    assert send(docs).status_code == 201


def test_blob_success_db_failure_delete_failure_retains_quota_then_recovers(docs, monkeypatch):
    _, documents, _, _, clock, _ = docs
    real_delete = documents.store.delete
    def fail_commit(*args):
        raise OperationalError("synthetic", None, Exception("sensitive-provider-detail"))
    def fail_delete(*args):
        raise StorageUnavailable()
    monkeypatch.setattr(documents, "_settle", fail_commit)
    monkeypatch.setattr(documents.store, "delete", fail_delete)
    response = send(docs)
    assert response.status_code == 503 and "sensitive" not in response.text
    assert balances(documents) == [(MAX_BYTES, 0), (MAX_BYTES, 0)]
    with documents.engine.begin() as conn:
        reservation = conn.execute(sa.select(m.storage_reservations)).mappings().one()
        assert reservation["state"] == "cleanup_pending"
        assert conn.execute(sa.select(m.cleanup_jobs.c.state)).scalar_one() == "failed"
    monkeypatch.setattr(documents.store, "delete", real_delete)
    clock[0] += timedelta(minutes=2)
    assert documents.cleanup(reservation["document_id"])
    assert not documents.cleanup(reservation["document_id"])
    assert balances(documents) == [(0, 0), (0, 0)]
    assert list(documents.store.directory.iterdir()) == []


def test_crash_after_write_and_ambiguous_commit_are_recoverable(docs, monkeypatch):
    client, documents, pid, _, clock, _ = docs
    token = client.cookies.get(documents.identity.session_cookie)
    upload = documents.begin(token, pid, "pdf", "crashed-request")
    documents.store.write(upload.key, PDF, "application/pdf")
    assert not documents.cleanup(upload.document_id)  # active writer cannot be purged
    clock[0] += timedelta(minutes=11)
    assert documents.cleanup(upload.document_id)
    assert balances(documents) == [(0, 0), (0, 0)]
    real_settle = documents._settle
    def commit_then_disconnect(*args):
        real_settle(*args)
        raise OperationalError("synthetic", None, Exception("commit acknowledgement lost"))
    monkeypatch.setattr(documents, "_settle", commit_then_disconnect)
    assert send(docs, key="committed-request").status_code == 503
    # abort must observe the committed state and preserve the document.
    assert send(docs, key="committed-request").status_code == 201
    assert balances(documents) == [(0, len(PDF)), (0, len(PDF))]


def test_deleted_while_writing_is_compensated(docs, monkeypatch):
    _, documents, pid, _, clock, _ = docs
    write = documents.store.write
    def delete_during_write(*args):
        write(*args)
        with documents.engine.begin() as conn:
            conn.execute(m.packets.update().where(m.packets.c.id == pid).values(deleted_at=clock[0]))
    monkeypatch.setattr(documents.store, "write", delete_during_write)
    assert send(docs).status_code == 404
    assert balances(documents) == [(0, 0), (0, 0)]
    assert list(documents.store.directory.iterdir()) == []


def test_download_rechecks_expiry_and_corruption(docs, monkeypatch):
    client, documents, pid, _, clock, _ = docs
    did = send(docs).json()["id"]
    read = documents.store.read
    monkeypatch.setattr(documents.store, "read", lambda key: b"corrupted")
    assert client.get(f"/packets/{pid}/documents/{did}/original").status_code == 503
    def expire_while_reading(key):
        body = read(key)
        with documents.engine.begin() as conn:
            conn.execute(m.packets.update().where(m.packets.c.id == pid).values(expires_at=clock[0] + timedelta(seconds=1)))
        clock[0] += timedelta(seconds=2)
        return body
    monkeypatch.setattr(documents.store, "read", expire_while_reading)
    assert client.get(f"/packets/{pid}/documents/{did}/original").status_code == 404


def test_local_adapter_never_overwrites_or_follows_untrusted_paths(tmp_path):
    from referral_review.config import ConfigurationError

    store = LocalStore(str(tmp_path / "private"))
    key = object_key(uuid4())
    store.write(key, PDF, "application/pdf")
    with pytest.raises(StorageUnavailable):
        store.write(key, b"replacement", "application/pdf")
    assert store.read(key) == PDF
    for invalid in ("../secret", "/etc/passwd", "https://example.test", "rr-a.bin"):
        for operation in (store.read, store.delete):
            with pytest.raises(StorageUnavailable):
                operation(invalid)
    linked = object_key(uuid4())
    (store.directory / linked).symlink_to(store.directory / key)
    with pytest.raises(StorageUnavailable):
        store.read(linked)
    store.delete(linked)
    assert store.read(key) == PDF
    for directory in (str(Path(__file__).resolve().parents[4] / ".private"), str(tmp_path / "public" / "private")):
        with pytest.raises(ConfigurationError):
            LocalStore(directory)
    store.delete(key)
    store.delete(key)


def test_reconciliation_survives_database_outage_during_compensation(docs, monkeypatch):
    client, documents, pid, _, clock, _ = docs
    token = client.cookies.get(documents.identity.session_cookie)
    upload = documents.begin(token, pid, "pdf", "database-outage")
    documents.store.write(upload.key, PDF, "application/pdf")
    real_buckets = documents._buckets
    def unavailable(*args):
        raise OperationalError("synthetic", None, Exception("database unavailable"))
    monkeypatch.setattr(documents, "_buckets", unavailable)
    documents.abort(upload, object_attempted=True)
    monkeypatch.setattr(documents, "_buckets", real_buckets)
    assert balances(documents) == [(MAX_BYTES, 0), (MAX_BYTES, 0)]
    assert documents.reconcile() == {"selected": 0, "cleaned": 0}
    clock[0] += timedelta(minutes=11)
    assert documents.reconcile() == {"selected": 1, "cleaned": 1}
    assert balances(documents) == [(0, 0), (0, 0)]
    assert list(documents.store.directory.iterdir()) == []
    # A delayed worker cannot publish after its reservation was reclaimed.
    with pytest.raises(Exception) as caught:
        documents.finish(token, upload, "s.pdf", "pdf", PDF)
    assert caught.value.code.value == "STORAGE_UNAVAILABLE"
    assert list(documents.store.directory.iterdir()) == []


def test_multiple_files_fields_and_wrong_packet_never_bypass_limits(docs):
    client, documents, pid, headers, *_ = docs
    response = client.post(f"/packets/{pid}/documents", files=[
        ("file", ("a.pdf", PDF, "application/pdf")), ("file", ("b.pdf", PDF, "application/pdf"))],
        headers=headers | {"Idempotency-Key": uuid4().hex})
    assert response.status_code == 422
    response = client.post(f"/packets/{pid}/documents", files={"file": ("a.pdf", PDF, "application/pdf")},
        data={"owner_id": str(uuid4())}, headers=headers | {"Idempotency-Key": uuid4().hex})
    assert response.status_code == 422
    assert balances(documents) == [(0, 0), (0, 0)]
    did = send(docs).json()["id"]
    assert client.get(f"/packets/{uuid4()}/documents/{did}/original").status_code == 404


def test_configuration_disables_storage_by_default_and_forbids_production_disk(tmp_path):
    from referral_review.config import ConfigurationError, load_settings
    from referral_review.app import create_app

    app = create_app(load_settings({}))
    assert app.state.documents is None
    with pytest.raises(ConfigurationError):
        load_settings({"RR_STORAGE_BACKEND": "local", "RR_ENVIRONMENT": "production",
                       "RR_PRIVATE_STORAGE_DIR": str(tmp_path)})
    with pytest.raises(ConfigurationError):
        load_settings({"RR_STORAGE_BACKEND": "vercel"})
