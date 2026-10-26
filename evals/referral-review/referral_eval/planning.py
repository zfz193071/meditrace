"""Reviewable real-evaluation preflight. No transport, ledger writes or approvals.

The privileged future runner must call these checks and still enforce human
annotation review, atomic ledger/dispatch authorization and durable recording.
"""
import argparse
import hashlib
import hmac
import json
import os
import re
from pathlib import Path
from typing import Annotated, Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator

from . import runner
from .files import fixture_bytes, unique_json
from referral_review.config import Settings
from referral_review.errors import ApiError
from referral_review.evaluation.ledger import cap_microusd
from referral_review.extraction.contracts import ExtractionRevision
from referral_review.extraction.service import prepare_request
from referral_review.extraction.adapters import ExtractionError
from referral_review.persistence.migrations import require_current_schema
from referral_review.usage import budget, rates

# Reviewed synthetic v1 corpus, not a caller-supplied "synthetic": true flag.
# Update only after reviewing an intentional corpus revision; never auto-refresh.
MANIFEST_SHA256 = "7d4e1ef1217a5a9978a9725a122336151ea80d970798c8d8cc5d9bb36d6ba12f"
FREEZE_SHA256 = "c580820cfef2390ee81d5e7768d272cd7dd3a4aa697800adc11a574cd0590dd5"
Hash = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
Identifier = Annotated[str, Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,199}$")]
Amount = Annotated[int, Field(strict=True, ge=1, le=2**62)]


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


class Frozen(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)


class Sample(Frozen):
    key: Annotated[str, Field(pattern=r"^(dev|test)-[0-9]{2}$")]
    packet_sha256: Hash
    request_sha256: Hash | None
    input_bound: Annotated[int, Field(strict=True, ge=0, le=16000)]
    upper_microusd: Annotated[int, Field(strict=True, ge=0, le=2**62)]
    rejection: str | None

    @model_validator(mode="after")
    def coherent(self):
        if self.rejection is None:
            if self.request_sha256 is None or self.input_bound == 0 or self.upper_microusd == 0:
                raise ValueError("Incomplete callable sample")
        elif self.request_sha256 is not None or self.input_bound != 0 or self.upper_microusd != 0:
            raise ValueError("Rejected sample cannot reserve provider cost")
        return self


class Plan(Frozen):
    format: Literal["evaluation-plan-v1"] = "evaluation-plan-v1"
    batch_id: UUID
    operator_id: UUID
    split: Literal["dev", "test"]
    output: str
    model: Identifier
    price_version: Annotated[str, Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,99}$")]
    input_price: Amount
    output_price: Amount
    max_cost_microusd: Amount
    output_limit: Annotated[int, Field(strict=True, ge=1, le=6000)] = 6000
    corpus_sha256: Hash
    freeze_sha256: Hash
    implementation_sha256: Hash
    prompt_version: str
    schema_version: str
    checklist_version: str
    parser_version: str
    annotation_status: Literal["provisional_operator_review_pending"]
    samples: tuple[Sample, ...] = Field(min_length=1, max_length=20)

    @model_validator(mode="after")
    def coherent(self):
        keys = [s.key for s in self.samples]
        if len(set(keys)) != len(keys) or any(not k.startswith(self.split + "-") for k in keys):
            raise ValueError("Invalid selected samples")
        if not Path(self.output).is_absolute():
            raise ValueError("Absolute output directory required")
        return self

    @property
    def sha256(self):
        return digest(self.model_dump(mode="json"))

    @property
    def upper_microusd(self):
        return sum(s.upper_microusd for s in self.samples)


def implementation_hash():
    # Accounting and CLI changes must invalidate old consent just like prompts.
    paths = [runner.ROOT / "evals/referral-review", runner.ROOT / "src/backend/referral_review"]
    files = sorted([p for root in paths for p in root.rglob("*.py")] +
                   [runner.ROOT / "src/backend" / name for name in ("uv.lock", "pyproject.toml", "requirements.txt")])
    return digest([(str(p.relative_to(runner.ROOT)), runner.sha(p.read_bytes())) for p in files])


def build_plan(*, batch_id, operator_id, split, output, model, price_version,
               input_price, output_price, max_cost_usd, output_limit=6000,
               packet_keys=None, ack_test_exposure=False):
    if split == "test" and not ack_test_exposure:
        raise ValueError("Frozen test planning requires explicit exposure acknowledgement")
    if runner.sha(fixture_bytes(runner.CORPUS, "manifest.json")) != MANIFEST_SHA256 or runner.sha(
        fixture_bytes(runner.CORPUS, "freeze.json")) != FREEZE_SHA256:
        raise ValueError("Unreviewed corpus revision")
    manifest, cases = runner.load_cases(split)
    selected = set(packet_keys) if packet_keys is not None else {e["key"] for e, _, _ in cases}
    if (not selected or packet_keys is not None and len(selected) != len(packet_keys)
        or not selected.issubset({e["key"] for e, _, _ in cases})):
        raise ValueError("Invalid sample selection")
    # Validate settings before doing potentially expensive parsing. No keys/env.
    pricing = Settings(RR_MODEL_ID=model, RR_MODEL_PRICE_VERSION=price_version,
        RR_MODEL_INPUT_MICROUSD_PER_MILLION_TOKENS=input_price,
        RR_MODEL_OUTPUT_MICROUSD_PER_MILLION_TOKENS=output_price)
    if type(input_price) is not int or type(output_price) is not int or min(input_price, output_price) <= 0:
        raise ValueError("Positive integer prices required")
    cap = cap_microusd(max_cost_usd)
    output = str(Path(output).resolve())
    if Path(output).exists():
        raise ValueError("Report output directory must be new")
    samples = []
    for entry, packet, directory in cases:
        if entry["key"] not in selected: continue
        docs, issue = runner.parse_case(packet, directory)
        request_hash, bound, upper = None, 0, 0
        if issue is None:
            try:
                revision = ExtractionRevision(revision_id=runner.uid(packet["key"] + ":revision"),
                    pages=[p for d in docs for p in d["pages"]])
                request, bound = prepare_request(revision, pricing.model_id, output_limit)
                request_hash = digest(request)
                upper = budget.cost(bound, output_limit, input_price, output_price)
            except ExtractionError as exc:
                if exc.code != "MODEL_INPUT_LIMIT": raise
                issue, bound = "MODEL_INPUT_LIMIT", 0
        samples.append(Sample(key=entry["key"], packet_sha256=entry["sha256"], request_sha256=request_hash,
                              input_bound=bound, upper_microusd=upper, rejection=issue))
    v = runner.versions()
    return Plan(batch_id=batch_id, operator_id=operator_id, split=split, output=output,
        model=model, price_version=price_version, input_price=input_price, output_price=output_price,
        max_cost_microusd=cap, output_limit=output_limit, corpus_sha256=MANIFEST_SHA256, freeze_sha256=FREEZE_SHA256,
        implementation_sha256=implementation_hash(), prompt_version=v["prompt"], schema_version=v["schema"],
        checklist_version=v["checklist"], parser_version=v["parser"], annotation_status=manifest["annotation_status"],
        samples=tuple(samples))


def rebuild(plan):
    return build_plan(batch_id=plan.batch_id, operator_id=plan.operator_id, split=plan.split, output=plan.output,
        model=plan.model, price_version=plan.price_version, input_price=plan.input_price, output_price=plan.output_price,
        max_cost_usd=f"{plan.max_cost_microusd // 1_000_000}.{plan.max_cost_microusd % 1_000_000:06d}",
        output_limit=plan.output_limit, packet_keys=[s.key for s in plan.samples], ack_test_exposure=True)


def read_plan(path):
    path = Path(path)
    return Plan.model_validate(unique_json(fixture_bytes(path.parent, path.name, limit=1_000_000)))


def bound_request(plan, sample_key, revision):
    """Return immutable request bytes only when they match the reviewed sample."""
    sample = next((s for s in plan.samples if s.key == sample_key), None)
    if sample is None or sample.rejection is not None:
        raise ValueError("Sample is not approved for dispatch")
    revision = ExtractionRevision.model_validate(revision.model_dump(mode="json"))
    request, bound = prepare_request(revision, plan.model, plan.output_limit)
    if bound != sample.input_bound or digest(request) != sample.request_sha256:
        raise ValueError("Request differs from reviewed inputs")
    return canonical(request)


def validate_approval_binding(plan, *, approved_sha256, approved_max_cost_usd, operator_id, settings,
                              ack_test_exposure=False):
    """Check explicit approval parameters; does not assert a human has approved.

    The real runner remains closed. Callers cannot infer provider permission
    from this function, a plan file, or a CLI preview's successful exit.
    """
    plan = Plan.model_validate_json(canonical(plan.model_dump(mode="json")))
    if plan.split == "test" and not ack_test_exposure:
        raise ValueError("Frozen test exposure acknowledgement required")
    if (not isinstance(approved_sha256, str) or not re.fullmatch(r"[0-9a-f]{64}", approved_sha256)
        or not hmac.compare_digest(plan.sha256, approved_sha256)
        or cap_microusd(approved_max_cost_usd) != plan.max_cost_microusd or operator_id != plan.operator_id):
        raise ValueError("Approval does not match this plan")
    settings.require_real_ai_configuration()
    if operator_id not in settings.real_ai_user_ids:
        raise ValueError("Operator is not invited")
    actual = (settings.model_id, settings.price_version, settings.input_microusd_per_million,
              settings.output_microusd_per_million)
    if actual != (plan.model, plan.price_version, plan.input_price, plan.output_price):
        raise ValueError("Model or prices changed")
    if plan.upper_microusd > plan.max_cost_microusd:
        raise ValueError("Selected samples exceed approved cap; prepare a smaller selection")
    current = rebuild(plan)
    if current.sha256 != plan.sha256:
        raise ValueError("Inputs or implementation changed; prepare a new plan")


def require_operator(connection, plan, settings):
    """Future dispatch transaction: lock active invited user before batch/usage locks."""
    if not connection.in_transaction(): raise ValueError("Caller-owned transaction required")
    require_current_schema(connection)
    settings.require_real_ai_configuration()
    if plan.operator_id not in settings.real_ai_user_ids:
        raise ValueError("Operator is not invited")
    rates.lock_user(connection, plan.operator_id)


def summary(plan):
    return dict(plan_sha256=plan.sha256, batch_id=str(plan.batch_id), operator_id=str(plan.operator_id),
        samples=len(plan.samples), callable_samples=sum(s.rejection is None for s in plan.samples),
        rejected_samples=[dict(key=s.key, reason=s.rejection) for s in plan.samples if s.rejection],
        model=plan.model, price_version=plan.price_version, input_price=plan.input_price, output_price=plan.output_price,
        upper_microusd=plan.upper_microusd, max_cost_microusd=plan.max_cost_microusd, output=plan.output,
        within_cap=plan.upper_microusd <= plan.max_cost_microusd, execution="disabled", approval="not_recorded",
        annotation_status=plan.annotation_status)


def main():
    parser = argparse.ArgumentParser(description="Prepare a real-evaluation review plan. No DB writes or model calls.")
    parser.add_argument("--plan-file", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True, help="Future report directory; must not exist")
    parser.add_argument("--operator-id", type=UUID, required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--price-version", required=True)
    parser.add_argument("--input-price", type=int, required=True, help="micro-USD per million input tokens")
    parser.add_argument("--output-price", type=int, required=True, help="micro-USD per million output tokens")
    parser.add_argument("--max-cost-usd", required=True)
    parser.add_argument("--split", choices=["dev", "test"], default="dev")
    parser.add_argument("--packet", action="append", dest="packet_keys")
    parser.add_argument("--ack-test-exposure", action="store_true")
    args = parser.parse_args()
    try:
        plan = build_plan(batch_id=uuid4(), operator_id=args.operator_id, split=args.split, output=args.output,
            model=args.model, price_version=args.price_version, input_price=args.input_price, output_price=args.output_price,
            max_cost_usd=args.max_cost_usd, packet_keys=args.packet_keys, ack_test_exposure=args.ack_test_exposure)
        # Keep plan metadata private and never overwrite earlier review evidence.
        with os.fdopen(os.open(args.plan_file, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600), "wb") as file:
            file.write(canonical(plan.model_dump(mode="json")) + b"\n")
        print(json.dumps(summary(plan), sort_keys=True))
    except (ValueError, OSError, RuntimeError, ApiError):
        parser.error("Plan preparation failed; check inputs, corpus integrity and new output paths. No request sent.")
