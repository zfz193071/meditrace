"""Alembic accepts only an explicitly supplied connection; never read DATABASE_URL."""

from alembic import context
from referral_review.persistence.models import metadata, UTCDateTime

connection = context.config.attributes.get("connection")
if connection is None:
    raise RuntimeError("Use the explicit referral migration runner; no default database is allowed")


def render_item(kind, obj, _context):
    if kind == "type" and isinstance(obj, UTCDateTime):
        return "sa.DateTime(timezone=True)"
    return False


def include_object(obj, name, kind, reflected, compare_to):
    # Autogenerate must never propose deletion of legacy tables.
    if kind == "table":
        return name.startswith("rr_") and name != "rr_alembic_version"
    return True


context.configure(connection=connection, target_metadata=metadata,
                  version_table="rr_alembic_version", transactional_ddl=True,
                  render_item=render_item, include_object=include_object)
with context.begin_transaction():
    context.run_migrations()
