"""Request-bound execution; no worker, retries, or read-triggered recovery/provider calls."""
import asyncio
import time
from datetime import timedelta
from uuid import uuid4

import sqlalchemy as sa
from starlette.concurrency import run_in_threadpool

from ..checklist import CHECKLIST_VERSION, ChecklistManifest, evaluate
from ..errors import ApiError
from ..extraction import DeepSeekAdapter, ExtractionError, ExtractionRevision, FakeAdapter, extract
from ..extraction.contracts import PROMPT_VERSION, SCHEMA_VERSION
from ..extraction.service import prepare_request
from ..packets import Packets
from ..packets.service import _hash
from ..persistence import models as m
from ..persistence.migrations import require_current_schema
from ..schemas import DocumentPageResponse, ErrorCode, RunResponse
from ..usage import Usage, rates
from . import results
from ..operations.telemetry import audit, observe

PENDING_TTL = timedelta(minutes=30)
LEASE = timedelta(seconds=240)
APPLICATION_TIMEOUT = 180


class Runs:
    def __init__(self, identity, *, adapter_factory=None, fault=None):
        self.identity, self.engine, self.clock = identity, identity.engine, identity.clock
        self.settings = identity.settings
        self.usage, self.packets = Usage(identity), Packets(identity)
        self.adapter_factory = adapter_factory  # In-process test seam; no HTTP/environment switch.
        self.fault = fault or (lambda stage: None)

    def _owned(self, conn, token, rid):
        require_current_schema(conn)
        owner = self.identity.require_user(conn, token)
        row = conn.execute(sa.select(m.runs).where(m.runs.c.id == rid, m.runs.c.owner_id == owner)).mappings().first()
        if row is None:
            raise ApiError(ErrorCode.NOT_FOUND)
        packet = self.identity.require_owner(conn, token, row["packet_id"])
        row = conn.execute(sa.select(m.runs).where(m.runs.c.id == rid).with_for_update()).mappings().one()
        return row, packet

    def _current(self, conn, run, packet):
        revision = conn.execute(sa.select(m.revisions).where(m.revisions.c.id == run["revision_id"],
            m.revisions.c.packet_id == packet["id"])).mappings().first()
        if not revision or revision["revision_number"] != packet["current_revision"]:
            raise ApiError(ErrorCode.SOURCE_CHANGED)
        return revision

    def _source(self, conn, revision_id, packet_id):
        docs = conn.execute(sa.select(m.documents).join(m.revision_documents,
            m.revision_documents.c.document_id == m.documents.c.id).where(
                m.revision_documents.c.revision_id == revision_id, m.documents.c.packet_id == packet_id)
            .order_by(m.revision_documents.c.ordinal)).mappings().all()
        manifests, pages = [], []
        if not docs:
            raise ApiError(ErrorCode.PARSE_COVERAGE_INCOMPLETE)
        for doc in docs:
            rows = conn.execute(sa.select(m.document_pages).where(m.document_pages.c.document_id == doc["id"])
                                .order_by(m.document_pages.c.page_number)).mappings().all()
            if (doc["parse_status"] != "ready" or doc["deleted_at"] is not None or not doc["page_count"]
                or len(rows) != doc["page_count"] or [p["page_number"] for p in rows] != list(range(1, doc["page_count"] + 1))):
                raise ApiError(ErrorCode.PARSE_COVERAGE_INCOMPLETE)
            parsed = [DocumentPageResponse(**dict(p), parser_version=doc["parser_version"]) for p in rows]
            pages.extend(parsed)
            manifests.append(dict(id=doc["id"], title=doc["filename"], kind=doc["kind"], parse_status="ready",
                                  page_count=doc["page_count"], pages=parsed))
        try:
            return (ExtractionRevision(revision_id=revision_id, pages=pages),
                    ChecklistManifest(revision_id=revision_id, documents=manifests))
        except ValueError:
            raise ApiError(ErrorCode.PARSE_COVERAGE_INCOMPLETE) from None

    def _public(self, conn, row, packet):
        revision = conn.execute(sa.select(m.revisions.c.revision_number).where(m.revisions.c.id == row["revision_id"])).scalar_one()
        state = row["state"]
        phase = {"pending": "pending", "running": "dispatched" if row["provider_dispatched_at"] else "reserved",
                 "succeeded": "complete", "failed": "failed", "outcome_unknown": "unknown", "cancelled": "cancelled"}[state]
        return RunResponse(**{key: row[key] for key in RunResponse.model_fields if key not in ("stale", "phase", "result")},
                           stale=revision != packet["current_revision"], phase=phase,
                           result=results.load(conn, row) if state == "succeeded" else None)

    def create(self, token, packet_id, body, key):
        with self.engine.begin() as conn:
            require_current_schema(conn)
            packet = self.identity.require_owner(conn, token, packet_id)
            owner = packet["owner_id"]
            prior, digest = self.packets._previous(conn, owner, f"run:create:{packet_id}", key, body.model_dump(mode="json"))
            if prior:
                row, packet = self._owned(conn, token, prior["resource_id"])
                return self._public(conn, row, packet)
            if body.checklist_version != CHECKLIST_VERSION:
                raise ApiError(ErrorCode.CHECKLIST_UNSUPPORTED)
            revision = self._current(conn, {"revision_id": body.revision_id}, packet)
            if packet["synthetic_ack_at"] is None:
                raise ApiError(ErrorCode.SCHEMA_INVALID)
            source, _ = self._source(conn, body.revision_id, packet_id)
            if self.settings.mode == "bundled_demo":
                raise ApiError(ErrorCode.REAL_AI_NOT_ALLOWED)
            real = (self.settings.mode == "invited_real" and self.settings.real_ai_enabled
                    and owner in self.settings.real_ai_user_ids)
            if real:
                self.usage._real_configuration(owner)
            mode = "real" if real else "fake"
            model = self.settings.model_id if real else "fake-extraction-v1"
            try:
                prepare_request(source, model)
            except ExtractionError:
                raise ApiError(ErrorCode.MODEL_INPUT_LIMIT) from None
            input_hash = _hash({"manifest": revision["manifest_hash"], "pages": source.model_dump(mode="json"),
                                "prompt": PROMPT_VERSION, "schema": SCHEMA_VERSION, "model": model})
            row = conn.execute(sa.select(m.runs).where(m.runs.c.packet_id == packet_id,
                m.runs.c.revision_id == body.revision_id, m.runs.c.checklist_version == body.checklist_version,
                m.runs.c.mode == mode, m.runs.c.input_hash == input_hash, m.runs.c.state.in_(("pending", "running")))).mappings().first()
            if row and row["state"] == "pending" and row["created_at"] + PENDING_TTL <= self.clock():
                conn.execute(m.runs.update().where(m.runs.c.id == row["id"]).values(state="cancelled", error_code="PENDING_EXPIRED", finished_at=self.clock()))
                row = None
            if row is None:
                row = conn.execute(m.runs.insert().values(id=uuid4(), packet_id=packet_id, owner_id=owner,
                    revision_id=body.revision_id, checklist_version=body.checklist_version, mode=mode, state="pending",
                    input_hash=input_hash, prompt_version=PROMPT_VERSION, schema_version=SCHEMA_VERSION,
                    model_requested=model, created_at=self.clock()).returning(m.runs)).mappings().one()
            self.packets._record(conn, owner, f"run:create:{packet_id}", key, digest, row["id"])
            audit(conn, row, "created", self.clock())
            return self._public(conn, row, packet)

    def latest(self, token, packet_id):
        """Read-only refresh recovery, including stale/unknown runs; never dispatch."""
        with self.engine.begin() as conn:
            require_current_schema(conn)
            packet = self.identity.require_owner(conn, token, packet_id)
            row = conn.execute(sa.select(m.runs).where(m.runs.c.packet_id == packet_id,
                m.runs.c.owner_id == packet["owner_id"]).order_by(
                m.runs.c.created_at.desc(), m.runs.c.id.desc()).limit(1)).mappings().first()
            return self._public(conn, row, packet) if row else None

    def get(self, token, rid):
        with self.engine.begin() as conn:
            row, packet = self._owned(conn, token, rid)
            return self._public(conn, row, packet)

    def bind_operation(self, token, rid, action, key):
        """Bind an HTTP idempotency key to one owner/action/run; state machine prevents replay dispatch."""
        with self.engine.begin() as conn:
            row, _ = self._owned(conn, token, rid)
            audit(conn, row, action, self.clock())
            operation = f"run:{action}"
            prior, digest = self.packets._previous(conn, row["owner_id"], operation, key, {"run_id": str(rid)})
            if prior is None:
                self.packets._record(conn, row["owner_id"], operation, key, digest, rid)

    def cancel(self, token, rid):
        with self.engine.begin() as conn:
            row, packet = self._owned(conn, token, rid)
            if row["state"] == "cancelled":
                return self._public(conn, row, packet)
            if row["state"] != "pending":
                raise ApiError(ErrorCode.RUN_ACTIVE)
            conn.execute(m.runs.update().where(m.runs.c.id == rid).values(state="cancelled", finished_at=self.clock()))
            row = dict(row) | {"state": "cancelled", "finished_at": self.clock()}
            return self._public(conn, row, packet)

    def _attempt(self, token, rid):
        with self.engine.begin() as conn:
            row, packet = self._owned(conn, token, rid)
            if row["state"] != "pending":
                return False
            if row["created_at"] + PENDING_TTL <= self.clock():
                conn.execute(m.runs.update().where(m.runs.c.id == rid).values(state="cancelled", error_code="PENDING_EXPIRED", finished_at=self.clock()))
                return False
            rates.consume(conn, row["owner_id"], "execute", self.clock())
            return True

    def _claim(self, token, rid):
        with self.engine.begin() as conn:
            row, packet = self._owned(conn, token, rid)
            if row["state"] != "pending":
                return None
            if row["created_at"] + PENDING_TTL <= self.clock():
                conn.execute(m.runs.update().where(m.runs.c.id == rid).values(state="cancelled", error_code="PENDING_EXPIRED", finished_at=self.clock()))
                return None
            self._current(conn, row, packet)
            if row["prompt_version"] != PROMPT_VERSION or row["schema_version"] != SCHEMA_VERSION:
                raise ApiError(ErrorCode.USAGE_CONFLICT)
            if row["mode"] == "real" and row["model_requested"] != self.settings.model_id:
                raise ApiError(ErrorCode.REAL_AI_NOT_ALLOWED)
            source, manifest = self._source(conn, row["revision_id"], row["packet_id"])
            try:
                _, bound = prepare_request(source, row["model_requested"])
            except ExtractionError:
                raise ApiError(ErrorCode.MODEL_INPUT_LIMIT) from None
            self.fault("before_reserve")
            self.usage.reserve(row["owner_id"], rid, input_bound=bound, connection=conn)
            self.fault("after_reserve")
            claimed = conn.execute(m.runs.update().where(m.runs.c.id == rid, m.runs.c.state == "pending",
                m.runs.c.provider_dispatched_at.is_(None)).values(state="running", lease_expires_at=self.clock() + LEASE)).rowcount
            if claimed != 1:
                raise ApiError(ErrorCode.RUN_ACTIVE)
            audit(conn, row, "reserved", self.clock())
            return dict(row), source, manifest

    def _dispatch(self, token, rid):
        with self.engine.begin() as conn:
            row, packet = self._owned(conn, token, rid)
            self._current(conn, row, packet)
            if row["state"] != "running" or row["provider_dispatched_at"] is not None or row["lease_expires_at"] <= self.clock():
                raise ApiError(ErrorCode.RUN_ACTIVE)
            member = self.usage._member(conn, row["owner_id"])
            reservation = self.usage._prior(conn, rid)
            if (not reservation or reservation["state"] != "reserved"
                or reservation["membership_id"] != member["id"]):
                raise ApiError(ErrorCode.USAGE_CONFLICT)
            if row["mode"] == "real":
                self.usage._real_configuration(row["owner_id"])
                if self.usage._control(conn)["halted"]:
                    raise ApiError(ErrorCode.BUDGET_EXHAUSTED)
            self.fault("before_dispatch_marker")
            conn.execute(m.runs.update().where(m.runs.c.id == rid).values(provider_dispatched_at=self.clock()))
            audit(conn, row, "dispatched", self.clock())

    def _finish(self, owner, rid, extraction, evaluation, deadline):
        def check_deadline():
            if time.monotonic() >= deadline:
                raise TimeoutError()
        check_deadline()
        with self.engine.begin() as conn:
            row = self.usage._run(conn, owner, rid, active=False)
            if row["state"] not in ("running", "outcome_unknown"):
                return
            packet = conn.execute(sa.select(m.packets).where(m.packets.c.id == row["packet_id"])).mappings().one()
            disabled = conn.execute(sa.select(m.users.c.disabled_at).where(m.users.c.id == owner)).scalar_one()
            deleted = packet["deleted_at"] is not None or packet["expires_at"] <= self.clock() or disabled is not None
            outcome = "failed" if deleted else "succeeded"
            self.usage.settle(owner, rid, outcome=outcome, usage=extraction.usage, connection=conn)
            if not deleted:
                results.persist(conn, row, extraction, evaluation, check_deadline)
            self.fault("before_result_commit")
            check_deadline()
            conn.execute(m.runs.update().where(m.runs.c.id == rid).values(state=outcome,
                error_code="SOURCE_DELETED" if deleted else None, model_reported=extraction.model_reported,
                provider_request_id=extraction.provider_request_id, usage=extraction.usage.model_dump() if extraction.usage else None,
                finished_at=self.clock()))

            audit(conn, row, "complete", self.clock())

    def _error(self, owner, rid, code, *, uncertain=False, error=None):
        with self.engine.begin() as conn:
            row = self.usage._run(conn, owner, rid, active=False)
            if row["state"] not in ("running", "outcome_unknown"):
                return
            unknown = uncertain and row["provider_dispatched_at"] is not None
            usage = getattr(error, "usage", None)
            self.usage.settle(owner, rid, outcome="unknown" if unknown else "failed", usage=usage, connection=conn)
            conn.execute(m.runs.update().where(m.runs.c.id == rid).values(state="outcome_unknown" if unknown else "failed",
                error_code=code, usage=usage.model_dump() if usage else None,
                model_reported=getattr(error, "model_reported", None), provider_request_id=getattr(error, "provider_request_id", None),
                finished_at=self.clock()))
            audit(conn, row, "failed", self.clock())

    async def execute(self, token, rid):
        started = time.monotonic()
        try:
            return await self._execute(token, rid)
        finally:
            await run_in_threadpool(observe, self.engine, rid, "complete", int((time.monotonic() - started) * 1000))

    async def _execute(self, token, rid):
        claim = None
        database_task = None
        database_operation = None
        deadline = time.monotonic() + APPLICATION_TIMEOUT

        async def database(operation, *args):
            nonlocal database_task, database_operation
            database_operation = operation.__name__
            database_task = asyncio.create_task(run_in_threadpool(operation, *args))
            # Cancelling an await cannot stop a DB worker thread. Retain its handle
            # and join it before starting recovery on another connection.
            return await asyncio.shield(database_task)

        try:
            async with asyncio.timeout(APPLICATION_TIMEOUT):
                if not await database(self._attempt, token, rid):
                    return await run_in_threadpool(self.get, token, rid)
                claim = await database(self._claim, token, rid)
                if claim is None:
                    return await run_in_threadpool(self.get, token, rid)
                row, source, manifest = claim
                await run_in_threadpool(observe, self.engine, rid, "reserved")
                self.fault("after_claim_commit")
                adapter = (self.adapter_factory(row, source) if self.adapter_factory else
                           DeepSeekAdapter(self.settings.deepseek_key) if row["mode"] == "real" else FakeAdapter({"facts": []}))
                if adapter.mode != row["mode"]:
                    raise ApiError(ErrorCode.REAL_AI_NOT_ALLOWED)
                await database(self._dispatch, token, rid)
                await run_in_threadpool(observe, self.engine, rid, "dispatched")
                self.fault("after_dispatch_marker")
                if time.monotonic() >= deadline:
                    raise TimeoutError()
                extraction = await extract(source, self.settings, adapter)
                self.fault("after_response")
                evaluation = evaluate(extraction, manifest, row["checklist_version"])
                await database(self._finish, row["owner_id"], rid, extraction, evaluation, deadline)
        except ExtractionError as exc:
            if claim:
                await run_in_threadpool(self._error, claim[0]["owner_id"], rid, exc.code,
                    uncertain=exc.code in ("MODEL_TIMEOUT", "MODEL_UNAVAILABLE"), error=exc)
            else:
                raise ApiError(ErrorCode.MODEL_INPUT_LIMIT) from None
        except ApiError as exc:
            if claim:
                await run_in_threadpool(self._error, claim[0]["owner_id"], rid, exc.code.value)
            raise
        except (TimeoutError, asyncio.CancelledError):
            # Join any DB worker before recovery; otherwise its rollback/commit
            # can race recovery and leave a stale SQLite snapshot or a lock wait.
            if database_task is not None:
                try:
                    completed = await asyncio.shield(database_task)
                    if database_operation == "_claim" and claim is None:
                        claim = completed
                except Exception:
                    pass  # Transaction failed/rolled back; durable state is authoritative.
            # On process death this may not run; explicit reconcile follows the same durable marker.
            if claim:
                await run_in_threadpool(self._error, claim[0]["owner_id"], rid, "EXECUTION_INTERRUPTED", uncertain=True)
            if asyncio.current_task().cancelling():
                raise
        except Exception:
            # A commit failure could be ambiguous. Never dispatch again to recover it.
            if claim:
                await run_in_threadpool(self._error, claim[0]["owner_id"], rid, "EXECUTION_INTERRUPTED", uncertain=True)
            else:
                raise ApiError(ErrorCode.INTERNAL_ERROR) from None
        return await run_in_threadpool(self.get, token, rid)

    def reconcile(self, token, rid):
        with self.engine.begin() as conn:
            row, packet = self._owned(conn, token, rid)
            if row["state"] == "pending" and row["created_at"] + PENDING_TTL <= self.clock():
                conn.execute(m.runs.update().where(m.runs.c.id == rid).values(state="cancelled", error_code="PENDING_EXPIRED", finished_at=self.clock()))
            elif row["state"] == "running" and row["lease_expires_at"] <= self.clock():
                dispatched = row["provider_dispatched_at"] is not None
                self.usage.settle(row["owner_id"], rid, outcome="unknown" if dispatched else "failed", connection=conn)
                conn.execute(m.runs.update().where(m.runs.c.id == rid).values(
                    state="outcome_unknown" if dispatched else "failed", error_code="LEASE_EXPIRED", finished_at=self.clock()))
            elif row["state"] == "outcome_unknown":
                self.usage.settle(row["owner_id"], rid, outcome="unknown", connection=conn)
            row = conn.execute(sa.select(m.runs).where(m.runs.c.id == rid)).mappings().one()
            return self._public(conn, row, packet)
