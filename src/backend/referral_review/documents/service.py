"""Reservation -> private object -> settlement, with a durable cleanup intent.

Locks: identity (user/session/packet), storage buckets (sorted), reservation/job.
Provider operations never hold a DB transaction. A crash at any point leaves
either a committed document or an expiring reservation + cleanup job. Cleanup
retains quota until deletion is confirmed; retries cannot subtract twice.
"""

from dataclasses import dataclass
from datetime import timedelta
import hashlib
import json
import re
import time
from uuid import UUID, uuid4

import sqlalchemy as sa

from ..errors import ApiError
from ..identity.service import DATABASE_FAILURES
from ..persistence import models as m
from ..persistence.migrations import require_current_schema
from ..usage import rates
from ..schemas import DocumentPageResponse, DocumentResponse, ErrorCode
from .parser import MAX_DOCUMENT_CODEPOINTS, MAX_PAGES, PDF_PARSER_VERSION, parse_pdf, parse_text, rejected
from .storage import LocalStore, MAX_BYTES, PrivateBlobStore, StorageUnavailable, object_key

ACCOUNT_BYTES = 100 * 1024 * 1024
ACCOUNT_FILES = 50
GLOBAL_FILES = 5120
LEASE = timedelta(minutes=10)
LIVE = ("reserved", "stored", "cleanup_pending")


@dataclass(frozen=True)
class Upload:
    document_id: UUID
    packet_id: UUID
    owner_id: UUID
    key: str
    replay: bool = False


def public_document(row):
    return DocumentResponse(**{key: row[key] for key in DocumentResponse.model_fields})


def fingerprint(filename, kind, body):
    payload = [filename, kind, hashlib.sha256(body).hexdigest()]
    return hashlib.sha256(json.dumps(payload, ensure_ascii=True).encode()).hexdigest()


class Documents:
    def __init__(self, identity, store, *, global_bytes=1024**3):
        self.identity, self.engine, self.store = identity, identity.engine, store
        self.clock, self.global_bytes = identity.clock, global_bytes

    def _buckets(self, conn, owner_id):
        from sqlalchemy.dialects.postgresql import insert as pg_insert
        from sqlalchemy.dialects.sqlite import insert as sqlite_insert

        insert = pg_insert if conn.dialect.name == "postgresql" else sqlite_insert
        scopes = {"global": self.global_bytes, f"user:{owner_id}": ACCOUNT_BYTES}
        for scope, limit in sorted(scopes.items()):
            conn.execute(insert(m.storage_buckets).values(scope=scope, limit_bytes=limit)
                         .on_conflict_do_nothing(index_elements=[m.storage_buckets.c.scope]))
            conn.execute(sa.select(m.storage_buckets.c.scope).where(
                m.storage_buckets.c.scope == scope).with_for_update()).one()
        return scopes

    def _get(self, conn, token, packet_id, document_id):
        self.identity.require_owner(conn, token, packet_id)
        row = conn.execute(sa.select(m.documents).where(
            m.documents.c.id == document_id, m.documents.c.packet_id == packet_id,
            m.documents.c.deleted_at.is_(None))).mappings().first()
        if row is None:
            raise ApiError(ErrorCode.NOT_FOUND)
        return row

    def get(self, token, packet_id, document_id):
        with self.engine.begin() as conn:
            return public_document(self._get(conn, token, packet_id, document_id))

    def get_page(self, token, packet_id, document_id, page_number):
        with self.engine.begin() as conn:
            document = self._get(conn, token, packet_id, document_id)
            if document["parse_status"] not in ("ready", "rejected"):
                raise ApiError(ErrorCode.NOT_FOUND)
            page = conn.execute(sa.select(m.document_pages).where(
                m.document_pages.c.document_id == document_id,
                m.document_pages.c.page_number == page_number)).mappings().first()
            if page is None:
                raise ApiError(ErrorCode.NOT_FOUND)
            return DocumentPageResponse(**page, parser_version=document["parser_version"])

    @staticmethod
    def _active_document_filter(packet):
        packet_id = packet["id"]
        in_history = sa.exists().where(m.revision_documents.c.document_id == m.documents.c.id)
        in_current = sa.exists(sa.select(m.revision_documents.c.document_id).join(
            m.revisions, m.revision_documents.c.revision_id == m.revisions.c.id).where(
            m.revision_documents.c.document_id == m.documents.c.id,
            m.revisions.c.packet_id == packet_id,
            m.revisions.c.revision_number == packet["current_revision"]))
        return (m.documents.c.packet_id == packet_id, m.documents.c.deleted_at.is_(None),
                sa.or_(~in_history, in_current))

    def begin(self, token, packet_id, kind, idempotency_key):
        if not re.fullmatch(r"[A-Za-z0-9_-]{8,128}", idempotency_key or ""):
            raise ApiError(ErrorCode.SCHEMA_INVALID)
        with self.engine.begin() as conn:
            require_current_schema(conn)
            packet = self.identity.require_owner(conn, token, packet_id)
            rates.consume(conn, packet["owner_id"], "upload", self.clock())
        with self.engine.begin() as conn:
            require_current_schema(conn)
            packet = self.identity.require_owner(conn, token, packet_id)
            owner_id = packet["owner_id"]
            operation = f"document:{packet_id}"
            previous = conn.execute(sa.select(m.idempotency).where(
                m.idempotency.c.owner_id == owner_id, m.idempotency.c.operation == operation,
                m.idempotency.c.key == idempotency_key)).mappings().first()
            if previous:
                row = self._get(conn, token, packet_id, previous["resource_id"])
                reservation = conn.execute(sa.select(m.storage_reservations.c.state).where(
                    m.storage_reservations.c.document_id == row["id"])).scalar_one()
                if reservation != "stored":
                    raise ApiError(ErrorCode.IDEMPOTENCY_CONFLICT)
                return Upload(row["id"], packet_id, owner_id, row["storage_key"], replay=True)

            scopes = self._buckets(conn, owner_id)
            # Bucket locks serialize account and cross-account counts as well as bytes.
            live = sa.select(sa.func.count()).select_from(m.storage_reservations).where(
                m.storage_reservations.c.state.in_(LIVE))
            if (conn.execute(live).scalar_one() >= GLOBAL_FILES or
                conn.execute(live.where(m.storage_reservations.c.owner_id == owner_id)).scalar_one() >= ACCOUNT_FILES):
                raise ApiError(ErrorCode.DOCUMENT_LIMIT)
            # Historical revision members keep storage quota but not active-file slots.
            active_count = conn.execute(sa.select(sa.func.count()).select_from(m.documents).where(
                m.documents.c.parse_status.in_(("uploading", "parsing", "ready")),
                *self._active_document_filter(packet))).scalar_one()
            if active_count >= 5:
                raise ApiError(ErrorCode.DOCUMENT_LIMIT)
            reserved = MAX_BYTES if kind == "pdf" else 40_000
            for scope, limit in scopes.items():
                total = m.storage_buckets.c.reserved_bytes + m.storage_buckets.c.stored_bytes + reserved
                changed = conn.execute(m.storage_buckets.update().where(
                    m.storage_buckets.c.scope == scope, total <= limit,
                    total <= m.storage_buckets.c.limit_bytes).values(
                        reserved_bytes=m.storage_buckets.c.reserved_bytes + reserved)).rowcount
                if changed != 1:
                    raise ApiError(ErrorCode.STORAGE_LIMIT)
            document_id = uuid4()
            key = object_key(document_id)
            expires = self.clock() + LEASE
            conn.execute(m.documents.insert().values(id=document_id, packet_id=packet_id,
                owner_id=owner_id, kind=kind, filename="upload.pdf" if kind == "pdf" else "pasted-text.txt",
                sha256="0" * 64, storage_key=key, byte_size=0, parse_status="uploading", created_at=self.clock()))
            conn.execute(m.storage_reservations.insert().values(owner_id=owner_id, document_id=document_id,
                reserved_bytes=reserved, state="reserved", expires_at=expires))
            conn.execute(m.idempotency.insert().values(owner_id=owner_id, operation=operation,
                key=idempotency_key, request_hash="pending", resource_id=document_id,
                expires_at=self.clock() + timedelta(days=7)))
            # Intent is committed BEFORE any storage call, including an ambiguous PUT.
            conn.execute(m.cleanup_jobs.insert().values(object_key=key, entity_id=document_id,
                kind="object", state="pending", next_attempt_at=expires))
            return Upload(document_id, packet_id, owner_id, key)

    def finish(self, token, upload, filename, kind, body):
        digest = fingerprint(filename, kind, body)
        if upload.replay:
            with self.engine.begin() as conn:
                row = self._get(conn, token, upload.packet_id, upload.document_id)
                prior = conn.execute(sa.select(m.idempotency.c.request_hash).where(
                    m.idempotency.c.owner_id == upload.owner_id,
                    m.idempotency.c.operation == f"document:{upload.packet_id}",
                    m.idempotency.c.resource_id == upload.document_id)).scalar_one()
                if prior != digest:
                    raise ApiError(ErrorCode.IDEMPOTENCY_CONFLICT)
                if row["parse_status"] != "parsing":
                    return public_document(row)
            return self._parse_and_save(token, upload, kind, body)
        with self.engine.begin() as conn:
            self._get(conn, token, upload.packet_id, upload.document_id)
            reservation = conn.execute(sa.select(m.storage_reservations).where(
                m.storage_reservations.c.document_id == upload.document_id)).mappings().one()
            if reservation["state"] != "reserved" or reservation["expires_at"] <= self.clock():
                raise ApiError(ErrorCode.STORAGE_UNAVAILABLE)
            # Give the bounded object write a full lease, including when reading
            # the request body consumed most of the original upload reservation.
            expires = self.clock() + LEASE
            conn.execute(m.storage_reservations.update().where(m.storage_reservations.c.id == reservation["id"])
                         .values(expires_at=expires))
            conn.execute(m.cleanup_jobs.update().where(m.cleanup_jobs.c.entity_id == upload.document_id,
                m.cleanup_jobs.c.kind == "object").values(next_attempt_at=expires))
        self.store.write(upload.key, body, "application/pdf" if kind == "pdf" else "text/plain; charset=utf-8")
        # A commit failure is ambiguous: abort() first checks committed state.
        self._settle(token, upload, filename, kind, body, digest)
        return self._parse_and_save(token, upload, kind, body)

    def _parse_and_save(self, token, upload, kind, body):
        try:
            parsed = parse_text(body) if kind == "text" else parse_pdf(body)
        except Exception:
            parsed = rejected("PARSER_UNAVAILABLE", parser_version="text-v1" if kind == "text" else PDF_PARSER_VERSION)
        with self.engine.begin() as conn:
            packet = self.identity.require_owner(conn, token, upload.packet_id)
            row = conn.execute(sa.select(m.documents).where(m.documents.c.id == upload.document_id,
                m.documents.c.deleted_at.is_(None)).with_for_update()).mappings().first()
            if row is None:
                raise ApiError(ErrorCode.NOT_FOUND)
            if row["parse_status"] != "parsing":
                return public_document(row)
            if parsed.status == "ready":
                # Packet ownership lock serializes upload completion across instances.
                active = sa.select(m.documents.c.page_count, m.documents.c.id).where(
                    m.documents.c.parse_status == "ready", m.documents.c.id != upload.document_id,
                    *self._active_document_filter(packet))
                existing = conn.execute(active).all()
                page_total = 0
                text_total = 0
                for count, did in existing:
                    pages = conn.execute(sa.select(
                        m.document_pages.c.normalized_text).where(
                        m.document_pages.c.document_id == did)).scalars().all()
                    page_total += count if count is not None else len(pages)
                    text_total += sum(len(value) for value in pages)
                if page_total + (parsed.page_count or 0) > MAX_PAGES:
                    parsed = rejected("PACKET_PAGE_LIMIT", parser_version=parsed.parser_version,
                                      page_count=parsed.page_count)
                elif text_total + sum(len(page.normalized_text) for page in parsed.pages) > MAX_DOCUMENT_CODEPOINTS:
                    parsed = rejected("PACKET_TEXT_LIMIT", parser_version=parsed.parser_version,
                                      page_count=parsed.page_count)
            for page in parsed.pages:
                conn.execute(m.document_pages.insert().values(document_id=upload.document_id,
                    page_number=page.page_number, normalized_text=page.normalized_text,
                    text_hash=page.text_hash, parse_quality=page.parse_quality))
            updated = conn.execute(m.documents.update().where(m.documents.c.id == upload.document_id).values(
                parse_status=parsed.status, parser_version=parsed.parser_version,
                page_count=parsed.page_count, parse_error_code=parsed.issue_code,
                parse_error_page=parsed.issue_page).returning(m.documents)).mappings().one()
            return public_document(updated)

    def _settle(self, token, upload, filename, kind, body, digest):
        with self.engine.begin() as conn:
            self._get(conn, token, upload.packet_id, upload.document_id)
            scopes = self._buckets(conn, upload.owner_id)
            reservation = conn.execute(sa.select(m.storage_reservations).where(
                m.storage_reservations.c.document_id == upload.document_id).with_for_update()).mappings().one()
            if reservation["state"] != "reserved" or reservation["expires_at"] <= self.clock():
                raise ApiError(ErrorCode.STORAGE_UNAVAILABLE)
            if len(body) > reservation["reserved_bytes"]:
                raise ApiError(ErrorCode.FILE_TOO_LARGE)
            for scope in scopes:
                conn.execute(m.storage_buckets.update().where(m.storage_buckets.c.scope == scope).values(
                    reserved_bytes=m.storage_buckets.c.reserved_bytes - reservation["reserved_bytes"],
                    stored_bytes=m.storage_buckets.c.stored_bytes + len(body)))
            conn.execute(m.storage_reservations.update().where(m.storage_reservations.c.id == reservation["id"])
                         .values(state="stored", reserved_bytes=len(body)))
            row = conn.execute(m.documents.update().where(m.documents.c.id == upload.document_id).values(
                filename=filename, kind=kind, byte_size=len(body), sha256=hashlib.sha256(body).hexdigest(),
                parse_status="parsing").returning(m.documents)).mappings().one()
            conn.execute(m.idempotency.update().where(m.idempotency.c.resource_id == upload.document_id,
                m.idempotency.c.operation == f"document:{upload.packet_id}",
                m.idempotency.c.owner_id == upload.owner_id).values(request_hash=digest))
            conn.execute(m.cleanup_jobs.update().where(m.cleanup_jobs.c.entity_id == upload.document_id,
                m.cleanup_jobs.c.kind == "object").values(state="succeeded"))
            return public_document(row)

    def abort(self, upload, *, object_attempted):
        if upload.replay:
            return
        try:
            # Transaction makes the object unreachable before cleanup; committed uploads survive.
            with self.engine.begin() as conn:
                self._buckets(conn, upload.owner_id)
                row = conn.execute(sa.select(m.storage_reservations).where(
                    m.storage_reservations.c.document_id == upload.document_id).with_for_update()).mappings().one()
                if row["state"] != "reserved":
                    return
                conn.execute(m.storage_reservations.update().where(m.storage_reservations.c.id == row["id"])
                             .values(state="cleanup_pending"))
                conn.execute(m.documents.update().where(m.documents.c.id == upload.document_id).values(parse_status="failed"))
                conn.execute(m.cleanup_jobs.update().where(m.cleanup_jobs.c.entity_id == upload.document_id,
                    m.cleanup_jobs.c.kind == "object").values(next_attempt_at=self.clock()))
            self.cleanup(upload.document_id, skip_object=not object_attempted)
        except DATABASE_FAILURES:
            # Original durable intent remains due after its lease, including DB outages.
            return

    def cleanup(self, document_id, *, skip_object=False):
        """Internal compensation only; no API caller can supply object keys.

        MT-18 will schedule this bounded, reentrant operation. Reserved uploads
        are eligible only after the entire upload lease; stored files are never
        deleted by compensation. Logical deletes must be orchestrated by lifecycle.
        """
        with self.engine.begin() as conn:
            row = conn.execute(sa.select(m.storage_reservations).where(
                m.storage_reservations.c.document_id == document_id)).mappings().first()
            if row is None or row["state"] in ("stored", "released"):
                return False
            self._buckets(conn, row["owner_id"])
            row = conn.execute(sa.select(m.storage_reservations).where(
                m.storage_reservations.c.document_id == document_id).with_for_update()).mappings().one()
            if row["state"] in ("stored", "released") or (row["state"] == "reserved" and row["expires_at"] > self.clock()):
                return False
            job = conn.execute(sa.select(m.cleanup_jobs).where(m.cleanup_jobs.c.entity_id == document_id,
                m.cleanup_jobs.c.kind == "object").with_for_update()).mappings().one()
            if job["attempt_count"] >= 10:
                return False  # Operator review required; no infinite provider retry loop.
            if job["state"] == "running" and job["next_attempt_at"] > self.clock():
                return False
            if job["state"] == "failed" and job["next_attempt_at"] > self.clock():
                return False
            conn.execute(m.storage_reservations.update().where(m.storage_reservations.c.id == row["id"])
                         .values(state="cleanup_pending"))
            # Lifecycle may queue an immutable ready document after tombstoning.
            # Its parse record stays frozen until physical row deletion.
            conn.execute(m.documents.update().where(m.documents.c.id == document_id,
                m.documents.c.parse_status != "ready").values(parse_status="failed"))
            conn.execute(m.cleanup_jobs.update().where(m.cleanup_jobs.c.id == job["id"]).values(
                state="running", attempt_count=job["attempt_count"] + 1, next_attempt_at=self.clock() + LEASE))
        try:
            if not skip_object:
                self.store.delete(job["object_key"])
        except StorageUnavailable:
            with self.engine.begin() as conn:
                conn.execute(m.cleanup_jobs.update().where(m.cleanup_jobs.c.id == job["id"]).values(
                    state="failed", last_error_code="STORAGE_UNAVAILABLE",
                    next_attempt_at=self.clock() + timedelta(minutes=min(60, 2 ** min(job["attempt_count"], 6)))))
            return False
        with self.engine.begin() as conn:
            scopes = self._buckets(conn, row["owner_id"])
            current = conn.execute(sa.select(m.storage_reservations).where(
                m.storage_reservations.c.id == row["id"]).with_for_update()).mappings().one()
            if current["state"] == "cleanup_pending":
                for scope in scopes:
                    conn.execute(m.storage_buckets.update().where(m.storage_buckets.c.scope == scope).values(
                        reserved_bytes=m.storage_buckets.c.reserved_bytes - current["reserved_bytes"]))
                conn.execute(m.storage_reservations.update().where(m.storage_reservations.c.id == row["id"])
                             .values(state="released"))
            conn.execute(m.cleanup_jobs.update().where(m.cleanup_jobs.c.id == job["id"]).values(
                state="succeeded", last_error_code=None))
        return True

    def reconcile(self, *, limit=20, retry_exhausted=False):
        """Operator/MT-18 entry point. Bounded batch; never a read-side effect."""
        if not 1 <= limit <= 200:
            raise ValueError("Cleanup limit must be between 1 and 200")
        with self.engine.begin() as conn:
            due = conn.execute(sa.select(m.cleanup_jobs.c.entity_id).join(
                m.storage_reservations, m.storage_reservations.c.document_id == m.cleanup_jobs.c.entity_id).where(
                    m.cleanup_jobs.c.kind == "object", m.cleanup_jobs.c.state != "succeeded",
                    m.cleanup_jobs.c.next_attempt_at <= self.clock(),
                    m.storage_reservations.c.state.in_(("reserved", "cleanup_pending")),
                    sa.true() if retry_exhausted else m.cleanup_jobs.c.attempt_count < 10,
                ).order_by(m.cleanup_jobs.c.next_attempt_at, m.cleanup_jobs.c.id).limit(limit)).scalars().all()
            if retry_exhausted and due:
                conn.execute(m.cleanup_jobs.update().where(m.cleanup_jobs.c.entity_id.in_(due),
                    m.cleanup_jobs.c.kind == "object", m.cleanup_jobs.c.attempt_count >= 10).values(attempt_count=0))
        started, cleaned = time.monotonic(), 0
        for document_id in due:
            if time.monotonic() - started >= 45:
                break
            cleaned += bool(self.cleanup(document_id))
        return {"selected": len(due), "cleaned": cleaned}

    def read_original(self, token, packet_id, document_id):
        with self.engine.begin() as conn:
            row = dict(self._get(conn, token, packet_id, document_id))
            stored = conn.execute(sa.select(m.storage_reservations.c.state).where(
                m.storage_reservations.c.document_id == document_id)).scalar_one()
            if stored != "stored":
                raise ApiError(ErrorCode.NOT_FOUND)
        body = self.store.read(row["storage_key"])
        if len(body) != row["byte_size"] or hashlib.sha256(body).hexdigest() != row["sha256"]:
            raise StorageUnavailable()
        # Recheck after I/O so expiry/deletion/logout during a slow download wins.
        with self.engine.begin() as conn:
            self._get(conn, token, packet_id, document_id)
        return public_document(row), body


def configured_documents(settings, identity):
    if identity is None or settings.storage_backend == "disabled":
        return None
    store = LocalStore(settings.private_storage_dir) if settings.storage_backend == "local" else PrivateBlobStore(
        settings.blob_token.get_secret_value())
    return Documents(identity, store, global_bytes=settings.storage_global_bytes)
