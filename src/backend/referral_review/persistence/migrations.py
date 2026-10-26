"""Reviewed additive migration runner; invoked explicitly, never during startup."""

from pathlib import Path

from alembic import command
from alembic.config import Config
import sqlalchemy as sa

HEAD = "rr_0009"
REVIEWED_REVISIONS = frozenset({"rr_0001", "rr_0002", "rr_0003", "rr_0004", "rr_0005", "rr_0006", "rr_0007", "rr_0008", HEAD})
VERSION_TABLE = "rr_alembic_version"
SCRIPTS = Path(__file__).resolve().parents[2] / "migrations_referral"


class MigrationRequired(RuntimeError):
    pass


def configuration(connection=None) -> Config:
    config = Config()
    config.set_main_option("script_location", str(SCRIPTS))
    if connection is not None:
        config.attributes["connection"] = connection
    return config


def current_revision(connection) -> str | None:
    if not sa.inspect(connection).has_table(VERSION_TABLE):
        return None
    versions = connection.execute(sa.text(f"SELECT version_num FROM {VERSION_TABLE}")).scalars().all()
    if len(versions) != 1:
        raise MigrationRequired("Referral migration version is missing or ambiguous")
    return versions[0]


def require_current_schema(connection) -> str:
    if current_revision(connection) != HEAD:
        raise MigrationRequired("Referral schema migration required")
    return HEAD


def upgrade(connection, target: str) -> None:
    if target not in REVIEWED_REVISIONS:
        raise ValueError("Migration target is not reviewed")
    if not connection.in_transaction():
        raise ValueError("Migrations require a caller-owned transaction")
    # Serialize concurrent deployment migrations before inspecting the version.
    if connection.dialect.name == "postgresql":
        connection.execute(sa.text("SELECT pg_advisory_xact_lock(72831001)"))
    current = current_revision(connection)
    if current not in (None, *REVIEWED_REVISIONS) or (current is not None and current > target):
        raise MigrationRequired("Unknown schema version; refusing automatic change")
    if current is None:
        # Do not adopt pre-existing unmanaged rr_* tables as a successful migration.
        if any(name.startswith("rr_") for name in sa.inspect(connection).get_table_names()):
            raise MigrationRequired("Unversioned referral tables require manual inspection")
    command.upgrade(configuration(connection), target)
