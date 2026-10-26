"""Append late evaluation usage corrections without replacing settlements."""
from alembic import op
import sqlalchemy as sa

revision = "rr_0009"
down_revision = "rr_0008"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("rr_evaluation_adjustments",
        sa.Column("id", sa.Uuid(), nullable=False), sa.Column("attempt_id", sa.Uuid(), nullable=False),
        sa.Column("adjustment_key", sa.String(100), nullable=False),
        sa.Column("prompt_tokens", sa.BigInteger(), nullable=False),
        sa.Column("completion_tokens", sa.BigInteger(), nullable=False),
        sa.Column("actual_microusd", sa.BigInteger(), nullable=False),
        sa.Column("delta_microusd", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_rr_evaluation_adjustments")),
        sa.ForeignKeyConstraint(["attempt_id"], ["rr_evaluation_attempts.id"], name=op.f("fk_rr_evaluation_adjustments_attempt_id_rr_evaluation_attempts")),
        sa.UniqueConstraint("attempt_id", "adjustment_key", name=op.f("uq_rr_evaluation_adjustments_attempt_id_adjustment_key")),
        sa.CheckConstraint("actual_microusd >= 0 AND prompt_tokens >= 0 AND completion_tokens >= 0", name=op.f("ck_rr_evaluation_adjustments_amounts")))
    if op.get_bind().dialect.name == "postgresql":
        op.execute("CREATE TRIGGER rr_immutable BEFORE UPDATE OR DELETE ON rr_evaluation_adjustments FOR EACH ROW EXECUTE FUNCTION rr_reject_immutable_update()")
    else:
        for action in ("UPDATE", "DELETE"):
            op.execute(f"CREATE TRIGGER rr_evaluation_adjustments_no_{action.lower()} BEFORE {action} ON rr_evaluation_adjustments BEGIN SELECT RAISE(ABORT, 'Evaluation adjustments are append-only'); END")


def downgrade():
    raise RuntimeError("Referral migrations are additive; rollback never deletes data")
