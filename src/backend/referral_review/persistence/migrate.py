"""Explicit reviewed migration command. No environment file or default database."""

import argparse
import os
from sqlalchemy.engine import make_url

from .database import create_engine
from .migrations import REVIEWED_REVISIONS, current_revision, upgrade


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database-env", required=True, choices=["TEST_DATABASE_URL", "DATABASE_URL"])
    parser.add_argument("--schema", help="Generated test schema; never public or a user schema")
    parser.add_argument("--target", choices=sorted(REVIEWED_REVISIONS))
    parser.add_argument("--apply", action="store_true", help="Without this flag only inspect version")
    parser.add_argument("--confirm-production", action="store_true")
    args = parser.parse_args()
    if args.apply and not args.target:
        parser.error("--apply requires an explicit reviewed --target")
    if args.database_env == "DATABASE_URL" and (args.schema or (args.apply and not args.confirm_production)):
        parser.error("Production changes require --confirm-production and no test schema override")
    if args.database_env == "TEST_DATABASE_URL" and not args.schema:
        parser.error("Test migrations require an explicitly generated --schema")
    url = os.environ.get(args.database_env)
    if not url:
        parser.error("The requested database variable is not configured")
    engine = None
    try:
        if make_url(url).get_backend_name() not in ("postgresql", "postgres"):
            raise ValueError("Operational migrations require PostgreSQL; SQLite is test-only")
        engine = create_engine(url, schema=args.schema)
        with engine.begin() as connection:
            if args.schema:
                # Ensure search_path resolved to this schema, never the default schema.
                actual = connection.exec_driver_sql("SELECT current_schema()").scalar_one()
                if actual != args.schema:
                    raise ValueError("Test schema is missing")
            if args.apply:
                upgrade(connection, args.target)
            version = current_revision(connection)
        print(f"Referral schema version: {version or 'uninitialized'}")
    except Exception:
        parser.exit(1, "Migration failed; inspect schema version before retrying, especially after connection loss.\n")
    finally:
        if engine is not None:
            engine.dispose()


if __name__ == "__main__":
    main()
