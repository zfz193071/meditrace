"""Persist file/page parse failures without rewriting frozen rr_0001.

Revision: rr_0002
"""

from alembic import op
import sqlalchemy as sa

revision = "rr_0002"
down_revision = "rr_0001"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("rr_documents", sa.Column("page_count", sa.Integer(), nullable=True))
    op.add_column("rr_documents", sa.Column("parse_error_code", sa.String(40), nullable=True))
    op.add_column("rr_documents", sa.Column("parse_error_page", sa.Integer(), nullable=True))
    if op.get_bind().dialect.name == "postgresql":
        op.create_check_constraint("ck_rr_documents_page_count", "rr_documents",
                                   "page_count IS NULL OR page_count >= 1")
        op.create_check_constraint("ck_rr_documents_parse_error_page", "rr_documents",
                                   "parse_error_page IS NULL OR parse_error_page >= 1")
        op.execute("""CREATE OR REPLACE FUNCTION rr_protect_ready_document() RETURNS trigger
            LANGUAGE plpgsql AS $$ BEGIN
                IF OLD.parse_status = 'ready' AND
                   ROW(NEW.id, NEW.packet_id, NEW.owner_id, NEW.kind, NEW.filename, NEW.sha256,
                       NEW.storage_key, NEW.byte_size, NEW.parser_version, NEW.parse_status,
                       NEW.page_count, NEW.parse_error_code, NEW.parse_error_page)
                   IS DISTINCT FROM
                   ROW(OLD.id, OLD.packet_id, OLD.owner_id, OLD.kind, OLD.filename, OLD.sha256,
                       OLD.storage_key, OLD.byte_size, OLD.parser_version, OLD.parse_status,
                       OLD.page_count, OLD.parse_error_code, OLD.parse_error_page) THEN
                    RAISE EXCEPTION 'Ready document content is immutable' USING ERRCODE = '23514';
                END IF;
                RETURN NEW;
            END; $$""")
    elif op.get_bind().dialect.name == "sqlite":
        op.execute("DROP TRIGGER rr_document_content")
        columns = ("id", "packet_id", "owner_id", "kind", "filename", "sha256",
                   "storage_key", "byte_size", "parser_version", "parse_status",
                   "page_count", "parse_error_code", "parse_error_page")
        changed = " OR ".join(f"NEW.{column} IS NOT OLD.{column}" for column in columns)
        op.execute("CREATE TRIGGER rr_document_content BEFORE UPDATE ON rr_documents "
                   f"WHEN OLD.parse_status = 'ready' AND ({changed}) "
                   "BEGIN SELECT RAISE(ABORT, 'Ready document content is immutable'); END")
    else:
        raise RuntimeError("Unsupported migration dialect")


def downgrade():
    raise RuntimeError("Referral migrations are additive; application rollback never deletes data")
