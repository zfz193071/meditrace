"""Append minimal Checkout recovery data; never retain full payment events."""
from alembic import op
import sqlalchemy as sa

revision = "rr_0006"
down_revision = "rr_0005"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("rr_checkout_details",
        sa.Column("order_id", sa.Uuid(), nullable=False),
        sa.Column("return_path", sa.String(200), nullable=False),
        sa.Column("checkout_url", sa.Text()),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("order_id", name=op.f("pk_rr_checkout_details")),
        sa.ForeignKeyConstraint(["order_id"], ["rr_orders.id"], name=op.f("fk_rr_checkout_details_order_id_rr_orders")))


def downgrade():
    raise RuntimeError("Referral migrations are additive; rollback never deletes data")
