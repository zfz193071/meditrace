"""Metadata-only operator response. Intentionally excludes source/provider payloads."""
from datetime import datetime
from typing import Literal
from uuid import UUID

from ..schemas import Contract


class RunMetadata(Contract):
    run_id: UUID
    state: Literal["pending", "running", "succeeded", "failed", "outcome_unknown", "cancelled"]
    mode: Literal["precomputed", "fake", "replay", "real"]
    error_code: str | None
    model_requested_sha256: str | None
    model_reported_sha256: str | None
    prompt_tokens: int | None
    completion_tokens: int | None
    total_tokens: int | None
    reservation_id: UUID | None
    usage_state: Literal["reserved", "settled", "released", "retained_unknown", "estimated_spent"] | None
    estimated_microusd: int | None
    actual_microusd: int | None
    booked_microusd: int | None
    adjustment_count: int
    price_version_sha256: str | None


class Budget(Contract):
    bucket_key: str
    limit_microusd: int
    configured_limit_microusd: int
    reserved_microusd: int
    spent_microusd: int


class Audit(Contract):
    request_id: UUID
    run_id: UUID | None
    action: str
    created_at: datetime


class CleanupJob(Contract):
    id: UUID
    kind: Literal["object", "packet", "account", "orphan", "audit", "billing"]
    state: Literal["pending", "running", "succeeded", "failed"]
    attempt_count: int
    next_attempt_at: datetime


class OperationsStatus(Contract):
    budgets: list[Budget]
    alerts: dict[str, int]
    runs: list[RunMetadata]
    audit: list[Audit]
    cleanup_jobs: list[CleanupJob]
    limit: int
    audit_limit: int
