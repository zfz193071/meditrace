"""Append typed evaluation holders for the existing two global slot identities."""
from alembic import op
import sqlalchemy as sa

revision = "rr_0008"
down_revision = "rr_0007"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("rr_evaluation_slots",
        sa.Column("slot_number", sa.Integer(), nullable=False),
        sa.Column("attempt_id", sa.Uuid()), sa.Column("lease_expires_at", sa.DateTime(timezone=True)),
        sa.PrimaryKeyConstraint("slot_number", name=op.f("pk_rr_evaluation_slots")),
        sa.UniqueConstraint("attempt_id", name=op.f("uq_rr_evaluation_slots_attempt_id")),
        sa.ForeignKeyConstraint(["attempt_id"], ["rr_evaluation_attempts.id"], name=op.f("fk_rr_evaluation_slots_attempt_id_rr_evaluation_attempts")),
        sa.CheckConstraint("slot_number >= 0 AND slot_number < 2", name=op.f("ck_rr_evaluation_slots_slot")),
        sa.CheckConstraint("(attempt_id IS NULL AND lease_expires_at IS NULL) OR (attempt_id IS NOT NULL AND lease_expires_at IS NOT NULL)", name=op.f("ck_rr_evaluation_slots_lease")))


def downgrade():
    raise RuntimeError("Referral migrations are additive; rollback never deletes data")
