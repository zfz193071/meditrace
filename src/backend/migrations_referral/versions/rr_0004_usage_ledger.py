"""Append pricing snapshots, circuit breaker and immutable cost adjustments."""
from alembic import op
import sqlalchemy as sa

revision = "rr_0004"
down_revision = "rr_0003"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("rr_usage_details",
        sa.Column("reservation_id", sa.Uuid(), nullable=False),
        sa.Column("mode", sa.String(10), nullable=False), sa.Column("model", sa.String(200), nullable=False),
        sa.Column("input_bound", sa.Integer(), nullable=False), sa.Column("output_limit", sa.Integer(), nullable=False),
        sa.Column("input_price", sa.BigInteger(), nullable=False), sa.Column("output_price", sa.BigInteger(), nullable=False),
        sa.Column("outcome", sa.String(16)), sa.Column("unknown_at", sa.DateTime(timezone=True)),
        sa.Column("settled_at", sa.DateTime(timezone=True)), sa.Column("settlement_hash", sa.String(64)),
        sa.PrimaryKeyConstraint("reservation_id", name=op.f("pk_rr_usage_details")),
        sa.ForeignKeyConstraint(["reservation_id"], ["rr_usage_reservations.id"], name=op.f("fk_rr_usage_details_reservation_id_rr_usage_reservations")),
        sa.CheckConstraint("mode IN ('fake', 'real')", name=op.f("ck_rr_usage_details_mode")),
        sa.CheckConstraint("input_bound > 0 AND input_bound <= 16000 AND output_limit > 0 AND output_limit <= 6000 AND input_price >= 0 AND output_price >= 0", name=op.f("ck_rr_usage_details_limits")))
    op.create_table("rr_usage_controls",
        sa.Column("key", sa.String(30), nullable=False), sa.Column("halted", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("reason", sa.String(80)), sa.PrimaryKeyConstraint("key", name=op.f("pk_rr_usage_controls")))
    op.create_table("rr_usage_adjustments",
        sa.Column("id", sa.Uuid(), nullable=False), sa.Column("reservation_id", sa.Uuid(), nullable=False),
        sa.Column("adjustment_key", sa.String(100), nullable=False), sa.Column("actual_microusd", sa.BigInteger(), nullable=False),
        sa.Column("delta_microusd", sa.BigInteger(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_rr_usage_adjustments")),
        sa.ForeignKeyConstraint(["reservation_id"], ["rr_usage_reservations.id"], name=op.f("fk_rr_usage_adjustments_reservation_id_rr_usage_reservations")),
        sa.UniqueConstraint("reservation_id", "adjustment_key", name=op.f("uq_rr_usage_adjustments_reservation_id_adjustment_key")),
        sa.CheckConstraint("actual_microusd >= 0", name=op.f("ck_rr_usage_adjustments_amount")))


def downgrade():
    raise RuntimeError("Referral migrations are additive; rollback never deletes data")
