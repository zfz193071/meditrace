"""One two-slot global pool across workspace runs and evaluation attempts.

The existing workspace global rows are the shared mutex and slot identities.
An additive companion table preserves typed evaluation FKs without altering
workspace rows or their constraints. Either live holder makes a slot busy.
Caller owns its transaction and domain/budget locks. Lock account slots first
(workspace only), global workspace rows next, evaluation rows last.
"""
from datetime import timedelta

import sqlalchemy as sa

from ..errors import ApiError
from ..persistence import models as m
from ..persistence.repository import require_transaction
from ..schemas import ErrorCode
from . import rates

CAPACITY = 2
LEASE = timedelta(seconds=240)


def _global(conn):
    require_transaction(conn)
    for number in range(CAPACITY):
        rates.ensure(conn, m.concurrency_slots, {"scope": "global", "slot_number": number})
    workspace = conn.execute(sa.select(m.concurrency_slots).where(m.concurrency_slots.c.scope == "global",
        m.concurrency_slots.c.slot_number < CAPACITY).order_by(m.concurrency_slots.c.slot_number)
        .with_for_update()).mappings().all()
    for number in range(CAPACITY):
        rates.ensure(conn, m.evaluation_slots, {"slot_number": number})
    evaluation = conn.execute(sa.select(m.evaluation_slots).order_by(m.evaluation_slots.c.slot_number)
                              .with_for_update()).mappings().all()
    return list(zip(workspace, evaluation, strict=True))


def _active(row, field, now):
    return row[field] is not None and row["lease_expires_at"] > now


def _available(pairs, now):
    return next((w["slot_number"] for w, e in pairs
                 if not _active(w, "run_id", now) and not _active(e, "attempt_id", now)), None)


def claim_workspace(conn, run_id, now, lease):
    """Caller already holds the account slot; both claims commit atomically."""
    number = _available(_global(conn), now)
    if number is None:
        raise ApiError(ErrorCode.RUN_ACTIVE)
    conn.execute(m.concurrency_slots.update().where(m.concurrency_slots.c.scope == "global",
        m.concurrency_slots.c.slot_number == number).values(run_id=run_id, lease_expires_at=lease))


def require_workspace(conn, owner, run_id, now):
    """Revalidate actual slot ownership immediately before the dispatch marker."""
    account = conn.execute(sa.select(m.concurrency_slots).where(m.concurrency_slots.c.scope == f"account:{owner}")
                           .order_by(m.concurrency_slots.c.slot_number).with_for_update()).mappings().all()
    if not any(s["run_id"] == run_id and _active(s, "run_id", now) for s in account):
        raise ApiError(ErrorCode.RUN_ACTIVE)
    if not any(w["run_id"] == run_id and _active(w, "run_id", now) and not _active(e, "attempt_id", now)
               for w, e in _global(conn)):
        raise ApiError(ErrorCode.RUN_ACTIVE)


def claim_evaluation(conn, attempt_id, now):
    number = _available(_global(conn), now)
    if number is None:
        raise ApiError(ErrorCode.RUN_ACTIVE)
    lease = now + LEASE
    conn.execute(m.evaluation_slots.update().where(m.evaluation_slots.c.slot_number == number)
                 .values(attempt_id=attempt_id, lease_expires_at=lease))
    return lease


def release_evaluation(conn, attempt_id):
    # Never clear a lease reassigned while the original provider was uncertain.
    for _, e in _global(conn):
        if e["attempt_id"] == attempt_id:
            conn.execute(m.evaluation_slots.update().where(m.evaluation_slots.c.slot_number == e["slot_number"])
                         .values(attempt_id=None, lease_expires_at=None))
