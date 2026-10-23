"""Durable deletion, content erasure and bounded maintenance. No model dispatch.

Lock order is user -> packet -> ledger/storage -> cleanup job. External object
deletes use Documents' durable lease, outside transactions. Empty run shells
survive only while their already-dispatched costs still need reconciliation.
"""
from datetime import timedelta
import time

import sqlalchemy as sa

from ..errors import ApiError
from ..packets import Packets
from ..persistence import models as m
from ..persistence.migrations import require_current_schema
from ..schemas import ErrorCode
from ..usage import Usage

ACTIVE_USAGE = ("reserved", "retained_unknown")


class Deferred(Exception):
    """A dependency is still in flight; this is not a failed purge attempt."""


class Lifecycle:
    def __init__(self, identity, documents=None, billing=None):
        self.identity, self.engine, self.clock = identity, identity.engine, identity.clock
        self.documents, self.billing = documents, billing
        self.packets, self.usage = Packets(identity), Usage(identity)

    def _enqueue(self, conn, kind, entity):
        # Caller holds the corresponding user/packet lock.
        if not conn.execute(sa.select(m.cleanup_jobs.c.id).where(
                m.cleanup_jobs.c.kind == kind, m.cleanup_jobs.c.entity_id == entity,
                m.cleanup_jobs.c.state != "succeeded")).first():
            conn.execute(m.cleanup_jobs.insert().values(kind=kind, entity_id=entity,
                state="pending", next_attempt_at=self.clock()))

    def _tombstone(self, conn, packet):
        if packet["deleted_at"] is None:
            conn.execute(m.packets.update().where(m.packets.c.id == packet["id"]).values(
                deleted_at=self.clock(), updated_at=self.clock()))
        self._enqueue(conn, "packet", packet["id"])

    def delete_account(self, token, key):
        with self.engine.begin() as conn:
            owner = self.packets._user(conn, token)
            self.packets._previous(conn, owner, "account:delete", key, {})
            conn.execute(m.users.update().where(m.users.c.id == owner).values(
                disabled_at=self.clock(), display_name="Deleted account"))
            conn.execute(m.sessions.update().where(m.sessions.c.user_id == owner).values(revoked_at=self.clock()))
            conn.execute(m.memberships.update().where(m.memberships.c.owner_id == owner,
                m.memberships.c.revoked_at.is_(None)).values(revoked_at=self.clock()))
            conn.execute(m.orders.update().where(m.orders.c.owner_id == owner,
                m.orders.c.state == "pending").values(state="revoked"))
            for packet in conn.execute(sa.select(m.packets).where(m.packets.c.owner_id == owner)
                                       .order_by(m.packets.c.id).with_for_update()).mappings():
                self._tombstone(conn, packet)
            self._enqueue(conn, "account", owner)

    def _lock_packet(self, conn, pid):
        owner = conn.execute(sa.select(m.packets.c.owner_id).where(m.packets.c.id == pid)).scalar_one_or_none()
        if owner is None:
            return None
        conn.execute(sa.select(m.users.c.id).where(m.users.c.id == owner).with_for_update()).first()
        return conn.execute(sa.select(m.packets).where(m.packets.c.id == pid).with_for_update()).mappings().first()

    def expire(self, pid):
        with self.engine.begin() as conn:
            packet = self._lock_packet(conn, pid)
            if packet and packet["expires_at"] <= self.clock():
                self._tombstone(conn, packet)

    def _scrub(self, conn, packet):
        """Remove all content, including every historical review, before waiting on costs."""
        pid = packet["id"]
        rids = sa.select(m.runs.c.id).where(m.runs.c.packet_id == pid)
        for table, predicate in ((m.review_events, m.review_events.c.packet_id == pid),
                                 (m.review_snapshots, m.review_snapshots.c.packet_id == pid),
                                 (m.resolutions, m.resolutions.c.run_id.in_(rids))):
            conn.execute(m.idempotency.delete().where(m.idempotency.c.resource_id.in_(
                sa.select(table.c.id).where(predicate))))
        for table in (m.resolution_evidence, m.resolutions, m.finding_facts, m.finding_evidence,
                      m.finding_documents, m.fact_evidence, m.findings, m.facts, m.evidence):
            conn.execute(table.delete().where(table.c.run_id.in_(rids)))
        for table in (m.review_events, m.review_snapshots, m.handoff_drafts, m.packet_drafts):
            conn.execute(table.delete().where(table.c.packet_id == pid))
        conn.execute(m.audit_events.delete().where(sa.or_(m.audit_events.c.packet_id == pid,
            m.audit_events.c.run_id.in_(rids), m.audit_events.c.revision_id.in_(
                sa.select(m.revisions.c.id).where(m.revisions.c.packet_id == pid)))))
        conn.execute(m.document_pages.delete().where(m.document_pages.c.document_id.in_(
            sa.select(m.documents.c.id).where(m.documents.c.packet_id == pid))))
        conn.execute(m.documents.update().where(m.documents.c.packet_id == pid).values(
            deleted_at=self.clock()))
        conn.execute(m.revision_documents.delete().where(m.revision_documents.c.packet_id == pid))
        conn.execute(m.packets.update().where(m.packets.c.id == pid).values(title="Deleted packet"))

    def _queue_document(self, conn, document):
        if self.documents is None:
            raise ApiError(ErrorCode.STORAGE_UNAVAILABLE)
        self.documents._buckets(conn, document["owner_id"])
        row = conn.execute(sa.select(m.storage_reservations).where(
            m.storage_reservations.c.document_id == document["id"]).with_for_update()).mappings().one()
        if row["state"] == "stored":
            # Keep quota charged until object deletion actually succeeds. Compensation
            # releases reserved_bytes; move the stored charge into that bucket first.
            for scope in ("global", f"user:{document['owner_id']}"):
                conn.execute(m.storage_buckets.update().where(m.storage_buckets.c.scope == scope).values(
                    stored_bytes=m.storage_buckets.c.stored_bytes - row["reserved_bytes"],
                    reserved_bytes=m.storage_buckets.c.reserved_bytes + row["reserved_bytes"]))
            conn.execute(m.storage_reservations.update().where(m.storage_reservations.c.id == row["id"])
                         .values(state="cleanup_pending"))
            conn.execute(m.cleanup_jobs.update().where(m.cleanup_jobs.c.entity_id == document["id"],
                m.cleanup_jobs.c.kind == "object").values(state="pending", next_attempt_at=self.clock(),
                    attempt_count=0, last_error_code=None))
        # Reserved uploads retain their original lease, so an in-flight write can
        # finish before the final delete. Completion rechecks packet/document access.

    def orphan(self, did):
        with self.engine.begin() as conn:
            doc = conn.execute(sa.select(m.documents).where(m.documents.c.id == did)).mappings().first()
            if not doc or not self._lock_packet(conn, doc["packet_id"]):
                return
            if conn.execute(sa.select(m.revision_documents.c.document_id).where(
                    m.revision_documents.c.document_id == did)).first():
                return  # Saving a revision won the packet lock; historical sources survive.
            if doc["created_at"] + timedelta(hours=24) > self.clock():
                return
            conn.execute(m.documents.update().where(m.documents.c.id == did).values(
                deleted_at=self.clock()))
            conn.execute(m.document_pages.delete().where(m.document_pages.c.document_id == did))
            self._queue_document(conn, doc)
            self._enqueue(conn, "orphan", did)

    def recover_run(self, rid):
        with self.engine.begin() as conn:
            row = conn.execute(sa.select(m.runs).where(m.runs.c.id == rid)).mappings().first()
            if not row:
                return
            row = self.usage._run(conn, row["owner_id"], rid, active=False)
            if row["state"] == "pending" and row["created_at"] + timedelta(minutes=30) <= self.clock():
                conn.execute(m.runs.update().where(m.runs.c.id == rid).values(
                    state="cancelled", error_code="PENDING_EXPIRED", finished_at=self.clock()))
            elif row["state"] == "running" and row["lease_expires_at"] <= self.clock():
                dispatched = row["provider_dispatched_at"] is not None
                self.usage.settle(row["owner_id"], rid, outcome="unknown" if dispatched else "failed", connection=conn)
                conn.execute(m.runs.update().where(m.runs.c.id == rid).values(
                    state="outcome_unknown" if dispatched else "failed", error_code="LEASE_EXPIRED", finished_at=self.clock()))
            elif row["state"] == "outcome_unknown":
                prior = self.usage._prior(conn, rid)
                if prior and prior["state"] in ACTIVE_USAGE:
                    self.usage.settle(row["owner_id"], rid, outcome="unknown", connection=conn)

    def _purge_packet(self, conn, packet):
        pid = packet["id"]
        if packet["deleted_at"] is None and packet["expires_at"] > self.clock():
            raise Deferred()
        self._scrub(conn, packet)
        for doc in conn.execute(sa.select(m.documents).where(m.documents.c.packet_id == pid)).mappings():
            self._queue_document(conn, doc)
        rids = sa.select(m.runs.c.id).where(m.runs.c.packet_id == pid)
        busy = conn.execute(sa.select(m.usage_reservations.c.id).where(
            m.usage_reservations.c.run_id.in_(rids), m.usage_reservations.c.state.in_(ACTIVE_USAGE))).first()
        files = conn.execute(sa.select(m.storage_reservations.c.id).where(
            m.storage_reservations.c.document_id.in_(sa.select(m.documents.c.id).where(m.documents.c.packet_id == pid)),
            m.storage_reservations.c.state != "released")).first()
        if files:
            return False  # Commit erasure/queueing even while dependencies are pending.
        dids = sa.select(m.documents.c.id).where(m.documents.c.packet_id == pid)
        conn.execute(m.idempotency.delete().where(m.idempotency.c.resource_id.in_(dids)))
        conn.execute(m.storage_reservations.delete().where(m.storage_reservations.c.document_id.in_(dids)))
        conn.execute(m.cleanup_jobs.delete().where(m.cleanup_jobs.c.entity_id.in_(dids)))
        conn.execute(m.documents.delete().where(m.documents.c.packet_id == pid))
        if busy:
            return False  # Only non-content packet/revision/run shells remain.
        conn.execute(m.usage_reservations.update().where(m.usage_reservations.c.run_id.in_(rids))
                     .values(run_id=None, owner_id=None))
        conn.execute(m.concurrency_slots.update().where(m.concurrency_slots.c.run_id.in_(rids))
                     .values(run_id=None, lease_expires_at=None))
        resources = [pid, *conn.execute(rids).scalars(),
                     *conn.execute(sa.select(m.revisions.c.id).where(m.revisions.c.packet_id == pid)).scalars()]
        conn.execute(m.idempotency.delete().where(m.idempotency.c.resource_id.in_(resources)))
        conn.execute(m.runs.delete().where(m.runs.c.packet_id == pid))
        conn.execute(m.revision_documents.delete().where(m.revision_documents.c.packet_id == pid))
        conn.execute(m.revisions.delete().where(m.revisions.c.packet_id == pid))
        conn.execute(m.packets.delete().where(m.packets.c.id == pid))
        return True

    def _purge_account(self, conn, owner):
        if conn.execute(sa.select(m.packets.c.id).where(m.packets.c.owner_id == owner)).first():
            return False
        # All costs are settled before these composite FKs are detached.
        conn.execute(m.usage_reservations.update().where(m.usage_reservations.c.owner_id == owner)
                     .values(owner_id=None, run_id=None))
        conn.execute(m.memberships.update().where(m.memberships.c.owner_id == owner).values(owner_id=None))
        orders = sa.select(m.orders.c.id).where(m.orders.c.owner_id == owner)
        conn.execute(m.checkout_details.delete().where(m.checkout_details.c.order_id.in_(orders)))
        conn.execute(m.orders.update().where(m.orders.c.owner_id == owner).values(owner_id=None))
        for table, column in ((m.sessions, m.sessions.c.user_id), (m.idempotency, m.idempotency.c.owner_id),
                              (m.audit_events, m.audit_events.c.actor_id)):
            conn.execute(table.delete().where(column == owner))
        conn.execute(m.rate_limit_buckets.delete().where(m.rate_limit_buckets.c.scope == f"account:{owner}"))
        conn.execute(m.concurrency_slots.delete().where(m.concurrency_slots.c.scope == f"account:{owner}"))
        conn.execute(m.storage_buckets.delete().where(m.storage_buckets.c.scope == f"user:{owner}"))
        conn.execute(m.users.delete().where(m.users.c.id == owner))
        return True

    def purge(self, job_id):
        try:
            with self.engine.begin() as conn:
                job = conn.execute(sa.select(m.cleanup_jobs).where(m.cleanup_jobs.c.id == job_id)).mappings().first()
                if not job or job["state"] == "succeeded":
                    return True
                kind, entity = job["kind"], job["entity_id"]
                if kind == "packet":
                    packet = self._lock_packet(conn, entity)
                elif kind == "account":
                    user = conn.execute(sa.select(m.users).where(m.users.c.id == entity).with_for_update()).mappings().first()
                elif kind == "orphan":
                    doc = conn.execute(sa.select(m.documents).where(m.documents.c.id == entity)).mappings().first()
                    if doc:
                        self._lock_packet(conn, doc["packet_id"])
                job = conn.execute(sa.select(m.cleanup_jobs).where(m.cleanup_jobs.c.id == job_id)
                                   .with_for_update()).mappings().first()
                if not job or job["state"] == "succeeded":
                    return True
                if job["attempt_count"] >= 10 or job["next_attempt_at"] > self.clock():
                    return False
                if kind == "packet":
                    done = not packet or self._purge_packet(conn, packet)
                elif kind == "account":
                    if user and user["disabled_at"] is None:
                        raise Deferred()
                    done = not user or self._purge_account(conn, entity)
                elif kind == "orphan":
                    done = not doc
                    if doc:
                        released = conn.execute(sa.select(m.storage_reservations.c.state).where(
                            m.storage_reservations.c.document_id == entity)).scalar_one()
                        if released == "released":
                            conn.execute(m.storage_reservations.delete().where(m.storage_reservations.c.document_id == entity))
                            conn.execute(m.idempotency.delete().where(m.idempotency.c.resource_id == entity))
                            conn.execute(m.documents.delete().where(m.documents.c.id == entity))
                            conn.execute(m.cleanup_jobs.delete().where(m.cleanup_jobs.c.entity_id == entity, m.cleanup_jobs.c.kind == "object"))
                            done = True
                else:
                    raise Deferred()
                if done:
                    # Completed lifecycle jobs contain neither object keys nor old account IDs.
                    conn.execute(m.cleanup_jobs.delete().where(m.cleanup_jobs.c.id == job_id))
                else:
                    conn.execute(m.cleanup_jobs.update().where(m.cleanup_jobs.c.id == job_id).values(
                        next_attempt_at=self.clock() + timedelta(seconds=5)))
                return bool(done)
        except Deferred:
            return False
        except Exception:
            # A DB rollback preserves the original job. If DB is still down the
            # caller fails, and the same durable job remains available next time.
            with self.engine.begin() as conn:
                conn.execute(m.cleanup_jobs.update().where(m.cleanup_jobs.c.id == job_id).values(
                    state="failed", attempt_count=m.cleanup_jobs.c.attempt_count + 1,
                    last_error_code="PURGE_FAILED", next_attempt_at=self.clock() + timedelta(minutes=5)))
            return False

    def _candidates(self):
        now = self.clock()
        return [
            ("expire", sa.select(m.packets.c.id).where(m.packets.c.deleted_at.is_(None), m.packets.c.expires_at <= now)),
            ("orphan", sa.select(m.documents.c.id).where(m.documents.c.deleted_at.is_(None),
                m.documents.c.created_at <= now - timedelta(hours=24),
                ~sa.exists().where(m.revision_documents.c.document_id == m.documents.c.id))),
            ("recover_run", sa.select(m.runs.c.id).where(sa.or_(
                sa.and_(m.runs.c.state == "pending", m.runs.c.created_at <= now - timedelta(minutes=30)),
                sa.and_(m.runs.c.state == "running", m.runs.c.lease_expires_at <= now),
                sa.and_(m.runs.c.state == "outcome_unknown", sa.exists().where(
                    m.usage_reservations.c.run_id == m.runs.c.id,
                    m.usage_reservations.c.state == "retained_unknown",
                    m.usage_details.c.reservation_id == m.usage_reservations.c.id,
                    m.usage_details.c.unknown_at <= now - timedelta(hours=24)))))),
            ("object", sa.select(m.cleanup_jobs.c.entity_id).where(m.cleanup_jobs.c.kind == "object",
                m.cleanup_jobs.c.state != "succeeded", m.cleanup_jobs.c.next_attempt_at <= now,
                m.cleanup_jobs.c.attempt_count < 10).order_by(m.cleanup_jobs.c.next_attempt_at, m.cleanup_jobs.c.id)),
            ("purge", sa.select(m.cleanup_jobs.c.id).where(m.cleanup_jobs.c.kind.in_(("packet", "account", "orphan")),
                m.cleanup_jobs.c.state != "succeeded", m.cleanup_jobs.c.next_attempt_at <= now, m.cleanup_jobs.c.attempt_count < 10)
                .order_by(m.cleanup_jobs.c.next_attempt_at, m.cleanup_jobs.c.id)),
        ]

    def maintain(self, limit=200):
        if not 1 <= limit <= 200:
            raise ValueError("Maintenance limit must be 1..200")
        deadline = time.monotonic() + 45
        processed = failed = 0
        with self.engine.begin() as conn:
            require_current_schema(conn)
        for action, query in self._candidates():
            with self.engine.begin() as conn:
                ids = conn.execute(query.limit(limit - processed)).scalars().all()
            for entity in ids:
                # Reserve time for one bounded provider operation and its DB commit.
                if processed >= limit or time.monotonic() >= deadline - 35:
                    break
                processed += 1
                if action == "object":
                    if self.documents is None or not self.documents.cleanup(entity):
                        failed += 1
                else:
                    getattr(self, action)(entity)
        if self.billing and processed < limit and time.monotonic() < deadline - 35:
            result = self.billing.recover(limit=limit - processed, deadline=deadline - 5)
            processed += result["processed"] + result["failed"]
            failed += result["failed"]
        processed += self._retention(limit - processed, deadline)
        with self.engine.begin() as conn:
            pending = conn.execute(sa.select(sa.func.count()).select_from(m.cleanup_jobs).where(
                m.cleanup_jobs.c.state != "succeeded")).scalar_one()
            exhausted = conn.execute(sa.select(sa.func.count()).select_from(m.cleanup_jobs).where(
                m.cleanup_jobs.c.state != "succeeded", m.cleanup_jobs.c.attempt_count >= 10)).scalar_one()
            failed = max(failed, conn.execute(sa.select(sa.func.count()).select_from(m.cleanup_jobs).where(
                m.cleanup_jobs.c.state == "failed")).scalar_one())
            backlog = sum(conn.execute(sa.select(sa.func.count()).select_from(query.subquery())).scalar_one()
                          for _, query in self._candidates()[:3]) + pending
            if self.billing:
                backlog += self.billing.backlog(conn)
            backlog += self._retention_backlog(conn)
        return dict(processed=processed, failed=failed, exhausted=exhausted, backlog=backlog,
                    cursor="continue" if backlog else None)

    def _retention_queries(self):
        now = self.clock()
        return [(m.audit_events, m.audit_events.c.created_at <= now - timedelta(days=30)),
                (m.rate_limit_buckets, m.rate_limit_buckets.c.window_start <= now - timedelta(days=30)),
                (m.idempotency, m.idempotency.c.expires_at <= now),
                (m.oauth_states, m.oauth_states.c.expires_at <= now),
                (m.sessions, m.sessions.c.expires_at <= now),
                (m.billing_events, m.billing_events.c.received_at <= now - timedelta(days=90)),
                (m.orders, sa.and_(m.orders.c.created_at <= now - timedelta(days=90),
                    sa.or_(m.orders.c.checkout_session_id.is_not(None), m.orders.c.payment_intent_id.is_not(None),
                           m.orders.c.owner_id.is_not(None))))]

    def _retention_backlog(self, conn):
        return sum(conn.execute(sa.select(sa.func.count()).select_from(t).where(p)).scalar_one()
                   for t, p in self._retention_queries())

    def _retention(self, limit, deadline):
        count = 0
        for table, predicate in self._retention_queries():
            with self.engine.begin() as conn:
                rows = conn.execute(sa.select(table).where(predicate).limit(limit - count)).mappings().all()
            for row in rows:
                if count >= limit or time.monotonic() >= deadline - 5:
                    return count
                with self.engine.begin() as conn:
                    if table is m.orders:
                        # Preserve anonymous monetary aggregates/FKs; erase provider IDs.
                        owner = row["owner_id"]
                        if owner:
                            conn.execute(sa.select(m.users.c.id).where(m.users.c.id == owner).with_for_update()).first()
                        conn.execute(sa.select(m.orders.c.id).where(m.orders.c.id == row["id"]).with_for_update()).first()
                        members = sa.select(m.memberships.c.id).where(m.memberships.c.source_order_id == row["id"])
                        if conn.execute(sa.select(m.usage_reservations.c.id).where(
                                m.usage_reservations.c.membership_id.in_(members), m.usage_reservations.c.state.in_(ACTIVE_USAGE))).first():
                            continue
                        conn.execute(m.usage_reservations.update().where(m.usage_reservations.c.membership_id.in_(members))
                                     .values(owner_id=None, run_id=None))
                        conn.execute(m.memberships.update().where(m.memberships.c.source_order_id == row["id"]).values(owner_id=None))
                        conn.execute(m.checkout_details.delete().where(m.checkout_details.c.order_id == row["id"]))
                        conn.execute(m.orders.update().where(m.orders.c.id == row["id"]).values(
                            owner_id=None, checkout_session_id=None, payment_intent_id=None, state="revoked"))
                    else:
                        conn.execute(table.delete().where(*(column == row[column.name] for column in table.primary_key)))
                count += 1
        return count
