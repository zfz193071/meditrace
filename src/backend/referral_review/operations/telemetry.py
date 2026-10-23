"""Allowlisted metadata only. Never serialize requests, provider objects or exceptions."""
from contextvars import ContextVar
from hashlib import sha256
import json
import logging
from uuid import UUID, uuid4

import sqlalchemy as sa

from ..persistence import models as m
from ..schemas import ErrorCode

request_id = ContextVar("referral_request_id", default=None)
logger = logging.getLogger("meditrace.referral.telemetry")
logger.setLevel(logging.INFO)
CODES = {code.value for code in ErrorCode} | {
    "MODEL_TIMEOUT", "MODEL_UNAVAILABLE", "MODEL_INVALID_OUTPUT", "MODEL_TRUNCATED", "EXECUTION_INTERRUPTED",
    "LEASE_EXPIRED", "PENDING_EXPIRED", "SOURCE_DELETED", "UNCLASSIFIED",
}
PHASES = {"request", "reserved", "dispatched", "complete", "reconciled", "observation_unavailable"}


def digest(value):
    return sha256(value.encode()).hexdigest() if isinstance(value, str) else None


def safe_code(value):
    return value if value in CODES else "UNCLASSIFIED" if value else None


def emit(phase, *, run_id=None, duration_ms=None, status=None, error_code=None, metadata=None):
    # metadata is built by run_metadata below, never passed through from a request.
    record = {"event": "referral", "request_id": str(request_id.get() or uuid4()),
              "phase": phase if phase in PHASES else "observation_unavailable",
              "error_code": safe_code(error_code)}
    if isinstance(run_id, UUID):
        record["run_id"] = str(run_id)
    for key, value in (("duration_ms", duration_ms), ("status", status)):
        if type(value) is int and value >= 0:
            record[key] = value
    if metadata:
        record.update(metadata)
    try:
        logger.info(json.dumps(record, sort_keys=True))
    except Exception:
        pass  # Logging failures must never change execution/settlement outcomes.


def audit(conn, row, phase, now):
    """Commit correlation in the same transaction as state/ledger changes."""
    conn.execute(m.audit_events.insert().values(actor_id=None, packet_id=row["packet_id"],
        revision_id=row["revision_id"], run_id=row["id"], action="run:" + phase,
        request_id=request_id.get() or uuid4(), created_at=now))


def run_metadata(conn, rid):
    row = conn.execute(sa.select(m.runs).where(m.runs.c.id == rid)).mappings().first()
    if row is None:
        return None
    data = {"run_id": str(row["id"]), "state": row["state"], "mode": row["mode"],
            "error_code": safe_code(row["error_code"]),
            "model_requested_sha256": digest(row["model_requested"]),
            "model_reported_sha256": digest(row["model_reported"])}
    usage = row["usage"] if isinstance(row["usage"], dict) else {}
    for key in ("prompt_tokens", "completion_tokens", "total_tokens"):
        value = usage.get(key)
        data[key] = value if type(value) is int and value >= 0 else None
    reservation = conn.execute(sa.select(m.usage_reservations).where(
        m.usage_reservations.c.run_id == rid)).mappings().first()
    data.update(reservation_id=None, usage_state=None, estimated_microusd=None,
                actual_microusd=None, booked_microusd=None, adjustment_count=0, price_version_sha256=None)
    if reservation:
        adjustments, delta = conn.execute(sa.select(sa.func.count(), sa.func.coalesce(
            sa.func.sum(m.usage_adjustments.c.delta_microusd), 0)).where(
            m.usage_adjustments.c.reservation_id == reservation["id"])).one()
        booked = reservation["actual_microusd"]
        if booked is not None:
            booked += delta
        data.update(reservation_id=str(reservation["id"]), usage_state=reservation["state"],
            estimated_microusd=reservation["cost_upper_bound_microusd"],
            actual_microusd=booked if reservation["state"] in ("settled", "released") or adjustments else None,
            booked_microusd=booked, adjustment_count=adjustments, price_version_sha256=digest(reservation["price_version"]))
    return data


def observe(engine, rid, phase, duration_ms=None):
    try:
        with engine.connect() as conn:
            data = run_metadata(conn, rid)
        emit(phase, run_id=rid, duration_ms=duration_ms, metadata=data)
    except Exception:
        emit("observation_unavailable", run_id=rid, duration_ms=duration_ms)
