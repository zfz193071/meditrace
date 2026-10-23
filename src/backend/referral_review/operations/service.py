"""Operator metadata queries and bounded, selected-target recovery. No model calls."""
from datetime import timedelta
import time

import sqlalchemy as sa

from ..errors import ApiError
from ..lifecycle.service import Lifecycle
from ..persistence import models as m
from ..persistence.migrations import require_current_schema
from ..schemas import ErrorCode
from ..billing.provider import maintenance_deadline
from .telemetry import run_metadata, observe


class Operations:
    def __init__(self, identity, documents=None, billing=None):
        self.identity, self.engine = identity, identity.engine
        self.documents, self.billing = documents, billing
        self.lifecycle = Lifecycle(identity, documents, billing)

    def status(self, *, run_id=None, request_id=None):
        now, settings = self.identity.clock(), self.identity.settings
        with self.engine.connect() as conn:
            require_current_schema(conn)
            budgets = []
            for key, limit in ((f"day:{now:%Y-%m-%d}", settings.daily_budget_microusd),
                               (f"month:{now:%Y-%m}", settings.monthly_budget_microusd)):
                row = conn.execute(sa.select(m.budget_buckets).where(m.budget_buckets.c.bucket_key == key)).mappings().first()
                budgets.append(dict(row) | {"configured_limit_microusd": limit} if row else dict(
                    bucket_key=key, limit_microusd=limit, configured_limit_microusd=limit, reserved_microusd=0, spent_microusd=0))
            def count(table, *where):
                return conn.execute(sa.select(sa.func.count()).select_from(table).where(*where)).scalar_one()
            alerts = dict(
                financial_halt=count(m.usage_controls, m.usage_controls.c.halted.is_(True)),
                budget_overrun=count(m.budget_buckets, m.budget_buckets.c.spent_microusd +
                    m.budget_buckets.c.reserved_microusd > m.budget_buckets.c.limit_microusd),
                persistent_failures=count(m.rate_limit_buckets, m.rate_limit_buckets.c.action == "failure:86400",
                    m.rate_limit_buckets.c.window_start >= now - timedelta(days=1), m.rate_limit_buckets.c.count >= 10),
                payment_failures=count(m.billing_events, m.billing_events.c.state == "failed"),
                payment_backlog=count(m.billing_events, m.billing_events.c.state == "pending",
                    m.billing_events.c.received_at < now - timedelta(hours=1)),
                cleanup_failures=count(m.cleanup_jobs, m.cleanup_jobs.c.state == "failed"),
                cleanup_exhausted=count(m.cleanup_jobs, m.cleanup_jobs.c.state != "succeeded", m.cleanup_jobs.c.attempt_count >= 10),
                cleanup_overdue=count(m.cleanup_jobs, m.cleanup_jobs.c.state != "succeeded",
                    m.cleanup_jobs.c.next_attempt_at < now - timedelta(days=1)),
                unknown_runs=count(m.runs, m.runs.c.state == "outcome_unknown"))
            jobs = conn.execute(sa.select(m.cleanup_jobs.c.id, m.cleanup_jobs.c.kind, m.cleanup_jobs.c.state,
                m.cleanup_jobs.c.attempt_count, m.cleanup_jobs.c.next_attempt_at).where(
                m.cleanup_jobs.c.state != "succeeded").order_by(m.cleanup_jobs.c.next_attempt_at, m.cleanup_jobs.c.id).limit(20)).mappings().all()
            audits = []
            if run_id or request_id:
                query = sa.select(m.audit_events.c.request_id, m.audit_events.c.run_id, m.audit_events.c.action,
                    m.audit_events.c.created_at).where(m.audit_events.c.action.in_(
                        ["run:" + phase for phase in ("created", "execute", "cancel", "reconcile", "reserved", "dispatched", "complete", "failed", "recovered")]))
                if run_id:
                    query = query.where(m.audit_events.c.run_id == run_id)
                if request_id:
                    query = query.where(m.audit_events.c.request_id == request_id)
                audits = conn.execute(query.order_by(m.audit_events.c.created_at.desc(), m.audit_events.c.id.desc()).limit(100)).mappings().all()
                ids = {row["run_id"] for row in audits if row["run_id"]}
                if run_id:
                    ids.add(run_id)
            else:
                ids = conn.execute(sa.select(m.runs.c.id).where(m.runs.c.state == "outcome_unknown")
                    .order_by(m.runs.c.created_at, m.runs.c.id).limit(20)).scalars().all()
            runs = [data for rid in sorted(ids, key=str) if (data := run_metadata(conn, rid)) is not None]
            return dict(budgets=budgets, alerts=alerts, runs=runs, audit=[dict(row) for row in audits],
                        cleanup_jobs=[dict(row) for row in jobs], limit=20, audit_limit=100)

    def reconcile(self, rid):
        with self.engine.connect() as conn:
            require_current_schema(conn)
            if not conn.execute(sa.select(m.runs.c.id).where(m.runs.c.id == rid)).first():
                raise ApiError(ErrorCode.NOT_FOUND)
        self.lifecycle.recover_run(rid)
        observe(self.engine, rid, "reconciled")
        return self.status(run_id=rid)

    def retry_payment(self, event_id):
        if self.billing is None:
            raise ApiError(ErrorCode.BILLING_DISABLED)
        with self.engine.connect() as conn:
            require_current_schema(conn)
            if not conn.execute(sa.select(m.billing_events.c.state).where(
                    m.billing_events.c.stripe_event_id == event_id)).first():
                raise ApiError(ErrorCode.NOT_FOUND)
        context = maintenance_deadline.set(time.monotonic() + 45)
        try:
            self.billing.process_event(event_id)
        finally:
            maintenance_deadline.reset(context)
        return self.status()

    def retry_cleanup(self, job_id, *, retry_exhausted=False):
        # Only requeue a failed job. Never steal an active deletion lease or bypass
        # the domain eligibility checks. Release this lock before acquiring domain locks.
        with self.engine.begin() as conn:
            require_current_schema(conn)
            job = conn.execute(sa.select(m.cleanup_jobs).where(m.cleanup_jobs.c.id == job_id).with_for_update()).mappings().first()
            if not job:
                raise ApiError(ErrorCode.NOT_FOUND)
            if job["kind"] not in ("object", "packet", "account", "orphan"):
                raise ApiError(ErrorCode.USAGE_CONFLICT)
            if job["kind"] == "object" and self.documents is None:
                raise ApiError(ErrorCode.STORAGE_UNAVAILABLE)
            if job["state"] != "failed" or (job["attempt_count"] >= 10 and not retry_exhausted):
                raise ApiError(ErrorCode.USAGE_CONFLICT)
            conn.execute(m.cleanup_jobs.update().where(m.cleanup_jobs.c.id == job_id).values(
                state="pending", attempt_count=0 if retry_exhausted else job["attempt_count"],
                next_attempt_at=self.identity.clock(), last_error_code=None))
        if job["kind"] == "object":
            self.documents.cleanup(job["entity_id"])
        else:
            self.lifecycle.purge(job_id)
        return self.status()
