"""Canonical transport contracts. Future modules extend these rather than hand-copy TS."""

from datetime import datetime, timezone
from enum import StrEnum
from typing import Annotated, Literal
from uuid import UUID

from pydantic import AfterValidator, AwareDatetime, BaseModel, ConfigDict, Field, model_validator


def normalize_utc(value: datetime) -> datetime:
    return value.astimezone(timezone.utc)


UTCDateTime = Annotated[AwareDatetime, AfterValidator(normalize_utc)]
Sha256 = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)


class ErrorCode(StrEnum):
    AUTH_REQUIRED = "AUTH_REQUIRED"
    FORBIDDEN = "FORBIDDEN"
    NOT_FOUND = "NOT_FOUND"
    METHOD_NOT_ALLOWED = "METHOD_NOT_ALLOWED"
    SCHEMA_INVALID = "SCHEMA_INVALID"
    REAL_AI_NOT_ALLOWED = "REAL_AI_NOT_ALLOWED"
    SERVICE_NOT_READY = "SERVICE_NOT_READY"
    INTERNAL_ERROR = "INTERNAL_ERROR"


class ErrorDetail(Contract):
    code: ErrorCode
    message: str
    retryable: bool = False


class ErrorEnvelope(Contract):
    error: ErrorDetail
    request_id: UUID


class InputLimits(Contract):
    max_documents: int = Field(5, gt=0)
    max_pdf_bytes: int = Field(2 * 1024 * 1024, gt=0)
    max_packet_pdf_bytes: int = Field(10 * 1024 * 1024, gt=0)
    max_pages: int = Field(25, gt=0)
    max_text_codepoints: int = Field(10_000, gt=0)
    max_packet_codepoints: int = Field(30_000, gt=0)
    max_input_tokens: int = Field(16_000, gt=0)
    max_output_tokens: int = Field(6_000, gt=0)


class Capabilities(Contract):
    contract_version: str
    stage: Literal["foundation"] = "foundation"
    mode: Literal["bundled_demo", "sandbox", "invited_real"]
    synthetic_data_only: Literal[True] = True
    demo_mode_available: Literal[True] = True
    # Configuration alone cannot enable features whose secure workflows are not implemented.
    workspace_available: Literal[False] = False
    demo_cases_available: Literal[False] = False
    sandbox_execution_available: Literal[False] = False
    real_ai_execution_available: Literal[False] = False
    payments_available: Literal[False] = False
    payment_environment: Literal["test"] = "test"
    limits: InputLimits = Field(default_factory=InputLimits)


class ReadinessResponse(Contract):
    status: Literal["ready", "not_ready"]
    schema_version: str | None
    checklist_version: str | None
    checks: dict[str, Literal["ready", "not_checked", "not_implemented", "unavailable"]]


class Evidence(Contract):
    id: UUID
    document_id: UUID
    page_number: int = Field(ge=1)
    start_cp: int = Field(ge=0)
    end_cp: int = Field(gt=0)
    quote: str = Field(min_length=1)
    text_hash: Sha256

    @model_validator(mode="after")
    def span_matches_quote_length(self):
        # MT-06 validates the slice/hash against the actual immutable source page.
        if self.end_cp - self.start_cp != len(self.quote):
            raise ValueError("Evidence length must match its Unicode code point span")
        return self


class FieldKey(StrEnum):
    PATIENT_NAME = "patient.name"
    PATIENT_DOB = "patient.dob"
    REFERRER_NAME = "referrer.name"
    REFERRER_CONTACT = "referrer.contact"
    RECIPIENT = "recipient"
    REFERRAL_REASON = "referral.reason"
    MEDICATIONS = "medications"
    ALLERGIES = "allergies"
    ATTACHMENT_REFERENCE = "attachment_reference"
    REPORT_DESCRIPTION = "report.description"


class Fact(Contract):
    id: UUID
    field_key: FieldKey
    value_raw: str = Field(min_length=1)
    value_normalized: str | None = None
    assertion_status: Literal["stated", "explicitly_none", "unknown"]
    temporal_context: str | None = None
    evidence_ids: list[UUID] = Field(min_length=1)


class Finding(Contract):
    id: UUID
    rule_id: str = Field(pattern=r"^C0[1-8]$")
    checklist_version: str
    kind: Literal["missing", "unknown", "identity_mismatch", "statement_difference", "attachment_unmatched", "parse_quality"]
    field_keys: list[FieldKey] = Field(min_length=1)
    fact_ids: list[UUID] = Field(default_factory=list)
    evidence_ids: list[UUID] = Field(default_factory=list)
    checked_document_ids: list[UUID] = Field(min_length=1)
    message: str = Field(min_length=1)


class RunState(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    OUTCOME_UNKNOWN = "outcome_unknown"
    CANCELLED = "cancelled"


class ReviewResult(Contract):
    """A completed result, not a pending job; no invented execution endpoints in MT-01."""

    run_id: UUID
    revision_id: UUID
    mode: Literal["precomputed", "fake", "replay", "real"]
    created_at: UTCDateTime
    checklist_version: str
    prompt_version: str
    schema_version: str
    facts: list[Fact]
    evidence: list[Evidence]
    findings: list[Finding]

    @model_validator(mode="after")
    def valid_references(self):
        facts = {item.id for item in self.facts}
        evidence = {item.id for item in self.evidence}
        if len(facts) != len(self.facts) or len(evidence) != len(self.evidence) or len({item.id for item in self.findings}) != len(self.findings):
            raise ValueError("Duplicate result IDs")
        if any(not set(fact.evidence_ids).issubset(evidence) for fact in self.facts):
            raise ValueError("Fact references missing evidence")
        for finding in self.findings:
            if not set(finding.evidence_ids).issubset(evidence) or not set(finding.fact_ids).issubset(facts):
                raise ValueError("Finding references missing facts or evidence")
            if finding.checklist_version != self.checklist_version:
                raise ValueError("Finding checklist does not match result")
        return self


DOMAIN_CONTRACTS = (Evidence, Fact, Finding, ReviewResult, RunState)
