"""Transactional evaluation orchestration, currently isolated Fake rehearsal only.

No CLI or HTTP entry enables live dispatch. A future live entry must add actual
human consent/gold provenance and a reviewed provider/recording lifecycle.
"""
import asyncio
import json
import time
from typing import Literal
from uuid import UUID

from pydantic import Field, model_validator
import sqlalchemy as sa

from . import planning as p, runner
from .files import unique_json
from .journal import Journal
from referral_review.evaluation.ledger import EvaluationLedger, TERMINAL
from referral_review.extraction.adapters import FakeAdapter, ExtractionError
from referral_review.extraction.contracts import ExtractionRevision, TokenUsage
from referral_review.persistence import models as m


class Receipt(p.Frozen):
    format: Literal["evaluation-receipt-v1"] = "evaluation-receipt-v1"
    origin: Literal["fake"] = "fake"
    batch_id: UUID
    attempt_id: UUID
    plan_sha256: p.Hash
    sample_sha256: p.Hash
    request_sha256: p.Hash
    outcome: Literal["succeeded", "failed", "unknown"]
    error: Literal["MODEL_INVALID_OUTPUT", "MODEL_TRUNCATED", "MODEL_TIMEOUT", "MODEL_UNAVAILABLE"] | None
    output: dict | None
    usage: TokenUsage | None
    elapsed_ms: float = Field(ge=0, allow_inf_nan=False)

    @model_validator(mode="after")
    def coherent(self):
        if self.outcome == "succeeded":
            if self.output is None or self.error is not None:
                raise ValueError("Successful receipt requires output")
        elif self.output is not None or self.error is None:
            raise ValueError("Failed receipt cannot contain accepted output")
        if self.outcome == "unknown" and self.usage is not None:
            raise ValueError("Unknown receipt cannot claim usage")
        return self


def sample_hash(sample):
    return p.digest(sample.model_dump(mode="json"))


def rehearsal_only(settings):
    if settings.environment != "test":
        raise ValueError("Evaluation orchestration currently requires an isolated test environment")


def attempts(ledger, plan):
    with ledger._transaction() as conn:
        batch = conn.execute(sa.select(m.evaluation_batches).where(
            m.evaluation_batches.c.id == plan.batch_id)).mappings().first()
        if not batch:
            return {}
        if (batch["plan_hash"], batch["cap_microusd"], batch["model"], batch["price_version"],
            batch["input_price"], batch["output_price"]) != (
            plan.sha256, plan.max_cost_microusd, plan.model, plan.price_version, plan.input_price, plan.output_price):
            raise ValueError("Ledger belongs to a different plan")
        corrections = sa.select(sa.func.coalesce(sa.func.sum(m.evaluation_adjustments.c.delta_microusd), 0)).where(
            m.evaluation_adjustments.c.attempt_id == m.evaluation_attempts.c.id).scalar_subquery()
        corrected = sa.exists().where(m.evaluation_adjustments.c.attempt_id == m.evaluation_attempts.c.id)
        rows = conn.execute(sa.select(m.evaluation_attempts, corrections.label("adjustment_microusd"),
                                     corrected.label("usage_corrected")).where(
            m.evaluation_attempts.c.batch_id == plan.batch_id)).mappings().all()
    selected = {sample_hash(s) for s in plan.samples if s.rejection is None}
    if any(row["sample_hash"] not in selected for row in rows):
        raise ValueError("Unexpected ledger attempt")
    return {r["sample_hash"]: dict(r) for r in rows}


def recording(journal, plan, sample, row):
    data = journal.read(sample.key + ".json")
    if data is None:
        return None
    receipt = Receipt.model_validate(data)
    if (receipt.batch_id, receipt.attempt_id, receipt.plan_sha256, receipt.sample_sha256,
        receipt.request_sha256) != (plan.batch_id, row["id"], plan.sha256, sample_hash(sample), sample.request_sha256):
        raise ValueError("Recording does not match ledger attempt")
    if row["dispatched_at"] is None:
        raise ValueError("Recording without dispatch marker")
    return receipt


def receipt_key(receipt):
    return "receipt:" + p.digest(receipt.model_dump(mode="json"))


def reconcile(ledger, plan, journal):
    """Settle only this plan. No parsing, invitations, current prices or transport.

    Durable replies precede settlement, so a crash can safely repeat settlement.
    Missing replies retain unknown cost; recovery never retries the model.
    """
    rows = attempts(ledger, plan)
    for sample in plan.samples:
        row = rows.get(sample_hash(sample))
        if row is None:
            continue
        receipt = recording(journal, plan, sample, row)
        if receipt is not None:
            # Preserve the original estimate/outcome and append trusted late usage.
            if row["state"] == "estimated_spent" and receipt.outcome != "unknown":
                if receipt.usage is not None:
                    ledger.adjust(plan.batch_id, row["id"], adjustment_key=receipt_key(receipt), usage=receipt.usage)
                continue
            ledger.settle(plan.batch_id, row["id"], outcome=receipt.outcome, usage=receipt.usage)
        elif row["state"] not in TERMINAL and row["lease_expires_at"] <= ledger.clock():
            ledger.settle(plan.batch_id, row["id"],
                          outcome="cancelled" if row["dispatched_at"] is None else "unknown")
    return snapshot(ledger, plan, journal)


def snapshot(ledger, plan, journal):
    rows = attempts(ledger, plan)
    samples = []
    for sample in plan.samples:
        row = rows.get(sample_hash(sample))
        receipt = recording(journal, plan, sample, row) if row else None
        applied = False
        if receipt and receipt.usage and row["state"] == "estimated_spent":
            with ledger._transaction() as conn:
                applied = conn.execute(sa.select(sa.exists().where(
                    m.evaluation_adjustments.c.attempt_id == row["id"],
                    m.evaluation_adjustments.c.adjustment_key == receipt_key(receipt)))).scalar_one()
        base = row["actual_microusd"] if row else None
        samples.append(dict(key=sample.key, state=row["state"] if row else "rejected" if sample.rejection else "not_started",
            error=receipt.error if receipt else sample.rejection, outcome=row["outcome"] if row else None,
            recorded=receipt is not None, settlement_microusd=base,
            adjustment_microusd=row["adjustment_microusd"] if row else 0,
            simulated_microusd=base + row["adjustment_microusd"] if base is not None else None,
            cost_status="known" if row and (row["state"] == "settled" or row["usage_corrected"]) else
                        "estimated" if row and row["state"] == "estimated_spent" else
                        "released" if row and row["state"] == "released" else "unsettled",
            late_usage_pending=bool(receipt and receipt.usage and row["state"] == "estimated_spent" and not applied)))
    return dict(origin="fake", real_measurement=False, plan_sha256=plan.sha256, total=len(samples), samples=samples)


def recover_recordings(engine, settings, plan, *, clock=m.utcnow):
    rehearsal_only(settings)
    with Journal(plan, resume=True) as journal:
        return reconcile(EvaluationLedger(engine, settings, clock), plan, journal)


async def replay_recordings(plan):
    """Recompute provisional metrics without DB, keys or adapter. Keep every sample."""
    _, cases = runner.load_cases(plan.split, expected_manifest=plan.corpus_sha256, expected_freeze=plan.freeze_sha256)
    selected = {e["key"]: (packet, directory) for e, packet, directory in cases}
    rows = []
    with Journal(plan, resume=True) as journal:
        for sample in plan.samples:
            packet, directory = selected[sample.key]
            docs, issue = runner.parse_case(packet, directory)
            pages = [pg for d in docs for pg in d["pages"]]
            page_map = {(str(pg.document_id), pg.page_number): pg.normalized_text for pg in pages}
            data = journal.read(sample.key + ".json")
            result = None
            error = issue or sample.rejection
            status = "rejected" if error else "failed"
            if data is not None:
                receipt = Receipt.model_validate(data)
                if (receipt.plan_sha256, receipt.batch_id, receipt.sample_sha256, receipt.request_sha256) != (
                    plan.sha256, plan.batch_id, sample_hash(sample), sample.request_sha256):
                    raise ValueError("Recording does not match selected sample")
                if error is None:
                    error = receipt.error
                    if receipt.outcome == "succeeded":
                        try:
                            result = await runner.execute(packet, docs, "replay", receipt.output)
                            status = "succeeded"
                        except (ExtractionError, ValueError, TypeError, KeyError):
                            error = "MODEL_INVALID_OUTPUT"
            elif error is None:
                error = "EVALUATION_RECORDING_MISSING_OUTPUT"
            metrics = runner.score(result, packet["gold"]["result"], page_map) if packet["gold"]["automated_review_allowed"] else None
            rows.append(dict(key=sample.key, status=status, error=error, metrics=metrics))
    return dict(provider="replay", origin="fake", real_measurement=False,
                recorded_implementation=plan.implementation_sha256, current_implementation=p.implementation_hash(),
                annotation_status=plan.annotation_status, summary=runner.aggregate(rows), rows=rows)


class EvaluationSession:
    def __init__(self, engine, settings, plan, *, approval, resume=False, clock=m.utcnow):
        rehearsal_only(settings)
        self.plan = p.Plan.model_validate_json(p.canonical(plan.model_dump(mode="json")))
        self.settings, self.approval = settings, dict(approval)
        self.ledger = EvaluationLedger(engine, settings, clock)
        self.journal = None
        try:
            if resume:
                self.journal = Journal(self.plan, resume=True)
            self._check(require_new_output=not resume)
            if not resume:
                self.journal = Journal(self.plan)
        except BaseException:
            self.close()
            raise

    def close(self):
        if self.journal is not None:
            self.journal.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def _check(self, *, require_new_output=False):
        p.validate_approval_binding(self.plan, settings=self.settings,
                                    require_new_output=require_new_output, **self.approval)

    async def execute(self, key, adapter):
        rehearsal_only(self.settings)
        # Exact built-in Fake only: an arbitrary subclass cannot hide a network client.
        if type(adapter) is not FakeAdapter:
            raise ValueError("Live evaluation transport remains disabled")
        if self.journal is None or self.journal.directory is None:
            raise ValueError("Session is closed")
        self._check()
        sample = next((s for s in self.plan.samples if s.key == key), None)
        if sample is None:
            raise ValueError("Sample is not in this plan")
        if sample.rejection is not None:
            return snapshot(self.ledger, self.plan, self.journal)
        _, cases = runner.load_cases(self.plan.split, expected_manifest=p.MANIFEST_SHA256, expected_freeze=p.FREEZE_SHA256)
        _, packet, directory = next(c for c in cases if c[0]["key"] == key)
        docs, issue = runner.parse_case(packet, directory)
        if issue:
            raise ValueError("Reviewed input is no longer parseable")
        revision = ExtractionRevision(revision_id=runner.uid(key + ":revision"), pages=[pg for d in docs for pg in d["pages"]])
        request = p.bound_request(self.plan, key, revision)
        # User lock precedes batch/attempt/control/budget/slot locks. No external
        # calls or parsing inside this transaction, and no transport until commit.
        with self.ledger._transaction() as conn:
            p.require_operator(conn, self.plan, self.settings)
            self.ledger.open_batch(self.plan.batch_id, plan_hash=self.plan.sha256,
                                   max_cost_usd=self.approval["approved_max_cost_usd"], connection=conn)
            row = self.ledger.reserve(self.plan.batch_id, sample_hash=sample_hash(sample),
                input_bound=sample.input_bound, output_limit=self.plan.output_limit, connection=conn)
            if row["state"] == "reserved":
                row = self.ledger.record_dispatch(self.plan.batch_id, row["id"], connection=conn)
            else:
                # Existing markers are never permission to repeat transport.
                return dict(origin="fake", repeated=True, state=row["state"])
        started = time.monotonic()
        output = usage = error = None
        outcome = "succeeded"
        cancelled = False
        try:
            async with asyncio.timeout(130):
                reply = await adapter.complete(json.loads(request))
            if reply.usage is not None:
                usage = TokenUsage.model_validate(reply.usage.model_dump())
            if len(reply.content.encode()) > 128_000:
                raise ValueError("Output limit")
            output = unique_json(reply.content)
            await runner.execute(packet, docs, "replay", output)
        except (TimeoutError, asyncio.CancelledError) as exc:
            cancelled = isinstance(exc, asyncio.CancelledError)
            outcome, error, output, usage = "unknown", "MODEL_TIMEOUT", None, None
        except ExtractionError as exc:
            error = exc.code if exc.code in ("MODEL_TIMEOUT", "MODEL_UNAVAILABLE", "MODEL_TRUNCATED") else "MODEL_INVALID_OUTPUT"
            outcome = "unknown" if error in ("MODEL_TIMEOUT", "MODEL_UNAVAILABLE") else "failed"
            output = None
            usage = exc.usage if outcome == "failed" else None
        except (ValueError, TypeError, KeyError, AttributeError, RecursionError):
            outcome, error, output = "failed", "MODEL_INVALID_OUTPUT", None
        receipt = Receipt(batch_id=self.plan.batch_id, attempt_id=row["id"], plan_sha256=self.plan.sha256,
            sample_sha256=sample_hash(sample), request_sha256=sample.request_sha256, outcome=outcome,
            error=error, output=output, usage=usage, elapsed_ms=(time.monotonic() - started) * 1000)
        self.journal.write(sample.key + ".json", receipt.model_dump(mode="json"))
        self.ledger.settle(self.plan.batch_id, row["id"], outcome=outcome, usage=usage)
        if cancelled:
            raise asyncio.CancelledError
        return snapshot(self.ledger, self.plan, self.journal)
