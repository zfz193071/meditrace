"""Create isolated referral domain

Revision: rr_0001
"""
from alembic import op
import sqlalchemy as sa


revision = 'rr_0001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # Frozen additive schema. Never import live application metadata here.
    op.create_table('rr_billing_events',
    sa.Column('stripe_event_id', sa.String(length=200), nullable=False),
    sa.Column('event_type', sa.String(length=100), nullable=False),
    sa.Column('object_id', sa.String(length=200), nullable=False),
    sa.Column('state', sa.String(length=20), nullable=False),
    sa.Column('received_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('processed_at', sa.DateTime(timezone=True), nullable=True),
    sa.CheckConstraint("state IN ('pending', 'processed', 'rejected', 'failed')", name=op.f('ck_rr_billing_events_state')),
    sa.PrimaryKeyConstraint('stripe_event_id', name=op.f('pk_rr_billing_events'))
    )
    op.create_index('ix_rr_billing_events_state_received', 'rr_billing_events', ['state', 'received_at'], unique=False)
    op.create_table('rr_budget_buckets',
    sa.Column('bucket_key', sa.String(length=80), nullable=False),
    sa.Column('limit_microusd', sa.BigInteger(), nullable=False),
    sa.Column('reserved_microusd', sa.BigInteger(), server_default='0', nullable=False),
    sa.Column('spent_microusd', sa.BigInteger(), server_default='0', nullable=False),
    sa.CheckConstraint('limit_microusd >= 0 AND reserved_microusd >= 0 AND spent_microusd >= 0', name=op.f('ck_rr_budget_buckets_nonnegative')),
    sa.PrimaryKeyConstraint('bucket_key', name=op.f('pk_rr_budget_buckets'))
    )
    op.create_table('rr_cleanup_jobs',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('object_key', sa.Text(), nullable=True),
    sa.Column('entity_id', sa.Uuid(), nullable=True),
    sa.Column('kind', sa.String(length=20), nullable=False),
    sa.Column('state', sa.String(length=20), nullable=False),
    sa.Column('attempt_count', sa.Integer(), server_default='0', nullable=False),
    sa.Column('next_attempt_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('last_error_code', sa.String(length=80), nullable=True),
    sa.CheckConstraint("kind IN ('object', 'packet', 'account', 'orphan', 'audit', 'billing')", name=op.f('ck_rr_cleanup_jobs_kind')),
    sa.CheckConstraint("state IN ('pending', 'running', 'succeeded', 'failed')", name=op.f('ck_rr_cleanup_jobs_state')),
    sa.CheckConstraint('attempt_count >= 0', name=op.f('ck_rr_cleanup_jobs_attempts')),
    sa.CheckConstraint('object_key IS NOT NULL OR entity_id IS NOT NULL', name=op.f('ck_rr_cleanup_jobs_target')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_rr_cleanup_jobs'))
    )
    op.create_index('ix_rr_cleanup_due', 'rr_cleanup_jobs', ['state', 'next_attempt_at'], unique=False)
    op.create_table('rr_oauth_states',
    sa.Column('state_hash', sa.String(length=64), nullable=False),
    sa.Column('browser_nonce_hash', sa.String(length=64), nullable=False),
    sa.Column('encrypted_verifier', sa.Text(), nullable=False),
    sa.Column('return_path', sa.Text(), nullable=False),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('consumed_at', sa.DateTime(timezone=True), nullable=True),
    sa.PrimaryKeyConstraint('state_hash', name=op.f('pk_rr_oauth_states'))
    )
    op.create_index('ix_rr_oauth_expiry', 'rr_oauth_states', ['expires_at'], unique=False)
    op.create_table('rr_rate_limit_buckets',
    sa.Column('scope', sa.String(length=100), nullable=False),
    sa.Column('action', sa.String(length=80), nullable=False),
    sa.Column('window_start', sa.DateTime(timezone=True), nullable=False),
    sa.Column('count', sa.Integer(), server_default='0', nullable=False),
    sa.CheckConstraint('count >= 0', name=op.f('ck_rr_rate_limit_buckets_count')),
    sa.PrimaryKeyConstraint('scope', 'action', 'window_start', name=op.f('pk_rr_rate_limit_buckets'))
    )
    op.create_index('ix_rr_rate_window', 'rr_rate_limit_buckets', ['window_start'], unique=False)
    op.create_table('rr_storage_buckets',
    sa.Column('scope', sa.String(length=100), nullable=False),
    sa.Column('limit_bytes', sa.BigInteger(), nullable=False),
    sa.Column('reserved_bytes', sa.BigInteger(), server_default='0', nullable=False),
    sa.Column('stored_bytes', sa.BigInteger(), server_default='0', nullable=False),
    sa.CheckConstraint('limit_bytes >= 0 AND reserved_bytes >= 0 AND stored_bytes >= 0 AND reserved_bytes + stored_bytes <= limit_bytes', name=op.f('ck_rr_storage_buckets_capacity')),
    sa.PrimaryKeyConstraint('scope', name=op.f('pk_rr_storage_buckets'))
    )
    op.create_table('rr_users',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('github_subject', sa.String(length=128), nullable=False),
    sa.Column('display_name', sa.String(length=200), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('disabled_at', sa.DateTime(timezone=True), nullable=True),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_rr_users')),
    sa.UniqueConstraint('github_subject', name=op.f('uq_rr_users_github_subject'))
    )
    op.create_table('rr_idempotency',
    sa.Column('owner_id', sa.Uuid(), nullable=False),
    sa.Column('operation', sa.String(length=80), nullable=False),
    sa.Column('key', sa.String(length=200), nullable=False),
    sa.Column('request_hash', sa.String(length=64), nullable=False),
    sa.Column('resource_id', sa.Uuid(), nullable=False),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['owner_id'], ['rr_users.id'], name=op.f('fk_rr_idempotency_owner_id_rr_users')),
    sa.PrimaryKeyConstraint('owner_id', 'operation', 'key', name=op.f('pk_rr_idempotency'))
    )
    op.create_index('ix_rr_idempotency_expiry', 'rr_idempotency', ['expires_at'], unique=False)
    op.create_table('rr_orders',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('owner_id', sa.Uuid(), nullable=True),
    sa.Column('environment', sa.String(length=10), nullable=False),
    sa.Column('checkout_session_id', sa.String(length=200), nullable=True),
    sa.Column('payment_intent_id', sa.String(length=200), nullable=True),
    sa.Column('price_id', sa.String(length=200), nullable=False),
    sa.Column('amount', sa.BigInteger(), nullable=False),
    sa.Column('currency', sa.String(length=3), nullable=False),
    sa.Column('state', sa.String(length=20), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('paid_at', sa.DateTime(timezone=True), nullable=True),
    sa.CheckConstraint("environment IN ('test')", name=op.f('ck_rr_orders_environment')),
    sa.CheckConstraint("state IN ('pending', 'paid', 'expired', 'failed', 'refunded', 'revoked')", name=op.f('ck_rr_orders_state')),
    sa.CheckConstraint('amount > 0', name=op.f('ck_rr_orders_amount')),
    sa.ForeignKeyConstraint(['owner_id'], ['rr_users.id'], name=op.f('fk_rr_orders_owner_id_rr_users')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_rr_orders')),
    sa.UniqueConstraint('checkout_session_id', name=op.f('uq_rr_orders_checkout_session_id')),
    sa.UniqueConstraint('id', 'owner_id', 'environment', name=op.f('uq_rr_orders_id_owner_id_environment')),
    sa.UniqueConstraint('payment_intent_id', name=op.f('uq_rr_orders_payment_intent_id'))
    )
    op.create_index('ix_rr_orders_owner_created_id', 'rr_orders', ['owner_id', 'created_at', 'id'], unique=False)
    op.create_index('uq_rr_orders_pending_owner', 'rr_orders', ['owner_id', 'environment'], unique=True, postgresql_where=sa.text("state = 'pending'"), sqlite_where=sa.text("state = 'pending'"))
    op.create_table('rr_packets',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('owner_id', sa.Uuid(), nullable=False),
    sa.Column('title', sa.String(length=200), nullable=False),
    sa.Column('current_revision', sa.Integer(), server_default='0', nullable=False),
    sa.Column('review_version', sa.Integer(), server_default='0', nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
    sa.CheckConstraint('current_revision >= 0 AND review_version >= 0', name=op.f('ck_rr_packets_versions')),
    sa.CheckConstraint('expires_at > created_at', name=op.f('ck_rr_packets_expiry')),
    sa.ForeignKeyConstraint(['owner_id'], ['rr_users.id'], name=op.f('fk_rr_packets_owner_id_rr_users')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_rr_packets')),
    sa.UniqueConstraint('id', 'owner_id', name=op.f('uq_rr_packets_id_owner_id'))
    )
    op.create_index('ix_rr_packets_expiry', 'rr_packets', ['expires_at', 'deleted_at'], unique=False)
    op.create_index('ix_rr_packets_owner_created_id', 'rr_packets', ['owner_id', 'created_at', 'id'], unique=False)
    op.create_table('rr_sessions',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('user_id', sa.Uuid(), nullable=False),
    sa.Column('token_hash', sa.String(length=64), nullable=False),
    sa.Column('csrf_secret', sa.String(length=128), nullable=False),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['rr_users.id'], name=op.f('fk_rr_sessions_user_id_rr_users')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_rr_sessions')),
    sa.UniqueConstraint('token_hash', name=op.f('uq_rr_sessions_token_hash'))
    )
    op.create_index('ix_rr_sessions_user_expiry', 'rr_sessions', ['user_id', 'expires_at'], unique=False)
    op.create_table('rr_documents',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('packet_id', sa.Uuid(), nullable=False),
    sa.Column('owner_id', sa.Uuid(), nullable=False),
    sa.Column('kind', sa.String(length=20), nullable=False),
    sa.Column('filename', sa.String(length=255), nullable=False),
    sa.Column('sha256', sa.String(length=64), nullable=False),
    sa.Column('storage_key', sa.Text(), nullable=False),
    sa.Column('byte_size', sa.BigInteger(), nullable=False),
    sa.Column('parse_status', sa.String(length=20), nullable=False),
    sa.Column('parser_version', sa.String(length=80), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
    sa.CheckConstraint("kind IN ('pdf', 'text')", name=op.f('ck_rr_documents_kind')),
    sa.CheckConstraint("parse_status IN ('uploading', 'parsing', 'ready', 'rejected', 'failed')", name=op.f('ck_rr_documents_parse_status')),
    sa.CheckConstraint('byte_size >= 0', name=op.f('ck_rr_documents_size')),
    sa.ForeignKeyConstraint(['packet_id', 'owner_id'], ['rr_packets.id', 'rr_packets.owner_id'], name=op.f('fk_rr_documents_packet_id_owner_id_rr_packets')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_rr_documents')),
    sa.UniqueConstraint('id', 'owner_id', name=op.f('uq_rr_documents_id_owner_id')),
    sa.UniqueConstraint('id', 'packet_id', name=op.f('uq_rr_documents_id_packet_id')),
    sa.UniqueConstraint('storage_key', name=op.f('uq_rr_documents_storage_key'))
    )
    op.create_index('ix_rr_documents_packet_created', 'rr_documents', ['packet_id', 'created_at'], unique=False)
    op.create_table('rr_memberships',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('owner_id', sa.Uuid(), nullable=True),
    sa.Column('source_order_id', sa.Uuid(), nullable=False),
    sa.Column('environment', sa.String(length=10), nullable=False),
    sa.Column('valid_from', sa.DateTime(timezone=True), nullable=False),
    sa.Column('valid_until', sa.DateTime(timezone=True), nullable=False),
    sa.Column('granted_units', sa.Integer(), nullable=False),
    sa.Column('reserved_units', sa.Integer(), server_default='0', nullable=False),
    sa.Column('consumed_units', sa.Integer(), server_default='0', nullable=False),
    sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
    sa.CheckConstraint("environment IN ('test')", name=op.f('ck_rr_memberships_environment')),
    sa.CheckConstraint('granted_units >= 0 AND reserved_units >= 0 AND consumed_units >= 0 AND reserved_units + consumed_units <= granted_units', name=op.f('ck_rr_memberships_units')),
    sa.CheckConstraint('valid_until > valid_from', name=op.f('ck_rr_memberships_validity')),
    sa.ForeignKeyConstraint(['owner_id'], ['rr_users.id'], name=op.f('fk_rr_memberships_owner_id_rr_users')),
    sa.ForeignKeyConstraint(['source_order_id', 'owner_id', 'environment'], ['rr_orders.id', 'rr_orders.owner_id', 'rr_orders.environment'], name=op.f('fk_rr_memberships_source_order_id_owner_id_environment_rr_orders')),
    sa.ForeignKeyConstraint(['source_order_id'], ['rr_orders.id'], name=op.f('fk_rr_memberships_source_order_id_rr_orders')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_rr_memberships')),
    sa.UniqueConstraint('id', 'owner_id', name=op.f('uq_rr_memberships_id_owner_id')),
    sa.UniqueConstraint('source_order_id', name=op.f('uq_rr_memberships_source_order_id'))
    )
    op.create_index('ix_rr_memberships_owner_until', 'rr_memberships', ['owner_id', 'valid_until'], unique=False)
    op.create_table('rr_revisions',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('packet_id', sa.Uuid(), nullable=False),
    sa.Column('revision_number', sa.Integer(), nullable=False),
    sa.Column('manifest_hash', sa.String(length=64), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.CheckConstraint('revision_number > 0', name=op.f('ck_rr_revisions_number')),
    sa.ForeignKeyConstraint(['packet_id'], ['rr_packets.id'], name=op.f('fk_rr_revisions_packet_id_rr_packets')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_rr_revisions')),
    sa.UniqueConstraint('id', 'packet_id', name=op.f('uq_rr_revisions_id_packet_id')),
    sa.UniqueConstraint('packet_id', 'revision_number', name=op.f('uq_rr_revisions_packet_id_revision_number'))
    )
    op.create_table('rr_document_pages',
    sa.Column('document_id', sa.Uuid(), nullable=False),
    sa.Column('page_number', sa.Integer(), nullable=False),
    sa.Column('normalized_text', sa.Text(), nullable=False),
    sa.Column('text_hash', sa.String(length=64), nullable=False),
    sa.Column('parse_quality', sa.String(length=20), nullable=False),
    sa.CheckConstraint("parse_quality IN ('ready', 'empty', 'unreadable', 'failed')", name=op.f('ck_rr_document_pages_parse_quality')),
    sa.CheckConstraint('page_number >= 1', name=op.f('ck_rr_document_pages_page')),
    sa.ForeignKeyConstraint(['document_id'], ['rr_documents.id'], name=op.f('fk_rr_document_pages_document_id_rr_documents')),
    sa.PrimaryKeyConstraint('document_id', 'page_number', name=op.f('pk_rr_document_pages')),
    sa.UniqueConstraint('document_id', 'page_number', 'text_hash', name=op.f('uq_rr_document_pages_document_id_page_number_text_hash'))
    )
    op.create_table('rr_revision_documents',
    sa.Column('revision_id', sa.Uuid(), nullable=False),
    sa.Column('document_id', sa.Uuid(), nullable=False),
    sa.Column('packet_id', sa.Uuid(), nullable=False),
    sa.Column('ordinal', sa.Integer(), nullable=False),
    sa.CheckConstraint('ordinal >= 0', name=op.f('ck_rr_revision_documents_ordinal')),
    sa.ForeignKeyConstraint(['document_id', 'packet_id'], ['rr_documents.id', 'rr_documents.packet_id'], name=op.f('fk_rr_revision_documents_document_id_packet_id_rr_documents')),
    sa.ForeignKeyConstraint(['revision_id', 'packet_id'], ['rr_revisions.id', 'rr_revisions.packet_id'], name=op.f('fk_rr_revision_documents_revision_id_packet_id_rr_revisions')),
    sa.PrimaryKeyConstraint('revision_id', 'document_id', name=op.f('pk_rr_revision_documents')),
    sa.UniqueConstraint('revision_id', 'ordinal', name=op.f('uq_rr_revision_documents_revision_id_ordinal'))
    )
    op.create_index('ix_rr_revision_documents_document', 'rr_revision_documents', ['document_id'], unique=False)
    op.create_table('rr_runs',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('packet_id', sa.Uuid(), nullable=False),
    sa.Column('owner_id', sa.Uuid(), nullable=False),
    sa.Column('revision_id', sa.Uuid(), nullable=False),
    sa.Column('checklist_version', sa.String(length=100), nullable=False),
    sa.Column('mode', sa.String(length=20), nullable=False),
    sa.Column('state', sa.String(length=24), nullable=False),
    sa.Column('input_hash', sa.String(length=64), nullable=False),
    sa.Column('prompt_version', sa.String(length=100), nullable=False),
    sa.Column('schema_version', sa.String(length=100), nullable=False),
    sa.Column('model_requested', sa.String(length=100), nullable=True),
    sa.Column('model_reported', sa.String(length=100), nullable=True),
    sa.Column('lease_expires_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('provider_dispatched_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('provider_request_id', sa.String(length=200), nullable=True),
    sa.Column('usage', sa.JSON(), nullable=True),
    sa.Column('error_code', sa.String(length=80), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('finished_at', sa.DateTime(timezone=True), nullable=True),
    sa.CheckConstraint("mode IN ('precomputed', 'fake', 'replay', 'real')", name=op.f('ck_rr_runs_mode')),
    sa.CheckConstraint("state IN ('pending', 'running', 'succeeded', 'failed', 'outcome_unknown', 'cancelled')", name=op.f('ck_rr_runs_state')),
    sa.ForeignKeyConstraint(['packet_id', 'owner_id'], ['rr_packets.id', 'rr_packets.owner_id'], name=op.f('fk_rr_runs_packet_id_owner_id_rr_packets')),
    sa.ForeignKeyConstraint(['revision_id', 'packet_id'], ['rr_revisions.id', 'rr_revisions.packet_id'], name=op.f('fk_rr_runs_revision_id_packet_id_rr_revisions')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_rr_runs')),
    sa.UniqueConstraint('id', 'owner_id', name=op.f('uq_rr_runs_id_owner_id')),
    sa.UniqueConstraint('id', 'checklist_version', name=op.f('uq_rr_runs_id_checklist_version')),
    sa.UniqueConstraint('id', 'packet_id', 'revision_id', name=op.f('uq_rr_runs_id_packet_id_revision_id')),
    sa.UniqueConstraint('id', 'revision_id', name=op.f('uq_rr_runs_id_revision_id'))
    )
    op.create_index('ix_rr_runs_packet_created_id', 'rr_runs', ['packet_id', 'created_at', 'id'], unique=False)
    op.create_index('ix_rr_runs_state_lease', 'rr_runs', ['state', 'lease_expires_at'], unique=False)
    op.create_index('uq_rr_runs_active_input', 'rr_runs', ['packet_id', 'revision_id', 'checklist_version', 'mode', 'input_hash'], unique=True, postgresql_where=sa.text("state IN ('pending', 'running')"), sqlite_where=sa.text("state IN ('pending', 'running')"))
    op.create_table('rr_storage_reservations',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('owner_id', sa.Uuid(), nullable=False),
    sa.Column('document_id', sa.Uuid(), nullable=False),
    sa.Column('reserved_bytes', sa.BigInteger(), nullable=False),
    sa.Column('state', sa.String(length=24), nullable=False),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
    sa.CheckConstraint("state IN ('reserved', 'stored', 'released', 'cleanup_pending')", name=op.f('ck_rr_storage_reservations_state')),
    sa.CheckConstraint('reserved_bytes >= 0', name=op.f('ck_rr_storage_reservations_bytes')),
    sa.ForeignKeyConstraint(['document_id', 'owner_id'], ['rr_documents.id', 'rr_documents.owner_id'], name=op.f('fk_rr_storage_reservations_document_id_owner_id_rr_documents')),
    sa.ForeignKeyConstraint(['document_id'], ['rr_documents.id'], name=op.f('fk_rr_storage_reservations_document_id_rr_documents')),
    sa.ForeignKeyConstraint(['owner_id'], ['rr_users.id'], name=op.f('fk_rr_storage_reservations_owner_id_rr_users')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_rr_storage_reservations')),
    sa.UniqueConstraint('document_id', name=op.f('uq_rr_storage_reservations_document_id'))
    )
    op.create_index('ix_rr_storage_expiry', 'rr_storage_reservations', ['state', 'expires_at'], unique=False)
    op.create_index('ix_rr_storage_owner_state', 'rr_storage_reservations', ['owner_id', 'state'], unique=False)
    op.create_table('rr_audit_events',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('actor_id', sa.Uuid(), nullable=True),
    sa.Column('packet_id', sa.Uuid(), nullable=True),
    sa.Column('action', sa.String(length=80), nullable=False),
    sa.Column('revision_id', sa.Uuid(), nullable=True),
    sa.Column('run_id', sa.Uuid(), nullable=True),
    sa.Column('request_id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['actor_id'], ['rr_users.id'], name=op.f('fk_rr_audit_events_actor_id_rr_users')),
    sa.ForeignKeyConstraint(['packet_id'], ['rr_packets.id'], name=op.f('fk_rr_audit_events_packet_id_rr_packets')),
    sa.ForeignKeyConstraint(['revision_id'], ['rr_revisions.id'], name=op.f('fk_rr_audit_events_revision_id_rr_revisions')),
    sa.ForeignKeyConstraint(['run_id'], ['rr_runs.id'], name=op.f('fk_rr_audit_events_run_id_rr_runs')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_rr_audit_events'))
    )
    op.create_index('ix_rr_audit_created', 'rr_audit_events', ['created_at'], unique=False)
    op.create_index('ix_rr_audit_packet_created', 'rr_audit_events', ['packet_id', 'created_at'], unique=False)
    op.create_table('rr_concurrency_slots',
    sa.Column('scope', sa.String(length=100), nullable=False),
    sa.Column('slot_number', sa.Integer(), nullable=False),
    sa.Column('run_id', sa.Uuid(), nullable=True),
    sa.Column('lease_expires_at', sa.DateTime(timezone=True), nullable=True),
    sa.CheckConstraint('(run_id IS NULL AND lease_expires_at IS NULL) OR (run_id IS NOT NULL AND lease_expires_at IS NOT NULL)', name=op.f('ck_rr_concurrency_slots_lease')),
    sa.CheckConstraint('slot_number >= 0', name=op.f('ck_rr_concurrency_slots_slot')),
    sa.ForeignKeyConstraint(['run_id'], ['rr_runs.id'], name=op.f('fk_rr_concurrency_slots_run_id_rr_runs')),
    sa.PrimaryKeyConstraint('scope', 'slot_number', name=op.f('pk_rr_concurrency_slots')),
    sa.UniqueConstraint('scope', 'run_id', name=op.f('uq_rr_concurrency_slots_scope_run_id'))
    )
    op.create_index('ix_rr_slots_expiry', 'rr_concurrency_slots', ['lease_expires_at'], unique=False)
    op.create_table('rr_evidence',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('run_id', sa.Uuid(), nullable=False),
    sa.Column('revision_id', sa.Uuid(), nullable=False),
    sa.Column('document_id', sa.Uuid(), nullable=False),
    sa.Column('page_number', sa.Integer(), nullable=False),
    sa.Column('start_cp', sa.Integer(), nullable=False),
    sa.Column('end_cp', sa.Integer(), nullable=False),
    sa.Column('quote', sa.Text(), nullable=False),
    sa.Column('text_hash', sa.String(length=64), nullable=False),
    sa.CheckConstraint('start_cp >= 0 AND end_cp > start_cp AND end_cp - start_cp = length(quote)', name=op.f('ck_rr_evidence_span')),
    sa.ForeignKeyConstraint(['document_id', 'page_number', 'text_hash'], ['rr_document_pages.document_id', 'rr_document_pages.page_number', 'rr_document_pages.text_hash'], name=op.f('fk_rr_evidence_document_id_page_number_text_hash_rr_document_pages')),
    sa.ForeignKeyConstraint(['revision_id', 'document_id'], ['rr_revision_documents.revision_id', 'rr_revision_documents.document_id'], name=op.f('fk_rr_evidence_revision_id_document_id_rr_revision_documents')),
    sa.ForeignKeyConstraint(['run_id', 'revision_id'], ['rr_runs.id', 'rr_runs.revision_id'], name=op.f('fk_rr_evidence_run_id_revision_id_rr_runs')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_rr_evidence')),
    sa.UniqueConstraint('id', 'run_id', name=op.f('uq_rr_evidence_id_run_id'))
    )
    op.create_index('ix_rr_evidence_run', 'rr_evidence', ['run_id'], unique=False)
    op.create_table('rr_facts',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('run_id', sa.Uuid(), nullable=False),
    sa.Column('field_key', sa.String(length=60), nullable=False),
    sa.Column('value_raw', sa.Text(), nullable=False),
    sa.Column('value_normalized', sa.Text(), nullable=True),
    sa.Column('assertion_status', sa.String(length=24), nullable=False),
    sa.Column('temporal_context', sa.Text(), nullable=True),
    sa.CheckConstraint("assertion_status IN ('stated', 'explicitly_none', 'unknown')", name=op.f('ck_rr_facts_assertion_status')),
    sa.CheckConstraint("field_key IN ('patient.name', 'patient.dob', 'referrer.name', 'referrer.contact', 'recipient', 'referral.reason', 'medications', 'allergies', 'attachment_reference', 'report.description')", name=op.f('ck_rr_facts_field_key')),
    sa.CheckConstraint('length(value_raw) > 0', name=op.f('ck_rr_facts_value')),
    sa.ForeignKeyConstraint(['run_id'], ['rr_runs.id'], name=op.f('fk_rr_facts_run_id_rr_runs')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_rr_facts')),
    sa.UniqueConstraint('id', 'run_id', name=op.f('uq_rr_facts_id_run_id'))
    )
    op.create_index('ix_rr_facts_run_field', 'rr_facts', ['run_id', 'field_key'], unique=False)
    op.create_table('rr_findings',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('run_id', sa.Uuid(), nullable=False),
    sa.Column('rule_id', sa.String(length=3), nullable=False),
    sa.Column('checklist_version', sa.String(length=100), nullable=False),
    sa.Column('kind', sa.String(length=32), nullable=False),
    sa.Column('field_keys', sa.JSON(), nullable=False),
    sa.Column('message', sa.Text(), nullable=False),
    sa.CheckConstraint("kind IN ('missing', 'unknown', 'identity_mismatch', 'statement_difference', 'attachment_unmatched', 'parse_quality')", name=op.f('ck_rr_findings_kind')),
    sa.CheckConstraint("rule_id IN ('C01', 'C02', 'C03', 'C04', 'C05', 'C06', 'C07', 'C08')", name=op.f('ck_rr_findings_rule_id')),
    sa.ForeignKeyConstraint(['run_id'], ['rr_runs.id'], name=op.f('fk_rr_findings_run_id_rr_runs')),
    sa.ForeignKeyConstraint(['run_id', 'checklist_version'], ['rr_runs.id', 'rr_runs.checklist_version'], name=op.f('fk_rr_findings_run_id_checklist_version_rr_runs')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_rr_findings')),
    sa.UniqueConstraint('id', 'run_id', name=op.f('uq_rr_findings_id_run_id'))
    )
    op.create_index('ix_rr_findings_run', 'rr_findings', ['run_id'], unique=False)
    op.create_table('rr_handoff_drafts',
    sa.Column('packet_id', sa.Uuid(), nullable=False),
    sa.Column('revision_id', sa.Uuid(), nullable=False),
    sa.Column('run_id', sa.Uuid(), nullable=True),
    sa.Column('content', sa.JSON(), nullable=False),
    sa.Column('review_version', sa.Integer(), nullable=False),
    sa.CheckConstraint('review_version >= 0', name=op.f('ck_rr_handoff_drafts_version')),
    sa.ForeignKeyConstraint(['revision_id', 'packet_id'], ['rr_revisions.id', 'rr_revisions.packet_id'], name=op.f('fk_rr_handoff_drafts_revision_id_packet_id_rr_revisions')),
    sa.ForeignKeyConstraint(['run_id', 'packet_id', 'revision_id'], ['rr_runs.id', 'rr_runs.packet_id', 'rr_runs.revision_id'], name=op.f('fk_rr_handoff_drafts_run_id_packet_id_revision_id_rr_runs')),
    sa.PrimaryKeyConstraint('packet_id', name=op.f('pk_rr_handoff_drafts'))
    )
    op.create_table('rr_review_snapshots',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('packet_id', sa.Uuid(), nullable=False),
    sa.Column('revision_id', sa.Uuid(), nullable=False),
    sa.Column('run_id', sa.Uuid(), nullable=True),
    sa.Column('review_version', sa.Integer(), nullable=False),
    sa.Column('confirmed_by', sa.Uuid(), nullable=False),
    sa.Column('confirmed_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('payload', sa.JSON(), nullable=False),
    sa.Column('payload_hash', sa.String(length=64), nullable=False),
    sa.Column('has_unresolved', sa.Boolean(), nullable=False),
    sa.CheckConstraint('review_version >= 0', name=op.f('ck_rr_review_snapshots_version')),
    sa.ForeignKeyConstraint(['packet_id', 'confirmed_by'], ['rr_packets.id', 'rr_packets.owner_id'], name=op.f('fk_rr_review_snapshots_packet_id_confirmed_by_rr_packets')),
    sa.ForeignKeyConstraint(['revision_id', 'packet_id'], ['rr_revisions.id', 'rr_revisions.packet_id'], name=op.f('fk_rr_review_snapshots_revision_id_packet_id_rr_revisions')),
    sa.ForeignKeyConstraint(['run_id', 'packet_id', 'revision_id'], ['rr_runs.id', 'rr_runs.packet_id', 'rr_runs.revision_id'], name=op.f('fk_rr_review_snapshots_run_id_packet_id_revision_id_rr_runs')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_rr_review_snapshots')),
    sa.UniqueConstraint('packet_id', 'review_version', name=op.f('uq_rr_review_snapshots_packet_id_review_version'))
    )
    op.create_index('ix_rr_snapshots_packet_created_id', 'rr_review_snapshots', ['packet_id', 'confirmed_at', 'id'], unique=False)
    op.create_table('rr_usage_reservations',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('run_id', sa.Uuid(), nullable=True),
    sa.Column('membership_id', sa.Uuid(), nullable=False),
    sa.Column('owner_id', sa.Uuid(), nullable=True),
    sa.Column('units', sa.Integer(), nullable=False),
    sa.Column('cost_upper_bound_microusd', sa.BigInteger(), nullable=False),
    sa.Column('actual_microusd', sa.BigInteger(), nullable=True),
    sa.Column('state', sa.String(length=24), nullable=False),
    sa.Column('price_version', sa.String(length=100), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.CheckConstraint("state IN ('reserved', 'settled', 'released', 'retained_unknown', 'estimated_spent')", name=op.f('ck_rr_usage_reservations_state')),
    sa.CheckConstraint("state NOT IN ('reserved', 'retained_unknown') OR (run_id IS NOT NULL AND owner_id IS NOT NULL)", name=op.f('ck_rr_usage_reservations_active_owner')),
    sa.CheckConstraint('units > 0 AND cost_upper_bound_microusd >= 0 AND (actual_microusd IS NULL OR actual_microusd >= 0)', name=op.f('ck_rr_usage_reservations_amounts')),
    sa.ForeignKeyConstraint(['membership_id', 'owner_id'], ['rr_memberships.id', 'rr_memberships.owner_id'], name=op.f('fk_rr_usage_reservations_membership_id_owner_id_rr_memberships')),
    sa.ForeignKeyConstraint(['membership_id'], ['rr_memberships.id'], name=op.f('fk_rr_usage_reservations_membership_id_rr_memberships')),
    sa.ForeignKeyConstraint(['run_id', 'owner_id'], ['rr_runs.id', 'rr_runs.owner_id'], name=op.f('fk_rr_usage_reservations_run_id_owner_id_rr_runs')),
    sa.ForeignKeyConstraint(['run_id'], ['rr_runs.id'], name=op.f('fk_rr_usage_reservations_run_id_rr_runs')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_rr_usage_reservations')),
    sa.UniqueConstraint('run_id', name=op.f('uq_rr_usage_reservations_run_id'))
    )
    op.create_table('rr_fact_evidence',
    sa.Column('fact_id', sa.Uuid(), nullable=False),
    sa.Column('evidence_id', sa.Uuid(), nullable=False),
    sa.Column('run_id', sa.Uuid(), nullable=False),
    sa.ForeignKeyConstraint(['evidence_id', 'run_id'], ['rr_evidence.id', 'rr_evidence.run_id'], name=op.f('fk_rr_fact_evidence_evidence_id_run_id_rr_evidence')),
    sa.ForeignKeyConstraint(['fact_id', 'run_id'], ['rr_facts.id', 'rr_facts.run_id'], name=op.f('fk_rr_fact_evidence_fact_id_run_id_rr_facts')),
    sa.PrimaryKeyConstraint('fact_id', 'evidence_id', name=op.f('pk_rr_fact_evidence'))
    )
    op.create_table('rr_finding_documents',
    sa.Column('finding_id', sa.Uuid(), nullable=False),
    sa.Column('document_id', sa.Uuid(), nullable=False),
    sa.Column('run_id', sa.Uuid(), nullable=False),
    sa.Column('revision_id', sa.Uuid(), nullable=False),
    sa.ForeignKeyConstraint(['finding_id', 'run_id'], ['rr_findings.id', 'rr_findings.run_id'], name=op.f('fk_rr_finding_documents_finding_id_run_id_rr_findings')),
    sa.ForeignKeyConstraint(['revision_id', 'document_id'], ['rr_revision_documents.revision_id', 'rr_revision_documents.document_id'], name=op.f('fk_rr_finding_documents_revision_id_document_id_rr_revision_documents')),
    sa.ForeignKeyConstraint(['run_id', 'revision_id'], ['rr_runs.id', 'rr_runs.revision_id'], name=op.f('fk_rr_finding_documents_run_id_revision_id_rr_runs')),
    sa.PrimaryKeyConstraint('finding_id', 'document_id', name=op.f('pk_rr_finding_documents'))
    )
    op.create_table('rr_finding_evidence',
    sa.Column('finding_id', sa.Uuid(), nullable=False),
    sa.Column('evidence_id', sa.Uuid(), nullable=False),
    sa.Column('run_id', sa.Uuid(), nullable=False),
    sa.ForeignKeyConstraint(['evidence_id', 'run_id'], ['rr_evidence.id', 'rr_evidence.run_id'], name=op.f('fk_rr_finding_evidence_evidence_id_run_id_rr_evidence')),
    sa.ForeignKeyConstraint(['finding_id', 'run_id'], ['rr_findings.id', 'rr_findings.run_id'], name=op.f('fk_rr_finding_evidence_finding_id_run_id_rr_findings')),
    sa.PrimaryKeyConstraint('finding_id', 'evidence_id', name=op.f('pk_rr_finding_evidence'))
    )
    op.create_table('rr_finding_facts',
    sa.Column('finding_id', sa.Uuid(), nullable=False),
    sa.Column('fact_id', sa.Uuid(), nullable=False),
    sa.Column('run_id', sa.Uuid(), nullable=False),
    sa.ForeignKeyConstraint(['fact_id', 'run_id'], ['rr_facts.id', 'rr_facts.run_id'], name=op.f('fk_rr_finding_facts_fact_id_run_id_rr_facts')),
    sa.ForeignKeyConstraint(['finding_id', 'run_id'], ['rr_findings.id', 'rr_findings.run_id'], name=op.f('fk_rr_finding_facts_finding_id_run_id_rr_findings')),
    sa.PrimaryKeyConstraint('finding_id', 'fact_id', name=op.f('pk_rr_finding_facts'))
    )
    op.create_table('rr_resolutions',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('finding_id', sa.Uuid(), nullable=False),
    sa.Column('run_id', sa.Uuid(), nullable=False),
    sa.Column('actor_id', sa.Uuid(), nullable=False),
    sa.Column('action', sa.String(length=20), nullable=False),
    sa.Column('reason', sa.Text(), nullable=False),
    sa.Column('corrected_value', sa.Text(), nullable=True),
    sa.Column('review_version', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.CheckConstraint("action IN ('resolve', 'dismiss', 'defer', 'reopen')", name=op.f('ck_rr_resolutions_action')),
    sa.CheckConstraint("action NOT IN ('dismiss', 'defer') OR length(trim(reason)) > 0", name=op.f('ck_rr_resolutions_reason')),
    sa.CheckConstraint('review_version > 0', name=op.f('ck_rr_resolutions_version')),
    sa.ForeignKeyConstraint(['finding_id', 'run_id'], ['rr_findings.id', 'rr_findings.run_id'], name=op.f('fk_rr_resolutions_finding_id_run_id_rr_findings')),
    sa.ForeignKeyConstraint(['run_id', 'actor_id'], ['rr_runs.id', 'rr_runs.owner_id'], name=op.f('fk_rr_resolutions_run_id_actor_id_rr_runs')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_rr_resolutions')),
    sa.UniqueConstraint('id', 'run_id', name=op.f('uq_rr_resolutions_id_run_id'))
    )
    op.create_index('ix_rr_resolutions_finding_version', 'rr_resolutions', ['finding_id', 'review_version'], unique=False)
    op.create_table('rr_usage_buckets',
    sa.Column('reservation_id', sa.Uuid(), nullable=False),
    sa.Column('bucket_key', sa.String(length=80), nullable=False),
    sa.ForeignKeyConstraint(['bucket_key'], ['rr_budget_buckets.bucket_key'], name=op.f('fk_rr_usage_buckets_bucket_key_rr_budget_buckets')),
    sa.ForeignKeyConstraint(['reservation_id'], ['rr_usage_reservations.id'], name=op.f('fk_rr_usage_buckets_reservation_id_rr_usage_reservations')),
    sa.PrimaryKeyConstraint('reservation_id', 'bucket_key', name=op.f('pk_rr_usage_buckets'))
    )
    op.create_table('rr_resolution_evidence',
    sa.Column('resolution_id', sa.Uuid(), nullable=False),
    sa.Column('evidence_id', sa.Uuid(), nullable=False),
    sa.Column('run_id', sa.Uuid(), nullable=False),
    sa.ForeignKeyConstraint(['evidence_id', 'run_id'], ['rr_evidence.id', 'rr_evidence.run_id'], name=op.f('fk_rr_resolution_evidence_evidence_id_run_id_rr_evidence')),
    sa.ForeignKeyConstraint(['resolution_id', 'run_id'], ['rr_resolutions.id', 'rr_resolutions.run_id'], name=op.f('fk_rr_resolution_evidence_resolution_id_run_id_rr_resolutions')),
    sa.PrimaryKeyConstraint('resolution_id', 'evidence_id', name=op.f('pk_rr_resolution_evidence'))
    )
    # Immutable source/result/history rows can be purged, but never overwritten.
    immutable = (
        'rr_document_pages', 'rr_revisions', 'rr_revision_documents', 'rr_facts',
        'rr_evidence', 'rr_fact_evidence', 'rr_findings', 'rr_finding_facts',
        'rr_finding_evidence', 'rr_finding_documents', 'rr_resolutions',
        'rr_resolution_evidence', 'rr_review_snapshots', 'rr_usage_buckets',
    )
    dialect = op.get_bind().dialect.name
    if dialect == 'postgresql':
        op.execute("""CREATE FUNCTION rr_reject_immutable_update() RETURNS trigger
            LANGUAGE plpgsql AS $$ BEGIN
                RAISE EXCEPTION 'Immutable referral record' USING ERRCODE = '23514';
            END; $$""")
        for table in immutable:
            op.execute(f'CREATE TRIGGER rr_immutable BEFORE UPDATE ON {table} '
                       'FOR EACH ROW EXECUTE FUNCTION rr_reject_immutable_update()')
        op.execute("""CREATE FUNCTION rr_protect_ready_document() RETURNS trigger
            LANGUAGE plpgsql AS $$ BEGIN
                IF OLD.parse_status = 'ready' AND
                   ROW(NEW.id, NEW.packet_id, NEW.owner_id, NEW.kind, NEW.filename, NEW.sha256,
                       NEW.storage_key, NEW.byte_size, NEW.parser_version, NEW.parse_status)
                   IS DISTINCT FROM
                   ROW(OLD.id, OLD.packet_id, OLD.owner_id, OLD.kind, OLD.filename, OLD.sha256,
                       OLD.storage_key, OLD.byte_size, OLD.parser_version, OLD.parse_status) THEN
                    RAISE EXCEPTION 'Ready document content is immutable' USING ERRCODE = '23514';
                END IF;
                RETURN NEW;
            END; $$""")
        op.execute('CREATE TRIGGER rr_document_content BEFORE UPDATE ON rr_documents '
                   'FOR EACH ROW EXECUTE FUNCTION rr_protect_ready_document()')
    elif dialect == 'sqlite':
        for table in immutable:
            op.execute(f"CREATE TRIGGER {table}_immutable BEFORE UPDATE ON {table} "
                       "BEGIN SELECT RAISE(ABORT, 'Immutable referral record'); END")
        columns = ('id', 'packet_id', 'owner_id', 'kind', 'filename', 'sha256',
                   'storage_key', 'byte_size', 'parser_version', 'parse_status')
        changed = ' OR '.join(f'NEW.{column} IS NOT OLD.{column}' for column in columns)
        op.execute("CREATE TRIGGER rr_document_content BEFORE UPDATE ON rr_documents "
                   f"WHEN OLD.parse_status = 'ready' AND ({changed}) "
                   "BEGIN SELECT RAISE(ABORT, 'Ready document content is immutable'); END")
    else:
        raise RuntimeError('Unsupported migration dialect')


def downgrade():
    raise RuntimeError("Referral migrations are additive; roll back application code, never domain data")
