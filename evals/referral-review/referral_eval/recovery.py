"""Recovery CLI for an owned disposable PostgreSQL schema and private journal.

No production DATABASE_URL fallback, migration, schema creation, provider or retry.
Preview is enforced read-only by PostgreSQL. --apply requires the exact plan hash.
"""
import argparse
from contextlib import contextmanager
import json
import os
from pathlib import Path
import re
import stat

import sqlalchemy as sa

from . import planning as p
from .coordinator import reconcile, snapshot
from .files import unique_json
from .journal import Journal
from referral_review.config import Settings
from referral_review.evaluation.ledger import EvaluationLedger
from referral_review.persistence.database import create_engine
from referral_review.persistence.migrations import require_current_schema
from referral_review.persistence.test_database import Receipt, fingerprint, test_url


def ownership(path):
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(descriptor, "rb") as file:
        info = os.fstat(file.fileno())
        if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_uid != os.getuid()
            or stat.S_IMODE(info.st_mode) & 0o077 or info.st_size > 4096):
            raise ValueError("Private ownership receipt required")
        body = file.read(4097)
    if len(body) > 4096:
        raise ValueError("Oversized receipt")
    receipt = Receipt(**unique_json(body))
    if (not isinstance(receipt.schema, str) or not re.fullmatch(r"rr_test_[0-9a-f]{32}", receipt.schema)
        or not isinstance(receipt.token, str) or not re.fullmatch(r"[0-9a-f]{32}", receipt.token)):
        raise ValueError("Invalid ownership receipt")
    return receipt


@contextmanager
def owned_engine(receipt, *, apply):
    url = test_url()
    if receipt.database_fingerprint != fingerprint(url):
        raise ValueError("Database ownership mismatch")
    engine = create_engine(url, schema=receipt.schema)
    try:
        if not apply:
            @sa.event.listens_for(engine, "begin")
            def read_only(connection):
                connection.exec_driver_sql("SET TRANSACTION READ ONLY")
        with engine.begin() as conn:
            marker = conn.execute(sa.text("SELECT token FROM _meditrace_test_guard")).scalars().all()
            if marker != [receipt.token]:
                raise ValueError("Schema ownership mismatch")
            require_current_schema(conn)
        yield engine
    finally:
        engine.dispose()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", required=True, type=Path)
    parser.add_argument("--database-receipt", required=True, type=Path,
                        help="Private receipt from persistence.test_database create")
    parser.add_argument("--apply", action="store_true", help="Reconcile this plan only; never retry a model")
    parser.add_argument("--confirm-plan", help="Exact plan SHA-256 required with --apply")
    args = parser.parse_args(argv)
    try:
        plan = p.read_plan(args.plan)
        if (args.apply and args.confirm_plan != plan.sha256) or (not args.apply and args.confirm_plan is not None):
            raise ValueError("Exact plan confirmation required only for apply")
        receipt = ownership(args.database_receipt)
        with Journal(plan, resume=True) as journal, owned_engine(receipt, apply=args.apply) as engine:
            # Fixed test settings: no environment secrets, invitation or price reload.
            ledger = EvaluationLedger(engine, Settings(RR_ENVIRONMENT="test"))
            result = reconcile(ledger, plan, journal) if args.apply else snapshot(ledger, plan, journal)
        print(json.dumps(dict(operation="reconcile" if args.apply else "preview", **result), sort_keys=True))
    except Exception:
        # Driver/validation errors can contain credentials, paths or source payloads.
        parser.exit(1, "Evaluation recovery failed; check plan, private journal, isolated database receipt and confirmation.\n")


if __name__ == "__main__":
    main()
