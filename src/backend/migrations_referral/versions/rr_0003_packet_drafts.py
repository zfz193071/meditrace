"""Packet synthetic acknowledgment and resumable non-content draft metadata.

Revision: rr_0003
"""

from alembic import op
import sqlalchemy as sa

revision = "rr_0003"
down_revision = "rr_0002"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("rr_packets", sa.Column("synthetic_ack_at", sa.DateTime(timezone=True), nullable=True))
    op.create_table("rr_packet_drafts",
        sa.Column("packet_id", sa.Uuid(), nullable=False),
        sa.Column("selected_document_ids", sa.JSON(), nullable=False),
        sa.Column("last_location", sa.String(32), nullable=False),
        sa.Column("base_revision", sa.Integer(), nullable=False),
        sa.Column("draft_version", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("base_revision >= 0 AND draft_version >= 0", name=op.f("ck_rr_packet_drafts_versions")),
        sa.CheckConstraint("last_location IN ('documents', 'review', 'handoff')", name=op.f("ck_rr_packet_drafts_last_location")),
        sa.ForeignKeyConstraint(["packet_id"], ["rr_packets.id"], name=op.f("fk_rr_packet_drafts_packet_id_rr_packets")),
        sa.PrimaryKeyConstraint("packet_id", name=op.f("pk_rr_packet_drafts")))


def downgrade():
    raise RuntimeError("Referral migrations are additive; application rollback never deletes data")
