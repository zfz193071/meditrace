"""Review CAS across independent processes and additive migration on both databases."""
from datetime import timedelta
import multiprocessing
from uuid import uuid4
import sqlalchemy as sa
from referral_review.errors import ApiError
from referral_review.identity.service import Identity, hashed
from referral_review.persistence import models as m
from referral_review.persistence.database import create_engine
from referral_review.persistence.migrations import HEAD, upgrade
from referral_review.reviews import Reviews
from referral_review.reviews.contracts import ConfirmInput, HandoffDraftInput
from test_persistence import empty_engine, engine, seed, NOW
from test_runs_pg import settings

_BARRIER = None


def initialize(barrier):
    global _BARRIER
    _BARRIER = barrier


def edit(payload):
    url, schema, token, pid, revision, operation = payload
    engine = create_engine(url, schema=schema)
    reviews = Reviews(Identity(engine, settings(), clock=lambda: NOW))
    try:
        _BARRIER.wait(timeout=20)
        try:
            if operation == "draft":
                reviews.save_draft(token, pid, HandoffDraftInput(mode="manual", expected_revision=1,
                    expected_review_version=0, fields={"note": "Synthetic review"}), uuid4().hex)
            else:
                reviews.confirm(token, pid, ConfirmInput(mode="manual", revision_id=revision,
                    expected_review_version=0), uuid4().hex)
            return "saved"
        except ApiError as exc:
            return exc.code.value
    finally:
        engine.dispose()


def test_processes_share_draft_and_confirmation_lock(engine):
    token = "t" * 43
    with engine.begin() as conn:
        graph = seed(conn)
        conn.execute(m.sessions.insert().values(user_id=graph["owner"], token_hash=hashed(token),
            csrf_secret="c" * 43, expires_at=NOW + timedelta(days=1)))
        schema = conn.execute(sa.text("SELECT current_schema()")).scalar_one() if engine.dialect.name == "postgresql" else None
    args = (engine.url.render_as_string(hide_password=False), schema, token, graph["packet"], graph["revision"])
    ctx = multiprocessing.get_context("spawn")
    with ctx.Pool(2, initializer=initialize, initargs=(ctx.Barrier(2),)) as pool:
        results = pool.map_async(edit, [(*args, "draft"), (*args, "confirm")]).get(timeout=60)
    assert sorted(results) == ["REVIEW_CONFLICT", "saved"]
    with engine.begin() as conn:
        assert conn.execute(sa.select(m.packets.c.review_version)).scalar_one() == 1
        assert conn.execute(sa.select(sa.func.count()).select_from(m.review_events)).scalar_one() == 1


def test_upgrade_preserves_existing_review_snapshot(empty_engine):
    with empty_engine.begin() as conn:
        upgrade(conn, "rr_0004")
        graph = seed(conn)
        sid = uuid4()
        conn.execute(m.review_snapshots.insert().values(id=sid, packet_id=graph["packet"], revision_id=graph["revision"],
            run_id=None, review_version=0, confirmed_by=graph["owner"], confirmed_at=NOW,
            payload={"synthetic": "retained"}, payload_hash="a" * 64, has_unresolved=False))
        upgrade(conn, HEAD)
        assert conn.execute(sa.select(m.review_snapshots.c.payload).where(m.review_snapshots.c.id == sid)).scalar_one() == {"synthetic": "retained"}
        assert conn.execute(sa.select(sa.func.count()).select_from(m.review_events)).scalar_one() == 0
