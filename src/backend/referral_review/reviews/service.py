"""Transactional review overlays and immutable confirmations; no model or billing calls."""
from contextlib import contextmanager
from uuid import uuid4
import sqlalchemy as sa

from ..errors import ApiError
from ..packets.service import Packets, _hash
from ..persistence import models as m
from ..runs.results import load
from ..schemas import ErrorCode
from .contracts import ReviewEvent, ReviewHistory, HandoffDraftResponse, SnapshotResponse

STATUS = {"resolve": "resolved", "dismiss": "dismissed", "defer": "unresolved", "reopen": "open"}


class Reviews:
    def __init__(self, identity):
        self.identity, self.engine, self.clock = identity, identity.engine, identity.clock
        self.packets = Packets(identity)

    @contextmanager
    def _write(self):
        # SQLite has no FOR UPDATE: acquire its writer lock before the first read.
        # PostgreSQL uses the existing owner/packet row locks and compare-and-swap.
        with self.engine.connect().execution_options(sqlite_immediate=True) as conn:
            with conn.begin():
                yield conn

    def _revision(self, conn, packet):
        row = conn.execute(sa.select(m.revisions).where(m.revisions.c.packet_id == packet["id"],
            m.revisions.c.revision_number == packet["current_revision"])).mappings().first()
        if row is None:
            raise ApiError(ErrorCode.REVISION_CONFLICT, current_revision=packet["current_revision"])
        return row

    def _run(self, conn, packet, run_id):
        run = conn.execute(sa.select(m.runs).where(m.runs.c.id == run_id,
            m.runs.c.packet_id == packet["id"], m.runs.c.owner_id == packet["owner_id"]).with_for_update()).mappings().first()
        if run is None:
            raise ApiError(ErrorCode.NOT_FOUND)
        if run["state"] != "succeeded" or run["revision_id"] != self._revision(conn, packet)["id"]:
            raise ApiError(ErrorCode.STALE_RUN)
        return run

    def _advance(self, conn, packet, expected):
        version = packet["review_version"]
        if version != expected:
            raise ApiError(ErrorCode.REVIEW_CONFLICT, current_review_version=version)
        updated = conn.execute(m.packets.update().where(m.packets.c.id == packet["id"],
            m.packets.c.review_version == expected, m.packets.c.current_revision == packet["current_revision"])
            .values(review_version=version + 1, updated_at=self.clock()))
        if updated.rowcount != 1:
            raise ApiError(ErrorCode.REVIEW_CONFLICT, current_review_version=version)
        return version + 1

    def _previous(self, conn, packet, operation, key, body, **scope):
        return self.packets._previous(conn, packet["owner_id"], operation, key,
            dict(packet_id=str(packet["id"]), **scope, input=body.model_dump(mode="json")))

    def _event(self, conn, packet, revision_id, run_id, version, kind, content, operation, key, digest, event_id=None):
        event = dict(id=event_id or uuid4(), packet_id=packet["id"], revision_id=revision_id,
            run_id=run_id, actor_id=packet["owner_id"], review_version=version,
            kind=kind, content=content, created_at=self.clock())
        conn.execute(m.review_events.insert().values(**event))
        self.packets._record(conn, packet["owner_id"], operation, key, digest, event["id"])
        return ReviewEvent(**event)

    def _replay(self, conn, packet, prior):
        row = conn.execute(sa.select(m.review_events).where(m.review_events.c.id == prior["resource_id"],
            m.review_events.c.packet_id == packet["id"])).mappings().one()
        return ReviewEvent(**row)

    def resolve(self, token, run_id, finding_id, body, key):
        with self._write() as conn:
            # Authenticate before looking up resources; keep user -> packet -> run lock order.
            owner = self.packets._user(conn, token)
            pid = conn.execute(sa.select(m.runs.c.packet_id).where(m.runs.c.id == run_id,
                m.runs.c.owner_id == owner)).scalar_one_or_none()
            if pid is None:
                raise ApiError(ErrorCode.NOT_FOUND)
            packet = self.packets._packet(conn, token, pid)
            prior, digest = self._previous(conn, packet, "review:resolution", key, body,
                run_id=str(run_id), finding_id=str(finding_id))
            if prior:
                return self._replay(conn, packet, prior)
            run = self._run(conn, packet, run_id)
            if conn.execute(sa.select(m.findings.c.id).where(m.findings.c.id == finding_id,
                m.findings.c.run_id == run_id)).scalar_one_or_none() is None:
                raise ApiError(ErrorCode.NOT_FOUND)
            linked = set(body.linked_evidence_ids)
            valid = set(conn.execute(sa.select(m.evidence.c.id).where(m.evidence.c.run_id == run_id,
                m.evidence.c.id.in_(linked))).scalars())
            if valid != linked:
                raise ApiError(ErrorCode.NOT_FOUND)
            version = self._advance(conn, packet, body.expected_review_version)
            rid = uuid4()
            conn.execute(m.resolutions.insert().values(id=rid, finding_id=finding_id, run_id=run_id,
                actor_id=owner, action=body.action, reason=body.reason, corrected_value=body.corrected_value,
                review_version=version, created_at=self.clock()))
            for eid in linked:
                conn.execute(m.resolution_evidence.insert().values(resolution_id=rid, evidence_id=eid, run_id=run_id))
            content = dict(finding_id=str(finding_id), action=body.action, status=STATUS[body.action],
                reason=body.reason, corrected_value=body.corrected_value,
                linked_evidence_ids=sorted(map(str, linked)),
                provenance="Reviewer supplied" if body.corrected_value is not None else None)
            return self._event(conn, packet, run["revision_id"], run_id, version, "resolution", content,
                "review:resolution", key, digest, rid)

    def save_draft(self, token, packet_id, body, key):
        with self._write() as conn:
            packet = self.packets._packet(conn, token, packet_id)
            prior, digest = self._previous(conn, packet, "review:draft", key, body)
            if prior:
                return self._replay(conn, packet, prior)
            revision = self._revision(conn, packet)
            if body.expected_revision != packet["current_revision"]:
                raise ApiError(ErrorCode.REVISION_CONFLICT, current_revision=packet["current_revision"])
            if body.run_id is not None:
                self._run(conn, packet, body.run_id)
            version = self._advance(conn, packet, body.expected_review_version)
            content = dict(mode=body.mode, fields={name: dict(value=value, provenance="Reviewer supplied")
                for name, value in body.fields.items()},
                automatic_check="Not automatically checked" if body.mode == "manual" else "Run findings reviewed separately")
            values = dict(revision_id=revision["id"], run_id=body.run_id, content=content, review_version=version)
            current = conn.execute(sa.select(m.handoff_drafts.c.packet_id).where(
                m.handoff_drafts.c.packet_id == packet_id)).first()
            if current:
                conn.execute(m.handoff_drafts.update().where(m.handoff_drafts.c.packet_id == packet_id).values(**values))
            else:
                conn.execute(m.handoff_drafts.insert().values(packet_id=packet_id, **values))
            return self._event(conn, packet, revision["id"], body.run_id, version, "draft", content,
                "review:draft", key, digest)

    def get_draft(self, token, packet_id):
        with self.engine.begin() as conn:
            packet = self.packets._packet(conn, token, packet_id)
            row = conn.execute(sa.select(m.review_events).where(m.review_events.c.packet_id == packet_id,
                m.review_events.c.kind == "draft").order_by(m.review_events.c.review_version.desc()).limit(1)).mappings().first()
            return HandoffDraftResponse(draft=ReviewEvent(**row) if row else None,
                stale=bool(row and row["revision_id"] != self._revision(conn, packet)["id"]))

    def _decisions(self, conn, run_id):
        latest = {}
        for row in conn.execute(sa.select(m.review_events).where(m.review_events.c.run_id == run_id,
            m.review_events.c.kind == "resolution").order_by(m.review_events.c.review_version)).mappings():
            latest[row["content"]["finding_id"]] = ReviewEvent(**row).model_dump(mode="json")
        return latest

    def _snapshot(self, conn, packet, sid):
        row = conn.execute(sa.select(m.review_snapshots).where(m.review_snapshots.c.id == sid,
            m.review_snapshots.c.packet_id == packet["id"])).mappings().first()
        if row is None:
            raise ApiError(ErrorCode.NOT_FOUND)
        return SnapshotResponse(**row, historical=(row["revision_id"] != self._revision(conn, packet)["id"]
            or row["review_version"] != packet["review_version"]))

    def confirm(self, token, packet_id, body, key):
        with self._write() as conn:
            packet = self.packets._packet(conn, token, packet_id)
            prior, digest = self._previous(conn, packet, "review:confirm", key, body)
            if prior:
                return self._snapshot(conn, packet, prior["resource_id"])
            revision = self._revision(conn, packet)
            if revision["id"] != body.revision_id:
                raise ApiError(ErrorCode.REVISION_CONFLICT, current_revision=packet["current_revision"])
            result, decisions, finding_states = None, {}, []
            if body.run_id is not None:
                run = self._run(conn, packet, body.run_id)
                result = load(conn, run).model_dump(mode="json")
                decisions = self._decisions(conn, body.run_id)
                for finding in result["findings"]:
                    decision = decisions.get(finding["id"])
                    status = decision["content"]["status"] if decision else "open"
                    finding_states.append(dict(finding_id=finding["id"], kind=finding["kind"], status=status))
                if any(item["status"] == "open" for item in finding_states):
                    raise ApiError(ErrorCode.OPEN_FINDINGS)
            draft = conn.execute(sa.select(m.handoff_drafts).where(m.handoff_drafts.c.packet_id == packet_id,
                m.handoff_drafts.c.revision_id == revision["id"],
                m.handoff_drafts.c.run_id == body.run_id)).mappings().first()
            version = self._advance(conn, packet, body.expected_review_version)
            unresolved = any(item["status"] == "unresolved" for item in finding_states)
            identity_unresolved = any(item["kind"] == "identity_mismatch" and item["status"] != "resolved"
                for item in finding_states)
            warnings = (["Identity unresolved"] if identity_unresolved else [])
            if body.mode == "manual":
                warnings.append("Not automatically checked")
            sid, now = uuid4(), self.clock()
            payload = dict(schema_version="review-snapshot-v1", packet_id=str(packet_id),
                revision_id=str(revision["id"]), revision_number=revision["revision_number"],
                manifest_hash=revision["manifest_hash"], run_id=str(body.run_id) if body.run_id else None,
                mode=body.mode, review_version=version, confirmed_by=str(packet["owner_id"]), confirmed_at=now.isoformat(),
                warnings=warnings, has_unresolved=unresolved, identity_unresolved=identity_unresolved,
                status="Reviewed — unresolved items remain" if unresolved else "Reviewed",
                result=result, decisions=decisions, finding_states=finding_states,
                handoff=draft["content"] if draft else dict(mode=body.mode, fields={}))
            conn.execute(m.review_snapshots.insert().values(id=sid, packet_id=packet_id, revision_id=revision["id"],
                run_id=body.run_id, review_version=version, confirmed_by=packet["owner_id"], confirmed_at=now,
                payload=payload, payload_hash=_hash(payload), has_unresolved=unresolved))
            self._event(conn, packet, revision["id"], body.run_id, version, "confirmation",
                dict(snapshot_id=str(sid), mode=body.mode, warnings=warnings), "review:confirm", key, digest, sid)
            return self._snapshot(conn, dict(packet, review_version=version), sid)

    def snapshot(self, token, packet_id, snapshot_id):
        with self.engine.begin() as conn:
            packet = self.packets._packet(conn, token, packet_id)
            return self._snapshot(conn, packet, snapshot_id)

    def history(self, token, packet_id, cursor=None, limit=20):
        if not 1 <= limit <= 50:
            raise ApiError(ErrorCode.SCHEMA_INVALID)
        with self.engine.begin() as conn:
            self.packets._packet(conn, token, packet_id)
            query = sa.select(m.review_events).where(m.review_events.c.packet_id == packet_id)
            if cursor:
                # Packet-scoped, authenticated cursor cannot be reused across packets.
                created, eid = self.packets._decode_cursor(cursor, packet_id)
                query = query.where(sa.or_(m.review_events.c.created_at < created,
                    sa.and_(m.review_events.c.created_at == created, m.review_events.c.id < eid)))
            rows = conn.execute(query.order_by(m.review_events.c.created_at.desc(), m.review_events.c.id.desc())
                .limit(limit + 1)).mappings().all()
            return ReviewHistory(items=[ReviewEvent(**row) for row in rows[:limit]],
                next_cursor=self.packets._cursor(packet_id, rows[limit - 1]) if len(rows) > limit else None)
