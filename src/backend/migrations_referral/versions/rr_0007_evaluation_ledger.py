"""Append independent synthetic evaluation accounting; no workspace grants."""
from alembic import op
import sqlalchemy as sa

revision = "rr_0007"
down_revision = "rr_0006"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("rr_evaluation_batches",
        sa.Column("id", sa.Uuid(), nullable=False), sa.Column("plan_hash", sa.String(64), nullable=False),
        sa.Column("cap_microusd", sa.BigInteger(), nullable=False),
        sa.Column("reserved_microusd", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("spent_microusd", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("model", sa.String(200), nullable=False), sa.Column("price_version", sa.String(100), nullable=False),
        sa.Column("input_price", sa.BigInteger(), nullable=False), sa.Column("output_price", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_rr_evaluation_batches")),
        sa.CheckConstraint("cap_microusd > 0 AND reserved_microusd >= 0 AND spent_microusd >= 0 AND input_price > 0 AND output_price > 0", name=op.f("ck_rr_evaluation_batches_amounts")))
    op.create_table("rr_evaluation_attempts",
        sa.Column("id", sa.Uuid(), nullable=False), sa.Column("batch_id", sa.Uuid(), nullable=False),
        sa.Column("sample_hash", sa.String(64), nullable=False),
        sa.Column("input_bound", sa.Integer(), nullable=False), sa.Column("output_limit", sa.Integer(), nullable=False),
        sa.Column("upper_microusd", sa.BigInteger(), nullable=False), sa.Column("actual_microusd", sa.BigInteger()),
        sa.Column("state", sa.String(24), nullable=False), sa.Column("outcome", sa.String(16)),
        sa.Column("prompt_tokens", sa.BigInteger()), sa.Column("completion_tokens", sa.BigInteger()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("dispatched_at", sa.DateTime(timezone=True)), sa.Column("unknown_at", sa.DateTime(timezone=True)),
        sa.Column("settled_at", sa.DateTime(timezone=True)), sa.Column("settlement_hash", sa.String(64)),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_rr_evaluation_attempts")),
        sa.ForeignKeyConstraint(["batch_id"], ["rr_evaluation_batches.id"], name=op.f("fk_rr_evaluation_attempts_batch_id_rr_evaluation_batches")),
        sa.UniqueConstraint("batch_id", "sample_hash", name=op.f("uq_rr_evaluation_attempts_batch_id_sample_hash")),
        sa.CheckConstraint("state IN ('reserved', 'dispatched', 'retained_unknown', 'settled', 'released', 'estimated_spent')", name=op.f("ck_rr_evaluation_attempts_state")),
        sa.CheckConstraint("input_bound > 0 AND input_bound <= 16000 AND output_limit > 0 AND output_limit <= 6000 AND upper_microusd > 0 AND (actual_microusd IS NULL OR actual_microusd >= 0)", name=op.f("ck_rr_evaluation_attempts_amounts")),
        sa.CheckConstraint("(prompt_tokens IS NULL AND completion_tokens IS NULL) OR (prompt_tokens >= 0 AND completion_tokens >= 0 AND prompt_tokens IS NOT NULL AND completion_tokens IS NOT NULL)", name=op.f("ck_rr_evaluation_attempts_tokens")))
    op.create_index("ix_rr_evaluation_recovery", "rr_evaluation_attempts", ["state", "lease_expires_at"])
    op.create_table("rr_evaluation_buckets",
        sa.Column("attempt_id", sa.Uuid(), nullable=False), sa.Column("bucket_key", sa.String(80), nullable=False),
        sa.PrimaryKeyConstraint("attempt_id", "bucket_key", name=op.f("pk_rr_evaluation_buckets")),
        sa.ForeignKeyConstraint(["attempt_id"], ["rr_evaluation_attempts.id"], name=op.f("fk_rr_evaluation_buckets_attempt_id_rr_evaluation_attempts")),
        sa.ForeignKeyConstraint(["bucket_key"], ["rr_budget_buckets.bucket_key"], name=op.f("fk_rr_evaluation_buckets_bucket_key_rr_budget_buckets")))


def downgrade():
    raise RuntimeError("Referral migrations are additive; rollback never deletes data")
