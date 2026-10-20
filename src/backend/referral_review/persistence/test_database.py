"""Create/drop only disposable PostgreSQL schemas owned by this test invocation.

Never fall back to DATABASE_URL. A random marker and a connection fingerprint
must match before cleanup; guessed names and user/production schemas are rejected.
"""

import argparse
from contextlib import contextmanager
from dataclasses import asdict, dataclass
import hashlib
import json
import os
from pathlib import Path
import re
from uuid import uuid4

import sqlalchemy as sa
from sqlalchemy.engine import make_url

from .database import create_engine

__test__ = False


def test_url() -> str:
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        raise ValueError("TEST_DATABASE_URL is required; no production fallback")
    if make_url(url).get_backend_name() not in ("postgresql", "postgres"):
        raise ValueError("TEST_DATABASE_URL must be PostgreSQL")
    return url


def fingerprint(url):
    parsed = make_url(url)
    identity = json.dumps([parsed.host, parsed.port or 5432, parsed.database, parsed.username])
    return hashlib.sha256(identity.encode()).hexdigest()


@dataclass(frozen=True)
class Receipt:
    schema: str
    token: str
    database_fingerprint: str


def create_schema(url: str, *, record=None) -> Receipt:
    receipt = Receipt("rr_test_" + uuid4().hex, uuid4().hex, fingerprint(url))
    if record is not None:
        # Persist ownership before remote DDL, including a lost commit acknowledgement.
        record(receipt)
    admin = create_engine(url)
    if admin.dialect.name != "postgresql":
        raise ValueError("PostgreSQL test database required")
    try:
        with admin.begin() as connection:
            connection.execute(sa.schema.CreateSchema(receipt.schema))
            connection.exec_driver_sql(f'CREATE TABLE "{receipt.schema}"._meditrace_test_guard (token TEXT PRIMARY KEY)')
            connection.execute(sa.text(f'INSERT INTO "{receipt.schema}"._meditrace_test_guard VALUES (:token)'), {"token": receipt.token})
    finally:
        admin.dispose()
    return receipt


def drop_schema(url: str, receipt: Receipt, *, confirm: str) -> None:
    if not re.fullmatch(r"rr_test_[0-9a-f]{32}", receipt.schema) or confirm != receipt.schema:
        raise ValueError("Exact generated test schema confirmation required")
    if receipt.database_fingerprint != fingerprint(url) or not re.fullmatch(r"[0-9a-f]{32}", receipt.token):
        raise ValueError("Test database ownership mismatch")
    admin = create_engine(url)
    try:
        with admin.begin() as connection:
            # Missing/mismatched marker is a hard stop, not an invitation to force-drop.
            marker = connection.execute(sa.text(f'SELECT token FROM "{receipt.schema}"._meditrace_test_guard')).scalars().all()
            if marker != [receipt.token]:
                raise ValueError("Test schema ownership marker mismatch")
            connection.execute(sa.schema.DropSchema(receipt.schema, cascade=True))
    finally:
        admin.dispose()


@contextmanager
def isolated_database(url: str):
    receipt = create_schema(url)
    engine = create_engine(url, schema=receipt.schema)
    try:
        yield engine
    finally:
        engine.dispose()
        drop_schema(url, receipt, confirm=receipt.schema)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    create = commands.add_parser("create")
    create.add_argument("--receipt", required=True, type=Path)
    drop = commands.add_parser("drop")
    drop.add_argument("--receipt", required=True, type=Path)
    drop.add_argument("--confirm-schema", required=True)
    args = parser.parse_args()
    try:
        url = test_url()
        if args.command == "create":
            # Exclusive creation prevents overwriting an earlier cleanup receipt.
            with args.receipt.open("x", encoding="utf-8") as output:
                os.chmod(args.receipt, 0o600)
                def record(receipt):
                    json.dump(asdict(receipt), output)
                    output.write("\n")
                    output.flush()
                    os.fsync(output.fileno())
                receipt = create_schema(url, record=record)
            print(f"Created isolated schema: {receipt.schema}")
        else:
            receipt = Receipt(**json.loads(args.receipt.read_text()))
            drop_schema(url, receipt, confirm=args.confirm_schema)
            print(f"Dropped only owned test schema: {receipt.schema}; test data cannot be recovered")
    except Exception:
        # Drivers may embed URL/SQL in exception strings; never echo credentials.
        parser.exit(1, "Test schema operation failed; check TEST_DATABASE_URL, receipt and exact confirmation.\n")


if __name__ == "__main__":
    main()
