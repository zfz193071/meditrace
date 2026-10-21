"""Independent spawned processes execute one PostgreSQL-backed run; no provider network."""
import asyncio
import base64
from datetime import timedelta
import multiprocessing
import os
from uuid import uuid4

import pytest
import sqlalchemy as sa

from referral_review.config import Settings
from referral_review.documents.text_rules import text_hash
from referral_review.extraction import FakeAdapter
from referral_review.identity.service import Identity, hashed
from referral_review.persistence import models as m
from referral_review.persistence.database import create_engine
from referral_review.persistence.migrations import HEAD, upgrade
from referral_review.persistence.repository import save_revision
from referral_review.persistence.test_database import isolated_database, test_url as configured_test_url
from referral_review.runs import Runs
from referral_review.schemas import CreateRunInput
from test_persistence import NOW

_BARRIER = None
_CALLS = None


def settings():
    return Settings(RR_MODE="sandbox", RR_SITE_ORIGIN="https://example.test",
        RR_SESSION_ENCRYPTION_KEY=base64.urlsafe_b64encode(b"k" * 32).decode())


def initialize(barrier, calls):
    global _BARRIER, _CALLS
    _BARRIER, _CALLS = barrier, calls


def execute(payload):
    url, schema, token, rid = payload
    engine = create_engine(url, schema=schema)
    identity = Identity(engine, settings(), clock=lambda: NOW)
    class CountingFake(FakeAdapter):
        async def complete(self, request):
            with _CALLS.get_lock():
                _CALLS.value += 1
            await asyncio.sleep(0.2)
            return await super().complete(request)
    runs = Runs(identity, adapter_factory=lambda row, source: CountingFake({"facts": []}))
    try:
        _BARRIER.wait(timeout=20)
        return asyncio.run(runs.execute(token, rid)).state.value
    finally:
        engine.dispose()


def test_processes_dispatch_once_and_commit_one_success():
    if not os.getenv("TEST_DATABASE_URL"):
        pytest.skip("TEST_DATABASE_URL missing; PostgreSQL run execution competition remains unverified")
    with isolated_database(configured_test_url()) as engine:
        owner, packet, document, order = [uuid4() for _ in range(4)]
        token = "t" * 43
        text = "Synthetic referral"
        with engine.begin() as conn:
            upgrade(conn, HEAD)
            schema = conn.execute(sa.text("SELECT current_schema()")).scalar_one()
            conn.execute(m.users.insert().values(id=owner, github_subject=str(owner), display_name="Synthetic"))
            conn.execute(m.sessions.insert().values(user_id=owner, token_hash=hashed(token), csrf_secret="c" * 43,
                                                   expires_at=NOW + timedelta(days=1)))
            conn.execute(m.packets.insert().values(id=packet, owner_id=owner, title="Synthetic", synthetic_ack_at=NOW,
                created_at=NOW, updated_at=NOW, expires_at=NOW + timedelta(days=7)))
            conn.execute(m.documents.insert().values(id=document, packet_id=packet, owner_id=owner, kind="text",
                filename="synthetic.txt", sha256=text_hash(text), storage_key=str(document), byte_size=len(text),
                parse_status="ready", parser_version="text-v1", page_count=1))
            conn.execute(m.document_pages.insert().values(document_id=document, page_number=1, normalized_text=text,
                                                          text_hash=text_hash(text), parse_quality="ready"))
            revision = save_revision(conn, owner_id=owner, packet_id=packet, expected_revision=0,
                                     document_ids=[document], now=NOW)
            conn.execute(m.orders.insert().values(id=order, owner_id=owner, environment="test", price_id="synthetic",
                amount=100, currency="usd", state="paid", paid_at=NOW))
            conn.execute(m.memberships.insert().values(owner_id=owner, source_order_id=order, environment="test",
                valid_from=NOW, valid_until=NOW + timedelta(days=30), granted_units=20))
        runs = Runs(Identity(engine, settings(), clock=lambda: NOW))
        rid = runs.create(token, packet, CreateRunInput(revision_id=revision,
            checklist_version="outpatient-referral-demo@1"), "pg-run-key").id
        ctx = multiprocessing.get_context("spawn")
        calls = ctx.Value("i", 0)
        with ctx.Pool(3, initializer=initialize, initargs=(ctx.Barrier(3), calls)) as pool:
            results = pool.map_async(execute, [(engine.url.render_as_string(hide_password=False), schema, token, rid)] * 3).get(timeout=60)
        assert set(results).issubset({"running", "succeeded"})
        assert "succeeded" in results
        assert calls.value == 1
        assert runs.get(token, rid).state == "succeeded"
        with engine.begin() as conn:
            assert conn.execute(sa.select(sa.func.count()).select_from(m.usage_reservations)).scalar_one() == 1
            assert conn.execute(sa.select(m.memberships.c.consumed_units)).scalar_one() == 1
            assert conn.execute(sa.select(sa.func.count()).select_from(m.findings)).scalar_one() == 7
