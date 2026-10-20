"""Explicit engine and transaction ownership; no dotenv or legacy DB fallback."""

from contextlib import contextmanager

import sqlalchemy as sa
from sqlalchemy.engine import make_url
from sqlalchemy.pool import NullPool, StaticPool


def create_engine(url: str, *, schema: str | None = None) -> sa.Engine:
    parsed = make_url(url)
    if parsed.drivername == "postgres":
        parsed = parsed.set(drivername="postgresql+psycopg2")
    if parsed.get_backend_name() not in ("postgresql", "sqlite"):
        raise ValueError("Only PostgreSQL and SQLite are supported")
    options = {"hide_parameters": True, "echo": False, "poolclass": NullPool}
    if parsed.get_backend_name() == "postgresql":
        # Schema is an identifier, never an unchecked SQL string.
        if schema:
            import re
            if not re.fullmatch(r"rr_test_[0-9a-f]{32}", schema):
                raise ValueError("Invalid isolated test schema")
        settings = "-c timezone=UTC -c lock_timeout=5000 -c statement_timeout=15000"
        if schema:
            settings += f" -c search_path={schema}"  # No public fallback.
        options["connect_args"] = {"connect_timeout": 10, "options": settings}
    elif schema:
        raise ValueError("SQLite has no PostgreSQL test schema")
    elif parsed.database in (None, "", ":memory:"):
        # A memory database must survive successive unit-of-work connections.
        # This is only a sequential test convenience, never a PostgreSQL lock fake.
        options["poolclass"] = StaticPool
    engine = sa.create_engine(parsed, **options)
    if engine.dialect.name == "sqlite":
        @sa.event.listens_for(engine, "connect")
        def configure_sqlite(dbapi, _record):
            # Explicit BEGIN makes DDL rollback transactional on Python's sqlite3.
            dbapi.isolation_level = None
            dbapi.execute("PRAGMA foreign_keys=ON")
            dbapi.execute("PRAGMA busy_timeout=5000")

        @sa.event.listens_for(engine, "begin")
        def begin_sqlite(connection):
            connection.exec_driver_sql("BEGIN")
    return engine


@contextmanager
def transaction(engine: sa.Engine):
    """One connection/transaction; rollback on every exception, no implicit retries.

    External model/storage/payment calls must be outside this context. This is
    intentionally a Core Connection, not a generic per-table repository framework.
    """
    with engine.begin() as connection:
        yield connection
