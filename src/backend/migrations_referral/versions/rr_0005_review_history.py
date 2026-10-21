"""Append immutable reviewer history, retaining every handoff draft edit."""
from alembic import op
import sqlalchemy as sa

revision = "rr_0005"
down_revision = "rr_0004"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("rr_review_events",
        sa.Column("id", sa.Uuid(), nullable=False), sa.Column("packet_id", sa.Uuid(), nullable=False),
        sa.Column("revision_id", sa.Uuid(), nullable=False), sa.Column("run_id", sa.Uuid()),
        sa.Column("actor_id", sa.Uuid(), nullable=False), sa.Column("review_version", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(20), nullable=False), sa.Column("content", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_rr_review_events")),
        sa.ForeignKeyConstraint(["packet_id", "actor_id"], ["rr_packets.id", "rr_packets.owner_id"], name=op.f("fk_rr_review_events_packet_id_actor_id_rr_packets")),
        sa.ForeignKeyConstraint(["revision_id", "packet_id"], ["rr_revisions.id", "rr_revisions.packet_id"], name=op.f("fk_rr_review_events_revision_id_packet_id_rr_revisions")),
        sa.ForeignKeyConstraint(["run_id", "packet_id", "revision_id"], ["rr_runs.id", "rr_runs.packet_id", "rr_runs.revision_id"], name=op.f("fk_rr_review_events_run_id_packet_id_revision_id_rr_runs")),
        sa.UniqueConstraint("packet_id", "review_version", name=op.f("uq_rr_review_events_packet_id_review_version")),
        sa.CheckConstraint("review_version > 0", name=op.f("ck_rr_review_events_version")),
        sa.CheckConstraint("kind IN ('resolution', 'draft', 'confirmation')", name=op.f("ck_rr_review_events_kind")))
    op.create_index("ix_rr_review_events_packet_created_id", "rr_review_events", ["packet_id", "created_at", "id"])
    if op.get_bind().dialect.name == "postgresql":
        op.execute("CREATE TRIGGER rr_immutable BEFORE UPDATE ON rr_review_events FOR EACH ROW EXECUTE FUNCTION rr_reject_immutable_update()")
    else:
        op.execute("CREATE TRIGGER rr_review_events_immutable BEFORE UPDATE ON rr_review_events BEGIN SELECT RAISE(ABORT, 'Review history is immutable'); END")


def downgrade():
    raise RuntimeError("Referral migrations are additive; rollback never deletes data")
