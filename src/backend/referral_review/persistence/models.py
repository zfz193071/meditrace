"""SQLAlchemy Core domain models, isolated from legacy metadata.

Associations are normalized so PostgreSQL can enforce run/revision/packet
membership instead of trusting UUID arrays inside JSON. JSON is reserved for
non-relational payloads. Public operations live in repository.py, not per-table CRUD.
"""

from datetime import datetime, timezone
from uuid import uuid4

import sqlalchemy as sa
from sqlalchemy.types import TypeDecorator


def utcnow():
    return datetime.now(timezone.utc)


class UTCDateTime(TypeDecorator):
    impl = sa.DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Timezone-aware datetime required")
        return value.astimezone(timezone.utc)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        if value.tzinfo is None:  # SQLite stores UTC without a timezone marker.
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)


metadata = sa.MetaData(naming_convention={
    "ix": "ix_%(table_name)s_%(column_0_name)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_N_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
})


def uid(name="id", *, primary=False, nullable=False, reference=None):
    args = [sa.ForeignKey(reference)] if reference else []
    return sa.Column(name, sa.Uuid(), *args, primary_key=primary, nullable=nullable,
                     default=uuid4 if primary and name == "id" else None)


def timestamp(name, *, nullable=False, created=False):
    return sa.Column(name, UTCDateTime(), nullable=nullable, default=utcnow if created else None)


def state(column, values):
    return sa.CheckConstraint(f"{column} IN ({', '.join(repr(v) for v in values.split())})", name=column)


def fk(local, remote):
    return sa.ForeignKeyConstraint(local.split(), remote.split())


users = sa.Table("rr_users", metadata,
    uid(primary=True), sa.Column("github_subject", sa.String(128), nullable=False, unique=True),
    sa.Column("display_name", sa.String(200), nullable=False), timestamp("created_at", created=True),
    timestamp("disabled_at", nullable=True))

sessions = sa.Table("rr_sessions", metadata,
    uid(primary=True), uid("user_id", reference="rr_users.id"),
    sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
    sa.Column("csrf_secret", sa.String(128), nullable=False), timestamp("expires_at"),
    timestamp("revoked_at", nullable=True), sa.Index("ix_rr_sessions_user_expiry", "user_id", "expires_at"))

oauth_states = sa.Table("rr_oauth_states", metadata,
    sa.Column("state_hash", sa.String(64), primary_key=True),
    sa.Column("browser_nonce_hash", sa.String(64), nullable=False),
    sa.Column("encrypted_verifier", sa.Text, nullable=False), sa.Column("return_path", sa.Text, nullable=False),
    timestamp("expires_at"), timestamp("consumed_at", nullable=True), sa.Index("ix_rr_oauth_expiry", "expires_at"))

packets = sa.Table("rr_packets", metadata,
    uid(primary=True), uid("owner_id", reference="rr_users.id"), sa.Column("title", sa.String(200), nullable=False),
    timestamp("synthetic_ack_at", nullable=True),
    sa.Column("current_revision", sa.Integer, nullable=False, server_default="0"),
    sa.Column("review_version", sa.Integer, nullable=False, server_default="0"),
    timestamp("created_at", created=True), timestamp("updated_at", created=True), timestamp("expires_at"),
    timestamp("deleted_at", nullable=True), sa.UniqueConstraint("id", "owner_id"),
    sa.CheckConstraint("current_revision >= 0 AND review_version >= 0", name="versions"),
    sa.CheckConstraint("expires_at > created_at", name="expiry"),
    sa.Index("ix_rr_packets_owner_created_id", "owner_id", "created_at", "id"),
    sa.Index("ix_rr_packets_expiry", "expires_at", "deleted_at"))

packet_drafts = sa.Table("rr_packet_drafts", metadata,
    uid("packet_id", primary=True, reference="rr_packets.id"),
    sa.Column("selected_document_ids", sa.JSON, nullable=False),
    sa.Column("last_location", sa.String(32), nullable=False),
    sa.Column("base_revision", sa.Integer, nullable=False),
    sa.Column("draft_version", sa.Integer, nullable=False),
    timestamp("updated_at", created=True),
    sa.CheckConstraint("base_revision >= 0 AND draft_version >= 0", name="versions"),
    state("last_location", "documents review handoff"))

documents = sa.Table("rr_documents", metadata,
    uid(primary=True), uid("packet_id"), uid("owner_id"),
    sa.Column("kind", sa.String(20), nullable=False), sa.Column("filename", sa.String(255), nullable=False),
    sa.Column("sha256", sa.String(64), nullable=False), sa.Column("storage_key", sa.Text, nullable=False, unique=True),
    sa.Column("byte_size", sa.BigInteger, nullable=False), sa.Column("parse_status", sa.String(20), nullable=False),
    sa.Column("parser_version", sa.String(80), nullable=True),
    sa.Column("page_count", sa.Integer, nullable=True),
    sa.Column("parse_error_code", sa.String(40), nullable=True),
    sa.Column("parse_error_page", sa.Integer, nullable=True), timestamp("created_at", created=True),
    timestamp("deleted_at", nullable=True),
    fk("packet_id owner_id", "rr_packets.id rr_packets.owner_id"),
    sa.UniqueConstraint("id", "packet_id"), sa.UniqueConstraint("id", "owner_id"),
    sa.CheckConstraint("byte_size >= 0", name="size"),
    sa.CheckConstraint("page_count IS NULL OR page_count >= 1", name="page_count"),
    sa.CheckConstraint("parse_error_page IS NULL OR parse_error_page >= 1", name="parse_error_page"),
    state("kind", "pdf text"),
    state("parse_status", "uploading parsing ready rejected failed"),
    sa.Index("ix_rr_documents_packet_created", "packet_id", "created_at"))

document_pages = sa.Table("rr_document_pages", metadata,
    uid("document_id", primary=True, reference="rr_documents.id"),
    sa.Column("page_number", sa.Integer, primary_key=True), sa.Column("normalized_text", sa.Text, nullable=False),
    sa.Column("text_hash", sa.String(64), nullable=False), sa.Column("parse_quality", sa.String(20), nullable=False),
    sa.UniqueConstraint("document_id", "page_number", "text_hash"),
    sa.CheckConstraint("page_number >= 1", name="page"), state("parse_quality", "ready empty unreadable failed"))

revisions = sa.Table("rr_revisions", metadata,
    uid(primary=True), uid("packet_id", reference="rr_packets.id"),
    sa.Column("revision_number", sa.Integer, nullable=False), sa.Column("manifest_hash", sa.String(64), nullable=False),
    timestamp("created_at", created=True), sa.UniqueConstraint("packet_id", "revision_number"),
    sa.UniqueConstraint("id", "packet_id"), sa.CheckConstraint("revision_number > 0", name="number"))

revision_documents = sa.Table("rr_revision_documents", metadata,
    uid("revision_id", primary=True), uid("document_id", primary=True), uid("packet_id"),
    sa.Column("ordinal", sa.Integer, nullable=False),
    fk("revision_id packet_id", "rr_revisions.id rr_revisions.packet_id"),
    fk("document_id packet_id", "rr_documents.id rr_documents.packet_id"),
    sa.UniqueConstraint("revision_id", "ordinal"), sa.CheckConstraint("ordinal >= 0", name="ordinal"),
    sa.Index("ix_rr_revision_documents_document", "document_id"))

runs = sa.Table("rr_runs", metadata,
    uid(primary=True), uid("packet_id"), uid("owner_id"), uid("revision_id"),
    sa.Column("checklist_version", sa.String(100), nullable=False), sa.Column("mode", sa.String(20), nullable=False),
    sa.Column("state", sa.String(24), nullable=False), sa.Column("input_hash", sa.String(64), nullable=False),
    sa.Column("prompt_version", sa.String(100), nullable=False), sa.Column("schema_version", sa.String(100), nullable=False),
    sa.Column("model_requested", sa.String(100)), sa.Column("model_reported", sa.String(100)),
    timestamp("lease_expires_at", nullable=True), timestamp("provider_dispatched_at", nullable=True),
    sa.Column("provider_request_id", sa.String(200)), sa.Column("usage", sa.JSON),
    sa.Column("error_code", sa.String(80)), timestamp("created_at", created=True), timestamp("finished_at", nullable=True),
    fk("packet_id owner_id", "rr_packets.id rr_packets.owner_id"),
    fk("revision_id packet_id", "rr_revisions.id rr_revisions.packet_id"),
    sa.UniqueConstraint("id", "revision_id"), sa.UniqueConstraint("id", "owner_id"),
    sa.UniqueConstraint("id", "checklist_version"),
    sa.UniqueConstraint("id", "packet_id", "revision_id"),
    state("mode", "precomputed fake replay real"), state("state", "pending running succeeded failed outcome_unknown cancelled"),
    sa.Index("ix_rr_runs_packet_created_id", "packet_id", "created_at", "id"),
    sa.Index("ix_rr_runs_state_lease", "state", "lease_expires_at"))
sa.Index("uq_rr_runs_active_input", runs.c.packet_id, runs.c.revision_id, runs.c.checklist_version,
         runs.c.mode, runs.c.input_hash, unique=True,
         postgresql_where=runs.c.state.in_(["pending", "running"]), sqlite_where=runs.c.state.in_(["pending", "running"]))

evidence = sa.Table("rr_evidence", metadata,
    uid(primary=True), uid("run_id"), uid("revision_id"), uid("document_id"),
    sa.Column("page_number", sa.Integer, nullable=False), sa.Column("start_cp", sa.Integer, nullable=False),
    sa.Column("end_cp", sa.Integer, nullable=False), sa.Column("quote", sa.Text, nullable=False),
    sa.Column("text_hash", sa.String(64), nullable=False),
    fk("run_id revision_id", "rr_runs.id rr_runs.revision_id"),
    fk("revision_id document_id", "rr_revision_documents.revision_id rr_revision_documents.document_id"),
    fk("document_id page_number text_hash", "rr_document_pages.document_id rr_document_pages.page_number rr_document_pages.text_hash"),
    sa.UniqueConstraint("id", "run_id"),
    sa.CheckConstraint("start_cp >= 0 AND end_cp > start_cp AND end_cp - start_cp = length(quote)", name="span"),
    sa.Index("ix_rr_evidence_run", "run_id"))

facts = sa.Table("rr_facts", metadata,
    uid(primary=True), uid("run_id", reference="rr_runs.id"), sa.Column("field_key", sa.String(60), nullable=False),
    sa.Column("value_raw", sa.Text, nullable=False), sa.Column("value_normalized", sa.Text),
    sa.Column("assertion_status", sa.String(24), nullable=False), sa.Column("temporal_context", sa.Text),
    sa.UniqueConstraint("id", "run_id"), state("assertion_status", "stated explicitly_none unknown"),
    state("field_key", "patient.name patient.dob referrer.name referrer.contact recipient referral.reason medications allergies attachment_reference report.description"),
    sa.CheckConstraint("length(value_raw) > 0", name="value"), sa.Index("ix_rr_facts_run_field", "run_id", "field_key"))

fact_evidence = sa.Table("rr_fact_evidence", metadata,
    uid("fact_id", primary=True), uid("evidence_id", primary=True), uid("run_id"),
    fk("fact_id run_id", "rr_facts.id rr_facts.run_id"), fk("evidence_id run_id", "rr_evidence.id rr_evidence.run_id"))

findings = sa.Table("rr_findings", metadata,
    uid(primary=True), uid("run_id", reference="rr_runs.id"), sa.Column("rule_id", sa.String(3), nullable=False),
    sa.Column("checklist_version", sa.String(100), nullable=False), sa.Column("kind", sa.String(32), nullable=False),
    sa.Column("field_keys", sa.JSON, nullable=False), sa.Column("message", sa.Text, nullable=False),
    fk("run_id checklist_version", "rr_runs.id rr_runs.checklist_version"),
    sa.UniqueConstraint("id", "run_id"), state("rule_id", "C01 C02 C03 C04 C05 C06 C07 C08"),
    state("kind", "missing unknown identity_mismatch statement_difference attachment_unmatched parse_quality"),
    sa.Index("ix_rr_findings_run", "run_id"))

finding_facts = sa.Table("rr_finding_facts", metadata,
    uid("finding_id", primary=True), uid("fact_id", primary=True), uid("run_id"),
    fk("finding_id run_id", "rr_findings.id rr_findings.run_id"), fk("fact_id run_id", "rr_facts.id rr_facts.run_id"))
finding_evidence = sa.Table("rr_finding_evidence", metadata,
    uid("finding_id", primary=True), uid("evidence_id", primary=True), uid("run_id"),
    fk("finding_id run_id", "rr_findings.id rr_findings.run_id"), fk("evidence_id run_id", "rr_evidence.id rr_evidence.run_id"))
finding_documents = sa.Table("rr_finding_documents", metadata,
    uid("finding_id", primary=True), uid("document_id", primary=True), uid("run_id"), uid("revision_id"),
    fk("finding_id run_id", "rr_findings.id rr_findings.run_id"),
    fk("run_id revision_id", "rr_runs.id rr_runs.revision_id"),
    fk("revision_id document_id", "rr_revision_documents.revision_id rr_revision_documents.document_id"))

resolutions = sa.Table("rr_resolutions", metadata,
    uid(primary=True), uid("finding_id"), uid("run_id"), uid("actor_id"),
    sa.Column("action", sa.String(20), nullable=False), sa.Column("reason", sa.Text, nullable=False),
    sa.Column("corrected_value", sa.Text), sa.Column("review_version", sa.Integer, nullable=False),
    timestamp("created_at", created=True), sa.UniqueConstraint("id", "run_id"),
    fk("finding_id run_id", "rr_findings.id rr_findings.run_id"),
    fk("run_id actor_id", "rr_runs.id rr_runs.owner_id"),
    state("action", "resolve dismiss defer reopen"), sa.CheckConstraint("review_version > 0", name="version"),
    sa.CheckConstraint("action NOT IN ('dismiss', 'defer') OR length(trim(reason)) > 0", name="reason"),
    sa.Index("ix_rr_resolutions_finding_version", "finding_id", "review_version"))
resolution_evidence = sa.Table("rr_resolution_evidence", metadata,
    uid("resolution_id", primary=True), uid("evidence_id", primary=True), uid("run_id"),
    fk("resolution_id run_id", "rr_resolutions.id rr_resolutions.run_id"),
    fk("evidence_id run_id", "rr_evidence.id rr_evidence.run_id"))

handoff_drafts = sa.Table("rr_handoff_drafts", metadata,
    uid("packet_id", primary=True), uid("revision_id"), uid("run_id", nullable=True),
    sa.Column("content", sa.JSON, nullable=False), sa.Column("review_version", sa.Integer, nullable=False),
    fk("revision_id packet_id", "rr_revisions.id rr_revisions.packet_id"),
    fk("run_id packet_id revision_id", "rr_runs.id rr_runs.packet_id rr_runs.revision_id"),
    sa.CheckConstraint("review_version >= 0", name="version"))
review_snapshots = sa.Table("rr_review_snapshots", metadata,
    uid(primary=True), uid("packet_id"), uid("revision_id"), uid("run_id", nullable=True),
    sa.Column("review_version", sa.Integer, nullable=False), uid("confirmed_by"), timestamp("confirmed_at", created=True),
    sa.Column("payload", sa.JSON, nullable=False), sa.Column("payload_hash", sa.String(64), nullable=False),
    sa.Column("has_unresolved", sa.Boolean, nullable=False),
    fk("revision_id packet_id", "rr_revisions.id rr_revisions.packet_id"),
    fk("run_id packet_id revision_id", "rr_runs.id rr_runs.packet_id rr_runs.revision_id"),
    fk("packet_id confirmed_by", "rr_packets.id rr_packets.owner_id"),
    sa.UniqueConstraint("packet_id", "review_version"), sa.CheckConstraint("review_version >= 0", name="version"),
    sa.Index("ix_rr_snapshots_packet_created_id", "packet_id", "confirmed_at", "id"))

orders = sa.Table("rr_orders", metadata,
    uid(primary=True), uid("owner_id", nullable=True, reference="rr_users.id"),
    sa.Column("environment", sa.String(10), nullable=False),
    sa.Column("checkout_session_id", sa.String(200), unique=True), sa.Column("payment_intent_id", sa.String(200), unique=True),
    sa.Column("price_id", sa.String(200), nullable=False), sa.Column("amount", sa.BigInteger, nullable=False),
    sa.Column("currency", sa.String(3), nullable=False), sa.Column("state", sa.String(20), nullable=False),
    timestamp("created_at", created=True), timestamp("paid_at", nullable=True),
    sa.UniqueConstraint("id", "owner_id", "environment"), state("environment", "test"),
    state("state", "pending paid expired failed refunded revoked"), sa.CheckConstraint("amount > 0", name="amount"),
    sa.Index("ix_rr_orders_owner_created_id", "owner_id", "created_at", "id"))
sa.Index("uq_rr_orders_pending_owner", orders.c.owner_id, orders.c.environment, unique=True,
         postgresql_where=orders.c.state == "pending", sqlite_where=orders.c.state == "pending")

memberships = sa.Table("rr_memberships", metadata,
    uid(primary=True), uid("owner_id", nullable=True, reference="rr_users.id"), uid("source_order_id"),
    sa.Column("environment", sa.String(10), nullable=False), timestamp("valid_from"), timestamp("valid_until"),
    sa.Column("granted_units", sa.Integer, nullable=False), sa.Column("reserved_units", sa.Integer, nullable=False, server_default="0"),
    sa.Column("consumed_units", sa.Integer, nullable=False, server_default="0"), timestamp("revoked_at", nullable=True),
    # Keep a direct order FK even after anonymization makes the composite nullable.
    sa.ForeignKeyConstraint(["source_order_id"], ["rr_orders.id"]),
    fk("source_order_id owner_id environment", "rr_orders.id rr_orders.owner_id rr_orders.environment"),
    sa.UniqueConstraint("source_order_id"), sa.UniqueConstraint("id", "owner_id"), state("environment", "test"),
    sa.CheckConstraint("valid_until > valid_from", name="validity"),
    sa.CheckConstraint("granted_units >= 0 AND reserved_units >= 0 AND consumed_units >= 0 AND reserved_units + consumed_units <= granted_units", name="units"),
    sa.Index("ix_rr_memberships_owner_until", "owner_id", "valid_until"))

billing_events = sa.Table("rr_billing_events", metadata,
    sa.Column("stripe_event_id", sa.String(200), primary_key=True), sa.Column("event_type", sa.String(100), nullable=False),
    sa.Column("object_id", sa.String(200), nullable=False), sa.Column("state", sa.String(20), nullable=False),
    timestamp("received_at", created=True), timestamp("processed_at", nullable=True),
    state("state", "pending processed rejected failed"), sa.Index("ix_rr_billing_events_state_received", "state", "received_at"))

budget_buckets = sa.Table("rr_budget_buckets", metadata,
    sa.Column("bucket_key", sa.String(80), primary_key=True), sa.Column("limit_microusd", sa.BigInteger, nullable=False),
    sa.Column("reserved_microusd", sa.BigInteger, nullable=False, server_default="0"),
    sa.Column("spent_microusd", sa.BigInteger, nullable=False, server_default="0"),
    # Actual provider spend may exceed the estimate: retain it, block new reserves.
    sa.CheckConstraint("limit_microusd >= 0 AND reserved_microusd >= 0 AND spent_microusd >= 0", name="nonnegative"))

usage_reservations = sa.Table("rr_usage_reservations", metadata,
    uid(primary=True), uid("run_id", nullable=True, reference="rr_runs.id"),
    uid("membership_id", reference="rr_memberships.id"), uid("owner_id", nullable=True),
    sa.Column("units", sa.Integer, nullable=False), sa.Column("cost_upper_bound_microusd", sa.BigInteger, nullable=False),
    sa.Column("actual_microusd", sa.BigInteger), sa.Column("state", sa.String(24), nullable=False),
    sa.Column("price_version", sa.String(100), nullable=False), timestamp("created_at", created=True),
    sa.UniqueConstraint("run_id"), fk("run_id owner_id", "rr_runs.id rr_runs.owner_id"),
    fk("membership_id owner_id", "rr_memberships.id rr_memberships.owner_id"),
    sa.CheckConstraint("units > 0 AND cost_upper_bound_microusd >= 0 AND (actual_microusd IS NULL OR actual_microusd >= 0)", name="amounts"),
    state("state", "reserved settled released retained_unknown estimated_spent"),
    sa.CheckConstraint("state NOT IN ('reserved', 'retained_unknown') OR (run_id IS NOT NULL AND owner_id IS NOT NULL)", name="active_owner"))
usage_buckets = sa.Table("rr_usage_buckets", metadata,
    uid("reservation_id", primary=True, reference="rr_usage_reservations.id"),
    sa.Column("bucket_key", sa.String(80), sa.ForeignKey("rr_budget_buckets.bucket_key"), primary_key=True))

concurrency_slots = sa.Table("rr_concurrency_slots", metadata,
    sa.Column("scope", sa.String(100), primary_key=True), sa.Column("slot_number", sa.Integer, primary_key=True),
    uid("run_id", nullable=True, reference="rr_runs.id"), timestamp("lease_expires_at", nullable=True),
    sa.CheckConstraint("slot_number >= 0", name="slot"),
    sa.CheckConstraint("(run_id IS NULL AND lease_expires_at IS NULL) OR (run_id IS NOT NULL AND lease_expires_at IS NOT NULL)", name="lease"),
    sa.UniqueConstraint("scope", "run_id"), sa.Index("ix_rr_slots_expiry", "lease_expires_at"))

storage_buckets = sa.Table("rr_storage_buckets", metadata,
    sa.Column("scope", sa.String(100), primary_key=True), sa.Column("limit_bytes", sa.BigInteger, nullable=False),
    sa.Column("reserved_bytes", sa.BigInteger, nullable=False, server_default="0"),
    sa.Column("stored_bytes", sa.BigInteger, nullable=False, server_default="0"),
    sa.CheckConstraint("limit_bytes >= 0 AND reserved_bytes >= 0 AND stored_bytes >= 0 AND reserved_bytes + stored_bytes <= limit_bytes", name="capacity"))
storage_reservations = sa.Table("rr_storage_reservations", metadata,
    uid(primary=True), uid("owner_id", reference="rr_users.id"), uid("document_id", reference="rr_documents.id"),
    sa.Column("reserved_bytes", sa.BigInteger, nullable=False), sa.Column("state", sa.String(24), nullable=False), timestamp("expires_at"),
    fk("document_id owner_id", "rr_documents.id rr_documents.owner_id"), sa.UniqueConstraint("document_id"),
    state("state", "reserved stored released cleanup_pending"), sa.CheckConstraint("reserved_bytes >= 0", name="bytes"),
    sa.Index("ix_rr_storage_owner_state", "owner_id", "state"), sa.Index("ix_rr_storage_expiry", "state", "expires_at"))

rate_limit_buckets = sa.Table("rr_rate_limit_buckets", metadata,
    sa.Column("scope", sa.String(100), nullable=False), sa.Column("action", sa.String(80), nullable=False),
    timestamp("window_start"), sa.Column("count", sa.Integer, nullable=False, server_default="0"),
    sa.PrimaryKeyConstraint("scope", "action", "window_start"), sa.CheckConstraint("count >= 0", name="count"),
    sa.Index("ix_rr_rate_window", "window_start"))

idempotency = sa.Table("rr_idempotency", metadata,
    uid("owner_id", primary=True, reference="rr_users.id"), sa.Column("operation", sa.String(80), primary_key=True),
    sa.Column("key", sa.String(200), primary_key=True), sa.Column("request_hash", sa.String(64), nullable=False),
    uid("resource_id"), timestamp("expires_at"), sa.Index("ix_rr_idempotency_expiry", "expires_at"))

audit_events = sa.Table("rr_audit_events", metadata,
    uid(primary=True), uid("actor_id", nullable=True, reference="rr_users.id"),
    uid("packet_id", nullable=True, reference="rr_packets.id"), sa.Column("action", sa.String(80), nullable=False),
    uid("revision_id", nullable=True, reference="rr_revisions.id"), uid("run_id", nullable=True, reference="rr_runs.id"),
    uid("request_id"), timestamp("created_at", created=True), sa.Index("ix_rr_audit_created", "created_at"),
    sa.Index("ix_rr_audit_packet_created", "packet_id", "created_at"))

cleanup_jobs = sa.Table("rr_cleanup_jobs", metadata,
    uid(primary=True), sa.Column("object_key", sa.Text, nullable=True), uid("entity_id", nullable=True),
    sa.Column("kind", sa.String(20), nullable=False), sa.Column("state", sa.String(20), nullable=False),
    sa.Column("attempt_count", sa.Integer, nullable=False, server_default="0"), timestamp("next_attempt_at"),
    sa.Column("last_error_code", sa.String(80)),
    state("kind", "object packet account orphan audit billing"), state("state", "pending running succeeded failed"),
    sa.CheckConstraint("attempt_count >= 0", name="attempts"),
    sa.CheckConstraint("object_key IS NOT NULL OR entity_id IS NOT NULL", name="target"),
    sa.Index("ix_rr_cleanup_due", "state", "next_attempt_at"))

# Frozen reservation pricing and reconciliation metadata; no provider/source payloads.
usage_details = sa.Table("rr_usage_details", metadata,
    uid("reservation_id", primary=True, reference="rr_usage_reservations.id"),
    sa.Column("mode", sa.String(10), nullable=False), sa.Column("model", sa.String(200), nullable=False),
    sa.Column("input_bound", sa.Integer, nullable=False), sa.Column("output_limit", sa.Integer, nullable=False),
    sa.Column("input_price", sa.BigInteger, nullable=False), sa.Column("output_price", sa.BigInteger, nullable=False),
    sa.Column("outcome", sa.String(16)), timestamp("unknown_at", nullable=True), timestamp("settled_at", nullable=True),
    sa.Column("settlement_hash", sa.String(64)),
    state("mode", "fake real"),
    sa.CheckConstraint("input_bound > 0 AND input_bound <= 16000 AND output_limit > 0 AND output_limit <= 6000 AND input_price >= 0 AND output_price >= 0", name="limits"))
usage_controls = sa.Table("rr_usage_controls", metadata,
    sa.Column("key", sa.String(30), primary_key=True),
    sa.Column("halted", sa.Boolean, nullable=False, server_default=sa.false()),
    sa.Column("reason", sa.String(80)))
usage_adjustments = sa.Table("rr_usage_adjustments", metadata,
    uid(primary=True), uid("reservation_id", reference="rr_usage_reservations.id"),
    sa.Column("adjustment_key", sa.String(100), nullable=False),
    sa.Column("actual_microusd", sa.BigInteger, nullable=False),
    sa.Column("delta_microusd", sa.BigInteger, nullable=False), timestamp("created_at", created=True),
    sa.UniqueConstraint("reservation_id", "adjustment_key"),
    sa.CheckConstraint("actual_microusd >= 0", name="amount"))

# Internal synthetic evaluation accounting. No patient text, credentials or user
# links; evaluation caps are independent of purchased workspace membership units.
evaluation_batches = sa.Table("rr_evaluation_batches", metadata,
    uid(primary=True), sa.Column("plan_hash", sa.String(64), nullable=False),
    sa.Column("cap_microusd", sa.BigInteger, nullable=False),
    sa.Column("reserved_microusd", sa.BigInteger, nullable=False, server_default="0"),
    sa.Column("spent_microusd", sa.BigInteger, nullable=False, server_default="0"),
    sa.Column("model", sa.String(200), nullable=False), sa.Column("price_version", sa.String(100), nullable=False),
    sa.Column("input_price", sa.BigInteger, nullable=False), sa.Column("output_price", sa.BigInteger, nullable=False),
    timestamp("created_at", created=True),
    sa.CheckConstraint("cap_microusd > 0 AND reserved_microusd >= 0 AND spent_microusd >= 0 AND input_price > 0 AND output_price > 0", name="amounts"))
evaluation_attempts = sa.Table("rr_evaluation_attempts", metadata,
    uid(primary=True), uid("batch_id", reference="rr_evaluation_batches.id"),
    sa.Column("sample_hash", sa.String(64), nullable=False),
    sa.Column("input_bound", sa.Integer, nullable=False), sa.Column("output_limit", sa.Integer, nullable=False),
    sa.Column("upper_microusd", sa.BigInteger, nullable=False), sa.Column("actual_microusd", sa.BigInteger),
    sa.Column("state", sa.String(24), nullable=False), sa.Column("outcome", sa.String(16)),
    sa.Column("prompt_tokens", sa.BigInteger), sa.Column("completion_tokens", sa.BigInteger),
    timestamp("created_at", created=True), timestamp("lease_expires_at"),
    timestamp("dispatched_at", nullable=True), timestamp("unknown_at", nullable=True), timestamp("settled_at", nullable=True),
    sa.Column("settlement_hash", sa.String(64)),
    sa.UniqueConstraint("batch_id", "sample_hash"),
    state("state", "reserved dispatched retained_unknown settled released estimated_spent"),
    sa.CheckConstraint("input_bound > 0 AND input_bound <= 16000 AND output_limit > 0 AND output_limit <= 6000 AND upper_microusd > 0 AND (actual_microusd IS NULL OR actual_microusd >= 0)", name="amounts"),
    sa.CheckConstraint("(prompt_tokens IS NULL AND completion_tokens IS NULL) OR (prompt_tokens >= 0 AND completion_tokens >= 0 AND prompt_tokens IS NOT NULL AND completion_tokens IS NOT NULL)", name="tokens"),
    sa.Index("ix_rr_evaluation_recovery", "state", "lease_expires_at"))
evaluation_buckets = sa.Table("rr_evaluation_buckets", metadata,
    uid("attempt_id", primary=True, reference="rr_evaluation_attempts.id"),
    sa.Column("bucket_key", sa.String(80), sa.ForeignKey("rr_budget_buckets.bucket_key"), primary_key=True))

# Durable reviewer history, including every replaced handoff draft.
review_events = sa.Table("rr_review_events", metadata,
    uid(primary=True), uid("packet_id"), uid("revision_id"), uid("run_id", nullable=True), uid("actor_id"),
    sa.Column("review_version", sa.Integer, nullable=False), sa.Column("kind", sa.String(20), nullable=False),
    sa.Column("content", sa.JSON, nullable=False), timestamp("created_at", created=True),
    fk("packet_id actor_id", "rr_packets.id rr_packets.owner_id"),
    fk("revision_id packet_id", "rr_revisions.id rr_revisions.packet_id"),
    fk("run_id packet_id revision_id", "rr_runs.id rr_runs.packet_id rr_runs.revision_id"),
    sa.UniqueConstraint("packet_id", "review_version"),
    sa.CheckConstraint("review_version > 0", name="version"), state("kind", "resolution draft confirmation"),
    sa.Index("ix_rr_review_events_packet_created_id", "packet_id", "created_at", "id"))

# Minimal checkout recovery data, separated from immutable accounting identifiers.
checkout_details = sa.Table("rr_checkout_details", metadata,
    uid("order_id", primary=True, reference="rr_orders.id"),
    sa.Column("return_path", sa.String(200), nullable=False),
    sa.Column("checkout_url", sa.Text), timestamp("expires_at"))
