"""Owner-scoped transactional primitives, not HTTP or business authorization.

Lock order: user -> packet -> run -> order -> membership -> budget (sorted key)
-> concurrency slot (sorted scope/number). Callers must not acquire earlier locks
after later ones. No function commits, retries or calls an external provider.
"""

import hashlib
import json
from datetime import datetime
from uuid import UUID, uuid4

import sqlalchemy as sa

from . import models as m


class NotFound(Exception):
    pass


class RevisionConflict(Exception):
    pass


class CapacityExceeded(Exception):
    pass


class InvalidReference(Exception):
    pass


def require_transaction(connection):
    if not connection.in_transaction():
        raise ValueError("A caller-owned transaction is required")


def owned_packet(connection, owner_id: UUID, packet_id: UUID, now: datetime, *, lock=False):
    query = sa.select(m.packets).where(
        m.packets.c.id == packet_id, m.packets.c.owner_id == owner_id,
        m.packets.c.deleted_at.is_(None), m.packets.c.expires_at > now)
    if lock:
        query = query.with_for_update()
    packet = connection.execute(query).mappings().first()
    if packet is None:
        raise NotFound("Packet not found")
    return packet


def save_revision(connection, *, owner_id: UUID, packet_id: UUID,
                  expected_revision: int, document_ids: list[UUID], now: datetime) -> UUID:
    """CAS + member validation + frozen manifest; failure rolls back this operation.

    The caller must use a transaction. HTTP idempotency/input limits belong to
    MT-07; this primitive cannot bypass ownership or persist a partial revision.
    """
    require_transaction(connection)
    if len(set(document_ids)) != len(document_ids):
        raise InvalidReference("Revision requires distinct documents")
    with connection.begin_nested():
        owned_packet(connection, owner_id, packet_id, now, lock=True)
        if not document_ids and expected_revision == 0:
            raise InvalidReference("Initial revision requires a document")
        docs = connection.execute(sa.select(m.documents).where(
            m.documents.c.id.in_(document_ids), m.documents.c.packet_id == packet_id,
            m.documents.c.owner_id == owner_id, m.documents.c.deleted_at.is_(None),
            m.documents.c.parse_status == "ready")).mappings().all()
        if len(docs) != len(document_ids):
            raise InvalidReference("Revision documents are unavailable")
        changed = connection.execute(sa.update(m.packets).where(
            m.packets.c.id == packet_id, m.packets.c.current_revision == expected_revision
        ).values(current_revision=expected_revision + 1, updated_at=now)).rowcount
        if changed != 1:
            raise RevisionConflict("Revision changed")
        by_id = {doc["id"]: doc for doc in docs}
        manifest = [{"id": str(doc_id), "sha256": by_id[doc_id]["sha256"],
                     "parser_version": by_id[doc_id]["parser_version"]} for doc_id in document_ids]
        digest = hashlib.sha256(json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        revision_id = uuid4()
        connection.execute(m.revisions.insert().values(id=revision_id, packet_id=packet_id,
                           revision_number=expected_revision + 1, manifest_hash=digest, created_at=now))
        if document_ids:
            connection.execute(m.revision_documents.insert(), [dict(revision_id=revision_id, document_id=doc_id,
                               packet_id=packet_id, ordinal=index) for index, doc_id in enumerate(document_ids)])
        return revision_id


def advance_review_version(connection, *, owner_id: UUID, packet_id: UUID,
                           expected_revision: int, expected_review_version: int, now: datetime) -> int:
    """CAS primitive; append the actual review change in the SAME transaction.

    This does not validate findings or confirm a snapshot; MT-12 owns those rules.
    """
    require_transaction(connection)
    owned_packet(connection, owner_id, packet_id, now, lock=True)
    changed = connection.execute(sa.update(m.packets).where(
        m.packets.c.id == packet_id, m.packets.c.current_revision == expected_revision,
        m.packets.c.review_version == expected_review_version,
    ).values(review_version=expected_review_version + 1, updated_at=now)).rowcount
    if changed != 1:
        raise RevisionConflict("Source or review version changed")
    return expected_review_version + 1


def add_evidence(connection, *, owner_id: UUID, run_id: UUID, evidence, now: datetime) -> None:
    require_transaction(connection)
    run = connection.execute(sa.select(m.runs).where(m.runs.c.id == run_id, m.runs.c.owner_id == owner_id)).mappings().first()
    if run is None:
        raise NotFound("Run not found")
    owned_packet(connection, owner_id, run["packet_id"], now)
    page = connection.execute(sa.select(m.document_pages).join(m.documents,
        m.documents.c.id == m.document_pages.c.document_id).join(m.revision_documents,
        m.document_pages.c.document_id == m.revision_documents.c.document_id).where(
        m.revision_documents.c.revision_id == run["revision_id"],
        m.documents.c.parse_status == "ready",
        m.document_pages.c.document_id == evidence.document_id,
        m.document_pages.c.page_number == evidence.page_number)).mappings().first()
    if (page is None or page["parse_quality"] != "ready" or page["text_hash"] != evidence.text_hash
        or hashlib.sha256(page["normalized_text"].encode()).hexdigest() != evidence.text_hash
        or page["normalized_text"][evidence.start_cp:evidence.end_cp] != evidence.quote):
        raise InvalidReference("Evidence does not match the run source")
    connection.execute(m.evidence.insert().values(**evidence.model_dump(), run_id=run_id, revision_id=run["revision_id"]))


def reserve_usage(connection, *, owner_id: UUID, run_id: UUID, membership_id: UUID,
                  bucket_keys: list[str], upper_bound_microusd: int, price_version: str, now: datetime) -> UUID:
    """Atomic ledger primitive, NOT permission to call a model.

    MT-10 must additionally enforce invitations, configuration, mode, daily/monthly
    bucket selection, rate/concurrency limits and model cost estimation. This
    primitive proves cross-instance membership/budget reservations cannot overdraw.
    """
    require_transaction(connection)
    if type(upper_bound_microusd) is not int or upper_bound_microusd <= 0 or not bucket_keys or len(set(bucket_keys)) != len(bucket_keys) or not price_version.strip():
        raise ValueError("Positive cost, distinct budget keys and price version required")
    with connection.begin_nested():
        user = connection.execute(sa.select(m.users.c.id).where(
            m.users.c.id == owner_id, m.users.c.disabled_at.is_(None)).with_for_update()).first()
        if not user:
            raise NotFound("Account not found")
        run = connection.execute(sa.select(m.runs).where(m.runs.c.id == run_id, m.runs.c.owner_id == owner_id)).mappings().first()
        if not run:
            raise NotFound("Run not found")
        owned_packet(connection, owner_id, run["packet_id"], now, lock=True)
        run = connection.execute(sa.select(m.runs).where(m.runs.c.id == run_id).with_for_update()).mappings().one()
        if run["state"] not in ("pending", "running"):
            raise InvalidReference("Run is not reservable")
        # Repeated reservations are rejected, never silently reserve twice.
        if connection.execute(sa.select(m.usage_reservations.c.id).where(m.usage_reservations.c.run_id == run_id)).first():
            raise InvalidReference("Run already has a usage reservation")
        member = connection.execute(sa.select(m.memberships).where(
            m.memberships.c.id == membership_id, m.memberships.c.owner_id == owner_id,
            m.memberships.c.revoked_at.is_(None), m.memberships.c.valid_from <= now,
            m.memberships.c.valid_until > now).with_for_update()).mappings().first()
        if not member:
            raise NotFound("Membership unavailable")
        reserved = connection.execute(sa.update(m.memberships).where(
            m.memberships.c.id == membership_id,
            m.memberships.c.reserved_units + m.memberships.c.consumed_units < m.memberships.c.granted_units
        ).values(reserved_units=m.memberships.c.reserved_units + 1)).rowcount
        if reserved != 1:
            raise CapacityExceeded("Membership capacity exceeded")
        for key in sorted(bucket_keys):
            connection.execute(sa.select(m.budget_buckets.c.bucket_key).where(
                m.budget_buckets.c.bucket_key == key).with_for_update()).first()
            changed = connection.execute(sa.update(m.budget_buckets).where(
                m.budget_buckets.c.bucket_key == key,
                m.budget_buckets.c.reserved_microusd + m.budget_buckets.c.spent_microusd + upper_bound_microusd <= m.budget_buckets.c.limit_microusd
            ).values(reserved_microusd=m.budget_buckets.c.reserved_microusd + upper_bound_microusd)).rowcount
            if changed != 1:
                raise CapacityExceeded("Budget capacity exceeded")
        reservation_id = uuid4()
        connection.execute(m.usage_reservations.insert().values(id=reservation_id, run_id=run_id,
            owner_id=owner_id, membership_id=membership_id, units=1, cost_upper_bound_microusd=upper_bound_microusd,
            state="reserved", price_version=price_version, created_at=now))
        connection.execute(m.usage_buckets.insert(), [dict(reservation_id=reservation_id, bucket_key=key) for key in sorted(bucket_keys)])
        return reservation_id
