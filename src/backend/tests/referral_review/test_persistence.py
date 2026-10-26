"""The same migration/constraint cases run on SQLite and isolated PostgreSQL.

No fallback to DATABASE_URL. PostgreSQL concurrency is in test_pg_concurrency.py.
"""

from datetime import datetime, timedelta, timezone
import hashlib
import os
from uuid import uuid4

from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.runtime.migration import MigrationContext
import pytest
import sqlalchemy as sa

from referral_review.persistence import models as m
from referral_review.persistence.database import create_engine, transaction
from referral_review.persistence.migrations import HEAD, MigrationRequired, configuration, current_revision, require_current_schema, upgrade
from referral_review.persistence.repository import CapacityExceeded, InvalidReference, NotFound, RevisionConflict, add_evidence, advance_review_version, reserve_usage, save_revision
from referral_review.persistence.test_database import Receipt, drop_schema, isolated_database, test_url as configured_test_url
from referral_review.schemas import Evidence

NOW = datetime(2026, 10, 20, tzinfo=timezone.utc)
BUCKETS = ["day:2026-10-20", "month:2026-10"]


@pytest.fixture(params=["sqlite", "postgresql"])
def empty_engine(request, tmp_path):
    if request.param == "postgresql":
        if not os.getenv("TEST_DATABASE_URL"):
            pytest.skip("TEST_DATABASE_URL is not configured; PostgreSQL is NOT verified")
        with isolated_database(configured_test_url()) as engine:
            yield engine
    else:
        engine = create_engine(f"sqlite:///{tmp_path / 'referral.db'}")
        try:
            yield engine
        finally:
            engine.dispose()


@pytest.fixture
def engine(empty_engine):
    with transaction(empty_engine) as connection:
        upgrade(connection, HEAD)
    return empty_engine


def seed(connection, *, units=1, budget=100):
    owner, packet, document, other_document, run, order, member = [uuid4() for _ in range(7)]
    connection.execute(m.users.insert().values(id=owner, github_subject=str(owner), display_name="Synthetic reviewer", created_at=NOW))
    connection.execute(m.packets.insert().values(id=packet, owner_id=owner, title="Synthetic packet", created_at=NOW,
                                                updated_at=NOW, expires_at=NOW + timedelta(days=7)))
    text = "A😀 patient"
    digest = hashlib.sha256(text.encode()).hexdigest()
    for doc in (document, other_document):
        connection.execute(m.documents.insert().values(id=doc, packet_id=packet, owner_id=owner, kind="text", filename="synthetic.txt",
            sha256=digest, storage_key=f"test/{doc}", byte_size=len(text.encode()), parse_status="ready", parser_version="text-v1", created_at=NOW))
        connection.execute(m.document_pages.insert().values(document_id=doc, page_number=1, normalized_text=text, text_hash=digest, parse_quality="ready"))
    revision = save_revision(connection, owner_id=owner, packet_id=packet, expected_revision=0, document_ids=[document], now=NOW)
    connection.execute(m.runs.insert().values(id=run, packet_id=packet, owner_id=owner, revision_id=revision,
        checklist_version="demo@1", mode="fake", state="pending", input_hash="a" * 64, prompt_version="v1", schema_version="0.1.0", created_at=NOW))
    connection.execute(m.orders.insert().values(id=order, owner_id=owner, environment="test", price_id="price_test", amount=100,
        currency="usd", state="paid", created_at=NOW, paid_at=NOW))
    connection.execute(m.memberships.insert().values(id=member, owner_id=owner, source_order_id=order, environment="test",
        valid_from=NOW, valid_until=NOW + timedelta(days=30), granted_units=units))
    for key in BUCKETS:
        if connection.execute(sa.select(m.budget_buckets).where(m.budget_buckets.c.bucket_key == key)).first() is None:
            connection.execute(m.budget_buckets.insert().values(bucket_key=key, limit_microusd=budget))
    return dict(owner=owner, packet=packet, document=document, other_document=other_document, revision=revision, run=run, member=member, order=order, text=text, digest=digest)


def reserve(connection, graph, **changes):
    args = dict(owner_id=graph["owner"], run_id=graph["run"], membership_id=graph["member"], bucket_keys=BUCKETS,
                upper_bound_microusd=60, price_version="synthetic-price-v1", now=NOW)
    return reserve_usage(connection, **(args | changes))


def test_migration_is_additive_idempotent_and_matches_models(empty_engine):
    with transaction(empty_engine) as c:
        c.exec_driver_sql("CREATE TABLE conversations (id INTEGER PRIMARY KEY, title TEXT)")
        c.exec_driver_sql("CREATE TABLE messages (id INTEGER PRIMARY KEY, content TEXT)")
        c.execute(sa.text("INSERT INTO conversations VALUES (1, :value)"), {"value": "Legacy ' ? 😀"})
        c.exec_driver_sql("INSERT INTO messages VALUES (1, 'unchanged')")
        with pytest.raises(MigrationRequired):
            require_current_schema(c)
        upgrade(c, HEAD)
        upgrade(c, HEAD)
        assert require_current_schema(c) == HEAD
        assert c.exec_driver_sql("SELECT * FROM conversations").all() == [(1, "Legacy ' ? 😀")]
        assert c.exec_driver_sql("SELECT * FROM messages").all() == [(1, "unchanged")]
        assert set(m.metadata.tables).issubset(sa.inspect(c).get_table_names())
        context = MigrationContext.configure(c, opts={"version_table": "rr_alembic_version", "include_object":
            lambda obj, name, kind, reflected, compare_to: kind != "table" or name.startswith("rr_")})
        assert compare_metadata(context, m.metadata) == []


def test_migration_failure_rolls_back_ddl_and_legacy_rows(empty_engine, monkeypatch):
    from alembic.operations import Operations
    with transaction(empty_engine) as c:
        c.exec_driver_sql("CREATE TABLE conversations (id INTEGER PRIMARY KEY)")
        c.exec_driver_sql("INSERT INTO conversations VALUES (1)")
    original = Operations.create_table
    count = 0

    def fail(self, *args, **kwargs):
        nonlocal count
        count += 1
        if count == 4:
            raise RuntimeError("injected migration failure")
        return original(self, *args, **kwargs)

    monkeypatch.setattr(Operations, "create_table", fail)
    with pytest.raises(RuntimeError, match="injected"):
        with transaction(empty_engine) as c:
            upgrade(c, HEAD)
    with transaction(empty_engine) as c:
        assert not any(name.startswith("rr_") for name in sa.inspect(c).get_table_names())
        assert c.exec_driver_sql("SELECT id FROM conversations").scalar_one() == 1


def test_application_rollback_never_downgrades_data(engine):
    with transaction(engine) as c:
        graph = seed(c)
        with pytest.raises(RuntimeError, match="additive"):
            command.downgrade(configuration(c), "base")
        assert current_revision(c) == HEAD
        assert c.execute(sa.select(m.packets.c.id)).scalar_one() == graph["packet"]
        with pytest.raises(ValueError, match="reviewed"):
            upgrade(c, "head")


def test_unmanaged_or_future_schema_fails_closed(empty_engine):
    with transaction(empty_engine) as c:
        c.exec_driver_sql("CREATE TABLE rr_unmanaged (id INTEGER)")
        with pytest.raises(MigrationRequired, match="Unversioned"):
            upgrade(c, HEAD)


@pytest.mark.parametrize("table,column,bad", [(m.runs, "state", "invented"), (m.runs, "mode", "live"),
    (m.documents, "parse_status", "invented"), (m.memberships, "reserved_units", 2), (m.orders, "environment", "live")])
def test_invalid_states_and_balances_are_rejected(engine, table, column, bad):
    with transaction(engine) as c:
        seed(c)
    with pytest.raises(sa.exc.IntegrityError):
        with transaction(engine) as c:
            c.execute(table.update().values({column: bad}))


def test_duplicate_events_pending_orders_and_run_reservations_are_rejected(engine):
    with transaction(engine) as c:
        graph = seed(c)
        c.execute(m.billing_events.insert().values(stripe_event_id="evt_test", event_type="test", object_id="obj_test", state="pending", received_at=NOW))
        reserve(c, graph)
    with pytest.raises(sa.exc.IntegrityError):
        with transaction(engine) as c:
            c.execute(m.billing_events.insert().values(stripe_event_id="evt_test", event_type="test", object_id="obj_test", state="pending", received_at=NOW))
    with transaction(engine) as c:
        with pytest.raises(InvalidReference, match="already"):
            reserve(c, graph)
        reservation = dict(c.execute(sa.select(m.usage_reservations)).mappings().one())
        reservation["id"] = uuid4()
    with pytest.raises(sa.exc.IntegrityError):
        with transaction(engine) as c:
            c.execute(m.usage_reservations.insert().values(**reservation))
    with pytest.raises(sa.exc.IntegrityError):
        with transaction(engine) as c:
            for _ in range(2):
                c.execute(m.orders.insert().values(owner_id=graph["owner"], environment="test", price_id="p", amount=100, currency="usd", state="pending"))


def test_active_run_and_membership_order_unique(engine):
    with transaction(engine) as c:
        graph = seed(c)
        run = dict(c.execute(sa.select(m.runs)).mappings().one())
        member = dict(c.execute(sa.select(m.memberships)).mappings().one())
    for table, data in ((m.runs, run), (m.memberships, member)):
        with pytest.raises(sa.exc.IntegrityError):
            with transaction(engine) as c:
                c.execute(table.insert().values(**(data | {"id": uuid4()})))


def test_cross_packet_members_and_wrong_revision_evidence_rejected(engine):
    with transaction(engine) as c:
        first, second = seed(c), seed(c)
    with pytest.raises(sa.exc.IntegrityError):
        with transaction(engine) as c:
            c.execute(m.revision_documents.insert().values(revision_id=first["revision"], document_id=second["document"], packet_id=first["packet"], ordinal=2))
    for doc in (first["other_document"], second["document"]):
        with pytest.raises(sa.exc.IntegrityError):
            with transaction(engine) as c:
                c.execute(m.evidence.insert().values(run_id=first["run"], revision_id=first["revision"], document_id=doc,
                    page_number=1, start_cp=0, end_cp=2, quote="A😀", text_hash=first["digest"]))


def test_revision_cas_ownership_expiry_and_operation_rollback(engine):
    with transaction(engine) as c:
        first, second = seed(c), seed(c)
        with pytest.raises(RevisionConflict):
            save_revision(c, owner_id=first["owner"], packet_id=first["packet"], expected_revision=0, document_ids=[first["document"]], now=NOW)
        with pytest.raises(NotFound):
            save_revision(c, owner_id=second["owner"], packet_id=first["packet"], expected_revision=1, document_ids=[first["document"]], now=NOW)
        with pytest.raises(NotFound):
            save_revision(c, owner_id=first["owner"], packet_id=first["packet"], expected_revision=1, document_ids=[first["document"]], now=NOW + timedelta(days=8))
        with pytest.raises(InvalidReference):
            save_revision(c, owner_id=first["owner"], packet_id=first["packet"], expected_revision=1, document_ids=[second["document"]], now=NOW)
        assert c.execute(sa.select(m.packets.c.current_revision).where(m.packets.c.id == first["packet"])).scalar_one() == 1
        assert c.execute(sa.select(sa.func.count()).select_from(m.revisions)).scalar_one() == 2


def test_evidence_unicode_exact_source_and_run_validation(engine):
    with transaction(engine) as c:
        graph = seed(c)
        evidence = Evidence(id=uuid4(), document_id=graph["document"], page_number=1, start_cp=0, end_cp=2, quote="A😀", text_hash=graph["digest"])
        add_evidence(c, owner_id=graph["owner"], run_id=graph["run"], evidence=evidence, now=NOW)
        with pytest.raises(InvalidReference):
            add_evidence(c, owner_id=graph["owner"], run_id=graph["run"], evidence=evidence.model_copy(update={"quote": "XX"}), now=NOW)
        with pytest.raises(NotFound):
            add_evidence(c, owner_id=uuid4(), run_id=graph["run"], evidence=evidence, now=NOW)


def test_budget_failure_rolls_back_membership_and_all_bucket_reservations(engine):
    with transaction(engine) as c:
        graph = seed(c)
        c.execute(m.budget_buckets.update().where(m.budget_buckets.c.bucket_key == BUCKETS[1]).values(limit_microusd=0))
        with pytest.raises(CapacityExceeded):
            reserve(c, graph)
        assert c.execute(sa.select(m.memberships.c.reserved_units)).scalar_one() == 0
        assert c.execute(sa.select(sa.func.sum(m.budget_buckets.c.reserved_microusd))).scalar_one() == 0
        assert c.execute(sa.select(sa.func.count()).select_from(m.usage_reservations)).scalar_one() == 0


def test_transaction_failure_rolls_back_entire_unit(engine):
    with pytest.raises(RuntimeError):
        with transaction(engine) as c:
            seed(c)
            raise RuntimeError("rollback")
    with transaction(engine) as c:
        assert c.execute(sa.select(sa.func.count()).select_from(m.users)).scalar_one() == 0


def test_naive_dates_rejected_and_utc_roundtrip(engine):
    with transaction(engine) as c:
        graph = seed(c)
        assert c.execute(sa.select(m.packets.c.created_at)).scalar_one() == NOW
    with pytest.raises(sa.exc.StatementError):
        with transaction(engine) as c:
            c.execute(m.packets.update().values(updated_at=NOW.replace(tzinfo=None)))


@pytest.mark.parametrize("table,values", [(m.document_pages, {"normalized_text": "rewritten"}),
    (m.revisions, {"manifest_hash": "b" * 64}), (m.documents, {"sha256": "b" * 64})])
def test_immutable_source_and_version_cannot_be_overwritten(engine, table, values):
    with transaction(engine) as c:
        seed(c)
    with pytest.raises(sa.exc.IntegrityError):
        with transaction(engine) as c:
            c.execute(table.update().values(**values))


def test_schema_version_check_has_no_ddl_side_effect(empty_engine):
    with transaction(empty_engine) as c:
        before = set(sa.inspect(c).get_table_names())
        assert current_revision(c) is None
        with pytest.raises(MigrationRequired):
            require_current_schema(c)
        assert set(sa.inspect(c).get_table_names()) == before


def test_review_version_cas_rejects_stale_review_and_source(engine):
    with transaction(engine) as c:
        graph = seed(c)
        args = dict(owner_id=graph["owner"], packet_id=graph["packet"], expected_revision=1, expected_review_version=0, now=NOW)
        assert advance_review_version(c, **args) == 1
        with pytest.raises(RevisionConflict):
            advance_review_version(c, **args)
        with pytest.raises(RevisionConflict):
            advance_review_version(c, **(args | {"expected_review_version": 1, "expected_revision": 0}))


def test_unknown_schema_version_is_not_automatically_changed(engine):
    with transaction(engine) as c:
        c.exec_driver_sql("UPDATE rr_alembic_version SET version_num='future_version'")
        with pytest.raises(MigrationRequired):
            upgrade(c, HEAD)
        assert current_revision(c) == "future_version"


def test_cross_run_fact_evidence_and_wrong_checklist_rejected(engine):
    with transaction(engine) as c:
        first, second = seed(c), seed(c)
        ref = Evidence(id=uuid4(), document_id=first["document"], page_number=1, start_cp=0, end_cp=2, quote="A😀", text_hash=first["digest"])
        add_evidence(c, owner_id=first["owner"], run_id=first["run"], evidence=ref, now=NOW)
        fact_id = uuid4()
        c.execute(m.facts.insert().values(id=fact_id, run_id=second["run"], field_key="patient.name", value_raw="A😀", assertion_status="stated"))
    with pytest.raises(sa.exc.IntegrityError):
        with transaction(engine) as c:
            c.execute(m.fact_evidence.insert().values(fact_id=fact_id, evidence_id=ref.id, run_id=second["run"]))
    with pytest.raises(sa.exc.IntegrityError):
        with transaction(engine) as c:
            c.execute(m.findings.insert().values(run_id=first["run"], rule_id="C01", checklist_version="wrong", kind="missing", field_keys=["patient.name"], message="synthetic"))


def test_postgres_migration_sql_compiles_without_legacy_or_destructive_ddl():
    import importlib.util
    from io import StringIO
    from alembic.operations import Operations
    from referral_review.persistence.migrations import SCRIPTS
    output = StringIO()
    context = MigrationContext.configure(dialect_name="postgresql", opts={"as_sql": True, "output_buffer": output})
    with Operations.context(context):
        for version in ("rr_0001_create_isolated_referral_domain.py",
                        "rr_0002_document_parse_details.py", "rr_0003_packet_drafts.py", "rr_0004_usage_ledger.py", "rr_0005_review_history.py", "rr_0006_checkout_details.py", "rr_0007_evaluation_ledger.py", "rr_0008_evaluation_slots.py", "rr_0009_evaluation_adjustments.py"):
            spec = importlib.util.spec_from_file_location(version.removesuffix(".py"), SCRIPTS / "versions" / version)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            module.upgrade()
    sql = output.getvalue()
    assert sql.count("CREATE TABLE rr_") == len(m.metadata.tables)
    assert "synthetic_ack_at" in sql and "CREATE TABLE rr_packet_drafts" in sql
    assert "TIMESTAMP WITH TIME ZONE" in sql
    assert "CREATE FUNCTION rr_protect_ready_document" in sql
    assert "DROP TABLE" not in sql and "conversations" not in sql and "messages" not in sql


def test_test_database_has_no_production_fallback(monkeypatch):
    monkeypatch.delenv("TEST_DATABASE_URL", raising=False)
    monkeypatch.setenv("DATABASE_URL", "postgresql://production-secret")
    with pytest.raises(ValueError, match="no production fallback"):
        configured_test_url()


@pytest.mark.parametrize("schema", ["public", "rr_test_bad", "rr_test_" + "a" * 32 + '; DROP SCHEMA public'])
def test_cleanup_refuses_nonowned_names_before_connecting(schema):
    with pytest.raises(ValueError, match="Exact"):
        drop_schema("postgresql://unused", Receipt(schema, "a" * 32, "wrong"), confirm=schema)


def test_cleanup_refuses_wrong_receipt_before_connecting():
    schema = "rr_test_" + "a" * 32
    with pytest.raises(ValueError, match="ownership"):
        drop_schema("postgresql://unused", Receipt(schema, "a" * 32, "wrong"), confirm=schema)


def test_sqlite_memory_database_survives_separate_units_of_work():
    engine = create_engine("sqlite:///:memory:")
    try:
        with transaction(engine) as c:
            upgrade(c, HEAD)
        with transaction(engine) as c:
            assert require_current_schema(c) == HEAD
    finally:
        engine.dispose()


def test_rr_0001_upgrade_preserves_ready_document_and_protects_new_fields(empty_engine):
    owner, packet, document = uuid4(), uuid4(), uuid4()
    with transaction(empty_engine) as c:
        upgrade(c, "rr_0001")
        c.execute(m.users.insert().values(id=owner, github_subject=str(owner),
                                           display_name="Migration user", created_at=NOW))
        c.execute(m.packets.insert().values(id=packet, owner_id=owner, title="Migration packet",
            created_at=NOW, updated_at=NOW, expires_at=NOW + timedelta(days=7)))
        c.execute(m.documents.insert().values(id=document, packet_id=packet, owner_id=owner,
            kind="text", filename="old.txt", sha256="a" * 64, storage_key=f"test/{document}",
            byte_size=1, parse_status="ready", parser_version="text-v1", created_at=NOW))
    with transaction(empty_engine) as c:
        upgrade(c, HEAD)
        row = c.execute(sa.select(m.documents).where(m.documents.c.id == document)).mappings().one()
        assert row["page_count"] is None and row["parse_status"] == "ready"
    with pytest.raises(sa.exc.IntegrityError):
        with transaction(empty_engine) as c:
            c.execute(m.documents.update().where(m.documents.c.id == document).values(page_count=1))


def test_rr_0002_upgrade_preserves_packet_and_adds_navigation_draft(empty_engine):
    owner, packet = uuid4(), uuid4()
    with transaction(empty_engine) as c:
        upgrade(c, "rr_0002")
        c.execute(m.users.insert().values(id=owner, github_subject=str(owner),
                                           display_name="Migration user", created_at=NOW))
        c.execute(m.packets.insert().values(id=packet, owner_id=owner, title="Old packet",
            created_at=NOW, updated_at=NOW, expires_at=NOW + timedelta(days=7)))
    with transaction(empty_engine) as c:
        upgrade(c, HEAD)
        row = c.execute(sa.select(m.packets).where(m.packets.c.id == packet)).mappings().one()
        assert row["title"] == "Old packet" and row["synthetic_ack_at"] is None
        c.execute(m.packet_drafts.insert().values(packet_id=packet, selected_document_ids=[],
            last_location="documents", base_revision=0, draft_version=1, updated_at=NOW))
    with transaction(empty_engine) as c:
        assert c.execute(sa.select(m.packet_drafts.c.draft_version)).scalar_one() == 1


def test_ownership_receipt_recorded_before_database_connection(monkeypatch):
    from referral_review.persistence import test_database
    records = []
    def fail(*args, **kwargs):
        assert len(records) == 1
        raise RuntimeError("simulated connection failure")
    monkeypatch.setattr(test_database, "create_engine", fail)
    with pytest.raises(RuntimeError, match="simulated"):
        test_database.create_schema("postgresql://unused", record=records.append)
    assert records[0].schema.startswith("rr_test_")


@pytest.mark.parametrize("amount", [True, 1.5, "60"])
def test_reservations_reject_noninteger_money_before_writing(amount):
    engine = create_engine("sqlite:///:memory:")
    try:
        with transaction(engine) as c:
            with pytest.raises(ValueError, match="Positive cost"):
                reserve_usage(c, owner_id=uuid4(), run_id=uuid4(), membership_id=uuid4(), bucket_keys=BUCKETS,
                              upper_bound_microusd=amount, price_version="test", now=NOW)
            # No schema exists: rejection took place before a query or write.
            assert sa.inspect(c).get_table_names() == []
    finally:
        engine.dispose()


def test_rr_0003_upgrade_preserves_existing_usage_rows(empty_engine):
    with transaction(empty_engine) as conn:
        upgrade(conn, "rr_0003")
        graph = seed(conn)
        reservation_id = reserve(conn, graph)
        before = dict(conn.execute(sa.select(m.usage_reservations).where(m.usage_reservations.c.id == reservation_id)).mappings().one())
        upgrade(conn, HEAD)
        after = dict(conn.execute(sa.select(m.usage_reservations).where(m.usage_reservations.c.id == reservation_id)).mappings().one())
        assert after == before
        assert conn.execute(sa.select(sa.func.count()).select_from(m.usage_details)).scalar_one() == 0
