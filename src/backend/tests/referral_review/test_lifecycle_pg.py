"""Optional real PostgreSQL cleanup competition; never uses production DATABASE_URL."""
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier
from uuid import uuid4

import sqlalchemy as sa

from referral_review.lifecycle import Lifecycle
from referral_review.packets import Packets
from referral_review.persistence import models as m
from test_identity import auth_client
from test_pg_concurrency import pg
from test_document_pg import storage_pg


def test_two_maintenance_connections_do_not_double_release_or_touch_other_packet(storage_pg, auth_client):
    documents, inputs = storage_pg
    clock = auth_client[2]
    for token, pid, _ in inputs:
        upload = documents.begin(token, pid, "text", uuid4().hex)
        documents.finish(token, upload, "synthetic.txt", "text", b"Synthetic source")
    token, pid, _ = inputs[0]
    Packets(documents.identity).delete(token, pid, uuid4().hex)
    service = Lifecycle(documents.identity, documents)
    service.maintain()
    clock[0] += timedelta(seconds=6)
    barrier = Barrier(2)
    def run():
        barrier.wait(timeout=10)
        return service.maintain()
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(run) for _ in range(2)]
        for future in futures:
            future.result(timeout=45)
    clock[0] += timedelta(seconds=6)
    service.maintain()
    with documents.engine.begin() as conn:
        assert conn.execute(sa.select(m.packets.c.id)).scalars().all() == [inputs[1][1]]
        bucket = conn.execute(sa.select(m.storage_buckets).where(m.storage_buckets.c.scope == "global")).mappings().one()
        assert bucket["reserved_bytes"] == 0 and bucket["stored_bytes"] == len(b"Synthetic source")
        assert conn.execute(sa.select(sa.func.count()).select_from(m.documents)).scalar_one() == 1
