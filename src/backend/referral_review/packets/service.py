"""Packet collection and immutable manifests; no provider calls or implicit cleanup."""

import base64
import binascii
from datetime import timedelta
import hashlib
import hmac
import json
import re
import unicodedata
from uuid import UUID, uuid4

import sqlalchemy as sa

from ..errors import ApiError
from ..persistence import models as m
from ..persistence.migrations import require_current_schema
from ..persistence.repository import InvalidReference, RevisionConflict, save_revision
from ..schemas import (DocumentResponse, ErrorCode, PacketDeleteResponse,
    PacketDetailResponse, PacketDraftResponse, PacketListResponse, PacketResponse,
    RevisionDocumentResponse, RevisionResponse)

PACKET_LIFETIME = timedelta(days=7)
IDEMPOTENCY_LIFETIME = timedelta(days=7)
MAX_PACKETS = 10
MAX_DOCUMENTS = 5
MAX_PAGES = 25
MAX_TEXT_CODEPOINTS = 30_000
MAX_PACKET_PDF_BYTES = 10 * 1024 * 1024
KEY_PATTERN = re.compile(r"[A-Za-z0-9_-]{8,128}\Z")


def _title(value):
    value = unicodedata.normalize("NFC", value.strip())
    if (not value or len(value) > 200 or
        any(unicodedata.category(char).startswith("C") for char in value)):
        raise ApiError(ErrorCode.SCHEMA_INVALID)
    return value


def _hash(payload):
    return hashlib.sha256(json.dumps(payload, sort_keys=True,
        ensure_ascii=True, separators=(",", ":")).encode()).hexdigest()


class Packets:
    def __init__(self, identity):
        self.identity, self.engine, self.clock = identity, identity.engine, identity.clock
        secret = identity.settings.session_encryption_key.get_secret_value().encode()
        self.cursor_key = hashlib.sha256(secret + b"referral-packet-cursor-v1").digest()

    def _user(self, conn, token):
        require_current_schema(conn)
        return self.identity.require_user(conn, token)

    def _packet(self, conn, token, packet_id):
        require_current_schema(conn)
        return self.identity.require_owner(conn, token, packet_id)

    def _previous(self, conn, owner_id, operation, key, payload):
        if not KEY_PATTERN.fullmatch(key or ""):
            raise ApiError(ErrorCode.SCHEMA_INVALID)
        prior = conn.execute(sa.select(m.idempotency).where(
            m.idempotency.c.owner_id == owner_id, m.idempotency.c.operation == operation,
            m.idempotency.c.key == key)).mappings().first()
        digest = _hash(payload)
        if prior is not None and prior["request_hash"] != digest:
            raise ApiError(ErrorCode.IDEMPOTENCY_CONFLICT)
        return prior, digest

    def _record(self, conn, owner_id, operation, key, digest, resource_id):
        conn.execute(m.idempotency.insert().values(owner_id=owner_id,
            operation=operation, key=key, request_hash=digest, resource_id=resource_id,
            expires_at=self.clock() + IDEMPOTENCY_LIFETIME))

    def _state(self, conn, packet):
        if packet["current_revision"]:
            count = conn.execute(sa.select(sa.func.count()).select_from(m.revision_documents).join(
                m.revisions, m.revisions.c.id == m.revision_documents.c.revision_id).where(
                m.revisions.c.packet_id == packet["id"],
                m.revisions.c.revision_number == packet["current_revision"])).scalar_one()
            if count:
                return "ready"
        count = conn.execute(sa.select(sa.func.count()).select_from(m.documents).where(
            m.documents.c.packet_id == packet["id"], m.documents.c.deleted_at.is_(None),
            m.documents.c.parse_status != "failed",
            ~sa.exists().where(m.revision_documents.c.document_id == m.documents.c.id))).scalar_one()
        return "collecting" if count else "empty"

    def _public(self, conn, row):
        return PacketResponse(id=row["id"], title=row["title"], state=self._state(conn, row),
            current_revision=row["current_revision"], review_version=row["review_version"],
            synthetic_data_ack=row["synthetic_ack_at"] is not None,
            created_at=row["created_at"], updated_at=row["updated_at"], expires_at=row["expires_at"])

    def _draft(self, conn, packet):
        row = conn.execute(sa.select(m.packet_drafts).where(
            m.packet_drafts.c.packet_id == packet["id"])).mappings().first()
        if row is None:
            return PacketDraftResponse(packet_id=packet["id"], selected_document_ids=[],
                last_location="documents", base_revision=packet["current_revision"],
                draft_version=0, updated_at=packet["updated_at"])
        return PacketDraftResponse(**row)

    def _cursor(self, owner_id, row):
        payload = json.dumps({"owner": str(owner_id), "created": row["created_at"].isoformat(),
                              "id": str(row["id"])}, sort_keys=True, separators=(",", ":")).encode()
        signature = hmac.new(self.cursor_key, payload, hashlib.sha256).digest()
        return (base64.urlsafe_b64encode(payload).decode().rstrip("=") + "." +
                base64.urlsafe_b64encode(signature).decode().rstrip("="))

    def _decode_cursor(self, cursor, owner_id):
        if not cursor or len(cursor) > 512:
            raise ApiError(ErrorCode.SCHEMA_INVALID)
        try:
            encoded, signed = cursor.split(".")
            payload = base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4))
            signature = base64.urlsafe_b64decode(signed + "=" * (-len(signed) % 4))
            if not hmac.compare_digest(signature, hmac.new(self.cursor_key, payload, hashlib.sha256).digest()):
                raise ValueError()
            value = json.loads(payload)
            if set(value) != {"owner", "created", "id"} or value["owner"] != str(owner_id):
                raise ValueError()
            from datetime import datetime
            created = datetime.fromisoformat(value["created"])
            if created.tzinfo is None:
                raise ValueError()
            return created, UUID(value["id"])
        except (ValueError, TypeError, KeyError, OverflowError, UnicodeError, binascii.Error):
            raise ApiError(ErrorCode.SCHEMA_INVALID) from None

    def create(self, token, title, key):
        title = _title(title)
        with self.engine.begin() as conn:
            owner_id = self._user(conn, token)  # User lock serializes the 10-packet cap.
            prior, digest = self._previous(conn, owner_id, "packet:create", key,
                                           {"title": title, "synthetic_data_ack": True})
            if prior:
                row = self._packet(conn, token, prior["resource_id"])
                return self._public(conn, row)
            count = conn.execute(sa.select(sa.func.count()).select_from(m.packets).where(
                m.packets.c.owner_id == owner_id, m.packets.c.deleted_at.is_(None),
                m.packets.c.expires_at > self.clock())).scalar_one()
            if count >= MAX_PACKETS:
                raise ApiError(ErrorCode.PACKET_LIMIT)
            now = self.clock()
            packet_id = uuid4()
            row = conn.execute(m.packets.insert().values(id=packet_id, owner_id=owner_id,
                title=title, synthetic_ack_at=now, created_at=now, updated_at=now,
                expires_at=now + PACKET_LIFETIME).returning(m.packets)).mappings().one()
            self._record(conn, owner_id, "packet:create", key, digest, packet_id)
            return self._public(conn, row)

    def list(self, token, cursor=None, limit=20):
        if limit < 1 or limit > 50:
            raise ApiError(ErrorCode.SCHEMA_INVALID)
        with self.engine.begin() as conn:
            owner_id = self._user(conn, token)
            query = sa.select(m.packets).where(m.packets.c.owner_id == owner_id,
                m.packets.c.deleted_at.is_(None), m.packets.c.expires_at > self.clock())
            if cursor is not None:
                created, packet_id = self._decode_cursor(cursor, owner_id)
                query = query.where(sa.or_(m.packets.c.created_at < created,
                    sa.and_(m.packets.c.created_at == created, m.packets.c.id < packet_id)))
            rows = conn.execute(query.order_by(m.packets.c.created_at.desc(),
                m.packets.c.id.desc()).limit(limit + 1)).mappings().all()
            return PacketListResponse(items=[self._public(conn, row) for row in rows[:limit]],
                next_cursor=self._cursor(owner_id, rows[limit - 1]) if len(rows) > limit else None)

    def get(self, token, packet_id):
        with self.engine.begin() as conn:
            packet = self._packet(conn, token, packet_id)
            documents = conn.execute(sa.select(m.documents).where(
                m.documents.c.packet_id == packet_id, m.documents.c.deleted_at.is_(None)
            ).order_by(m.documents.c.created_at, m.documents.c.id)).mappings().all()
            current_ids = []
            if packet["current_revision"]:
                current_ids = conn.execute(sa.select(m.revision_documents.c.document_id).join(
                    m.revisions, m.revisions.c.id == m.revision_documents.c.revision_id).where(
                    m.revisions.c.packet_id == packet_id,
                    m.revisions.c.revision_number == packet["current_revision"]
                ).order_by(m.revision_documents.c.ordinal)).scalars().all()
            return PacketDetailResponse(**self._public(conn, packet).model_dump(),
                current_document_ids=current_ids,
                documents=[DocumentResponse(**{key: row[key] for key in DocumentResponse.model_fields})
                           for row in documents], draft=self._draft(conn, packet))

    def rename(self, token, packet_id, title, key):
        title = _title(title)
        with self.engine.begin() as conn:
            packet = self._packet(conn, token, packet_id)
            owner_id = packet["owner_id"]
            operation = f"packet:title:{packet_id}"
            prior, digest = self._previous(conn, owner_id, operation, key, {"title": title})
            if prior is None:
                packet = conn.execute(m.packets.update().where(m.packets.c.id == packet_id).values(
                    title=title, updated_at=self.clock()).returning(m.packets)).mappings().one()
                self._record(conn, owner_id, operation, key, digest, packet_id)
            return self._public(conn, packet)

    def get_draft(self, token, packet_id):
        with self.engine.begin() as conn:
            return self._draft(conn, self._packet(conn, token, packet_id))

    def save_draft(self, token, packet_id, value, key):
        selected = value.selected_document_ids
        if len(selected) > MAX_DOCUMENTS or len(set(selected)) != len(selected):
            raise ApiError(ErrorCode.SCHEMA_INVALID)
        with self.engine.begin() as conn:
            packet = self._packet(conn, token, packet_id)
            operation = f"packet:draft:{packet_id}"
            payload = value.model_dump(mode="json")
            prior, digest = self._previous(conn, packet["owner_id"], operation, key, payload)
            if prior:
                return self._draft(conn, packet)
            if value.base_revision != packet["current_revision"]:
                raise ApiError(ErrorCode.REVISION_CONFLICT, current_revision=packet["current_revision"])
            current = conn.execute(sa.select(m.packet_drafts).where(
                m.packet_drafts.c.packet_id == packet_id).with_for_update()).mappings().first()
            version = current["draft_version"] if current else 0
            if value.expected_draft_version != version:
                raise ApiError(ErrorCode.DRAFT_CONFLICT)
            if selected:
                count = conn.execute(sa.select(sa.func.count()).select_from(m.documents).where(
                    m.documents.c.id.in_(selected), m.documents.c.packet_id == packet_id,
                    m.documents.c.owner_id == packet["owner_id"], m.documents.c.deleted_at.is_(None),
                    m.documents.c.parse_status != "failed")).scalar_one()
                if count != len(selected):
                    raise ApiError(ErrorCode.SCHEMA_INVALID)
            data = dict(selected_document_ids=[str(identifier) for identifier in selected],
                last_location=value.last_location, base_revision=value.base_revision,
                draft_version=version + 1, updated_at=self.clock())
            if current:
                conn.execute(m.packet_drafts.update().where(m.packet_drafts.c.packet_id == packet_id).values(**data))
            else:
                conn.execute(m.packet_drafts.insert().values(packet_id=packet_id, **data))
            self._record(conn, packet["owner_id"], operation, key, digest, packet_id)
            return self._draft(conn, packet)

    def _revision(self, conn, packet, number):
        row = conn.execute(sa.select(m.revisions).where(m.revisions.c.packet_id == packet["id"],
            m.revisions.c.revision_number == number)).mappings().first()
        if row is None:
            raise ApiError(ErrorCode.NOT_FOUND)
        docs = conn.execute(sa.select(m.documents).join(m.revision_documents,
            m.revision_documents.c.document_id == m.documents.c.id).where(
            m.revision_documents.c.revision_id == row["id"]
        ).order_by(m.revision_documents.c.ordinal)).mappings().all()
        return RevisionResponse(id=row["id"], packet_id=packet["id"],
            revision_number=number, manifest_hash=row["manifest_hash"],
            documents=[RevisionDocumentResponse(**{key: doc[key] for key in RevisionDocumentResponse.model_fields})
                       for doc in docs], is_current=packet["current_revision"] == number,
            created_at=row["created_at"])

    def get_revision(self, token, packet_id, number):
        with self.engine.begin() as conn:
            return self._revision(conn, self._packet(conn, token, packet_id), number)

    def save_revision(self, token, packet_id, value, key):
        identifiers = value.document_ids
        if len(identifiers) > MAX_DOCUMENTS or len(set(identifiers)) != len(identifiers):
            raise ApiError(ErrorCode.SCHEMA_INVALID)
        with self.engine.begin() as conn:
            packet = self._packet(conn, token, packet_id)
            operation = f"packet:revision:{packet_id}"
            prior, digest = self._previous(conn, packet["owner_id"], operation, key,
                value.model_dump(mode="json"))
            if prior:
                row = conn.execute(sa.select(m.revisions.c.revision_number).where(
                    m.revisions.c.id == prior["resource_id"],
                    m.revisions.c.packet_id == packet_id)).scalar_one()
                return self._revision(conn, packet, row)
            if packet["current_revision"] != value.expected_revision:
                raise ApiError(ErrorCode.REVISION_CONFLICT, current_revision=packet["current_revision"])
            if not identifiers and value.expected_revision == 0:
                raise ApiError(ErrorCode.SCHEMA_INVALID)
            docs = conn.execute(sa.select(m.documents).where(
                m.documents.c.id.in_(identifiers), m.documents.c.packet_id == packet_id,
                m.documents.c.owner_id == packet["owner_id"], m.documents.c.deleted_at.is_(None),
                m.documents.c.parse_status == "ready")).mappings().all()
            if len(docs) != len(identifiers):
                raise ApiError(ErrorCode.SCHEMA_INVALID)
            pdf_bytes = sum(doc["byte_size"] for doc in docs if doc["kind"] == "pdf")
            page_count = 0
            codepoints = 0
            for doc in docs:
                page_text = conn.execute(sa.select(m.document_pages.c.normalized_text).where(
                    m.document_pages.c.document_id == doc["id"])).scalars().all()
                if (not page_text or doc["page_count"] is not None and
                    doc["page_count"] != len(page_text)):
                    raise ApiError(ErrorCode.SCHEMA_INVALID)
                page_count += doc["page_count"] if doc["page_count"] is not None else len(page_text)
                codepoints += sum(len(text) for text in page_text)
            if (pdf_bytes > MAX_PACKET_PDF_BYTES or page_count > MAX_PAGES or
                codepoints > MAX_TEXT_CODEPOINTS):
                raise ApiError(ErrorCode.PACKET_INPUT_LIMIT)
            if packet["current_revision"]:
                existing = conn.execute(sa.select(m.revision_documents.c.document_id).join(
                    m.revisions, m.revisions.c.id == m.revision_documents.c.revision_id).where(
                    m.revisions.c.packet_id == packet_id,
                    m.revisions.c.revision_number == packet["current_revision"]
                ).order_by(m.revision_documents.c.ordinal)).scalars().all()
                if existing == identifiers:
                    raise ApiError(ErrorCode.SCHEMA_INVALID)
            try:
                revision_id = save_revision(conn, owner_id=packet["owner_id"], packet_id=packet_id,
                    expected_revision=value.expected_revision, document_ids=identifiers, now=self.clock())
            except RevisionConflict:
                current = conn.execute(sa.select(m.packets.c.current_revision).where(
                    m.packets.c.id == packet_id)).scalar_one()
                raise ApiError(ErrorCode.REVISION_CONFLICT, current_revision=current) from None
            except InvalidReference:
                raise ApiError(ErrorCode.SCHEMA_INVALID) from None
            draft = conn.execute(sa.select(m.packet_drafts.c.draft_version).where(
                m.packet_drafts.c.packet_id == packet_id)).scalar_one_or_none()
            data = dict(selected_document_ids=[str(identifier) for identifier in identifiers],
                last_location="review" if identifiers else "documents",
                base_revision=value.expected_revision + 1,
                draft_version=(draft or 0) + 1, updated_at=self.clock())
            if draft is None:
                conn.execute(m.packet_drafts.insert().values(packet_id=packet_id, **data))
            else:
                conn.execute(m.packet_drafts.update().where(m.packet_drafts.c.packet_id == packet_id).values(**data))
            self._record(conn, packet["owner_id"], operation, key, digest, revision_id)
            refreshed = conn.execute(sa.select(m.packets).where(m.packets.c.id == packet_id)).mappings().one()
            return self._revision(conn, refreshed, value.expected_revision + 1)

    def delete(self, token, packet_id, key):
        with self.engine.begin() as conn:
            owner_id = self._user(conn, token)
            row = conn.execute(sa.select(m.packets).where(m.packets.c.id == packet_id,
                m.packets.c.owner_id == owner_id).with_for_update()).mappings().first()
            if row is None:
                raise ApiError(ErrorCode.NOT_FOUND)
            operation = f"packet:delete:{packet_id}"
            prior, digest = self._previous(conn, owner_id, operation, key, {})
            if row["deleted_at"] is None:
                conn.execute(m.packets.update().where(m.packets.c.id == packet_id).values(
                    deleted_at=self.clock(), updated_at=self.clock()))
                conn.execute(m.cleanup_jobs.insert().values(entity_id=packet_id, kind="packet",
                    state="pending", next_attempt_at=self.clock()))
            if prior is None:
                self._record(conn, owner_id, operation, key, digest, packet_id)
            return PacketDeleteResponse(id=packet_id)
