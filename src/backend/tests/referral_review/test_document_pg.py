"""Independent PostgreSQL connections contend for the same storage reservations."""

from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier
from uuid import uuid4

import pytest
import sqlalchemy as sa

from referral_review.documents import Documents
from referral_review.documents.storage import LocalStore, MAX_BYTES
from referral_review.errors import ApiError
from referral_review.identity.service import Identity, hashed
from referral_review.persistence import models as m
from test_identity import auth_client
from test_pg_concurrency import pg


@pytest.fixture
def storage_pg(pg, auth_client, tmp_path):
    _, original_identity, clock, _ = auth_client
    identity = Identity(pg, original_identity.settings, clock=lambda: clock[0])
    documents = Documents(identity, LocalStore(str(tmp_path / "private")))
    inputs = []
    with pg.begin() as conn:
        for index in range(2):
            owner_id, packet_id = uuid4(), uuid4()
            token = ("a" if index == 0 else "b") * 43
            conn.execute(m.users.insert().values(id=owner_id, github_subject=str(index + 1), display_name="Synthetic"))
            conn.execute(m.sessions.insert().values(user_id=owner_id, token_hash=hashed(token),
                csrf_secret="x" * 43, expires_at=clock[0] + timedelta(days=7)))
            conn.execute(m.packets.insert().values(id=packet_id, owner_id=owner_id, title="Synthetic",
                created_at=clock[0], updated_at=clock[0], expires_at=clock[0] + timedelta(days=7)))
            inputs.append((token, packet_id, "pdf"))
    return documents, inputs


def compete(documents, inputs):
    gate = Barrier(2)
    def run(args):
        gate.wait(timeout=10)
        try:
            documents.begin(*args, uuid4().hex)
            return "accepted"
        except ApiError as exc:
            return exc.code.value
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(run, args) for args in inputs]
        return [f.result(timeout=30) for f in futures]


def test_global_storage_limit_serializes_different_accounts(storage_pg):
    documents, inputs = storage_pg
    documents.global_bytes = MAX_BYTES
    assert sorted(compete(documents, inputs)) == ["STORAGE_LIMIT", "accepted"]
    with documents.engine.begin() as conn:
        assert conn.execute(sa.select(m.storage_buckets.c.reserved_bytes).where(
            m.storage_buckets.c.scope == "global")).scalar_one() == MAX_BYTES
        assert conn.execute(sa.select(sa.func.count()).select_from(m.storage_reservations)).scalar_one() == 1


def test_packet_file_count_serializes_concurrent_uploads(storage_pg):
    documents, inputs = storage_pg
    for _ in range(4):
        documents.begin(*inputs[0], uuid4().hex)
    assert sorted(compete(documents, [inputs[0], inputs[0]])) == ["DOCUMENT_LIMIT", "accepted"]
    with documents.engine.begin() as conn:
        assert conn.execute(sa.select(sa.func.count()).select_from(m.storage_reservations)).scalar_one() == 5


def test_account_storage_limit_rolls_back_global_reservation(storage_pg):
    documents, inputs = storage_pg
    # Initialize bucket rows, then release a synthetic upload before lowering capacity.
    upload = documents.begin(*inputs[0], uuid4().hex)
    documents.abort(upload, object_attempted=False)
    with documents.engine.begin() as conn:
        conn.execute(m.storage_buckets.update().where(m.storage_buckets.c.scope == f"user:{upload.owner_id}")
                     .values(limit_bytes=MAX_BYTES))
    assert sorted(compete(documents, [inputs[0], inputs[0]])) == ["STORAGE_LIMIT", "accepted"]
    with documents.engine.begin() as conn:
        assert conn.execute(sa.select(m.storage_buckets.c.reserved_bytes).where(
            m.storage_buckets.c.scope == "global")).scalar_one() == MAX_BYTES
