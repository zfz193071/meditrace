"""Shared UTC fixed-window counters. Lock account before all counters; no process state."""
from datetime import timezone

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from ..errors import ApiError
from ..schemas import ErrorCode
from ..persistence import models as m

LIMITS = {"checkout": ((60, 5), (3600, 20)), "execute": ((60, 3), (3600, 20)), "upload": ((60, 10), (3600, 50)),
          "export": ((60, 10), (3600, 60))}


def ensure(conn, table, values):
    insert = pg_insert if conn.dialect.name == "postgresql" else sqlite_insert
    conn.execute(insert(table).values(**values).on_conflict_do_nothing())


def lock_user(conn, owner):
    if not conn.execute(sa.select(m.users.c.id).where(m.users.c.id == owner,
        m.users.c.disabled_at.is_(None)).with_for_update()).first():
        raise ApiError(ErrorCode.AUTH_REQUIRED)


def window(now, seconds):
    return type(now).fromtimestamp(int(now.timestamp()) // seconds * seconds, timezone.utc)


def _key(owner, action, now, seconds):
    return dict(scope=f"account:{owner}", action=f"{action}:{seconds}", window_start=window(now, seconds))


def count(conn, owner, action, now, seconds=86400):
    key = _key(owner, action, now, seconds)
    return conn.execute(sa.select(m.rate_limit_buckets.c.count).filter_by(**key)).scalar_one_or_none() or 0


def increment(conn, owner, action, now, seconds=86400):
    key = _key(owner, action, now, seconds)
    ensure(conn, m.rate_limit_buckets, key | {"count": 0})
    conn.execute(m.rate_limit_buckets.update().filter_by(**key).values(count=m.rate_limit_buckets.c.count + 1))


def check_failures(conn, owner, now):
    if count(conn, owner, "failure", now) >= 10:
        raise ApiError(ErrorCode.RATE_LIMITED)


def consume(conn, owner, action, now):
    # Caller commits this transaction even when a subsequent operation is rejected.
    lock_user(conn, owner)
    if action == "execute":
        check_failures(conn, owner, now)
    for seconds, limit in LIMITS[action]:
        if count(conn, owner, action, now, seconds) >= limit:
            raise ApiError(ErrorCode.RATE_LIMITED)
    for seconds, _ in LIMITS[action]:
        increment(conn, owner, action, now, seconds)
