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
    SOURCE_CHANGED = "SOURCE_CHANGED"
    CHECKLIST_UNSUPPORTED = "CHECKLIST_UNSUPPORTED"
    PARSE_COVERAGE_INCOMPLETE = "PARSE_COVERAGE_INCOMPLETE"
    MODEL_INPUT_LIMIT = "MODEL_INPUT_LIMIT"
    MEMBERSHIP_REQUIRED = "MEMBERSHIP_REQUIRED"
    QUOTA_EXHAUSTED = "QUOTA_EXHAUSTED"
    BUDGET_EXHAUSTED = "BUDGET_EXHAUSTED"
    RUN_ACTIVE = "RUN_ACTIVE"
    RATE_LIMITED = "RATE_LIMITED"
    USAGE_CONFLICT = "USAGE_CONFLICT"
    AUTH_REQUIRED = "AUTH_REQUIRED"
    FORBIDDEN = "FORBIDDEN"
    NOT_FOUND = "NOT_FOUND"
    METHOD_NOT_ALLOWED = "METHOD_NOT_ALLOWED"
    SCHEMA_INVALID = "SCHEMA_INVALID"
    REAL_AI_NOT_ALLOWED = "REAL_AI_NOT_ALLOWED"
    SERVICE_NOT_READY = "SERVICE_NOT_READY"
    INTERNAL_ERROR = "INTERNAL_ERROR"
    OAUTH_FAILED = "OAUTH_FAILED"
    FILE_UNSUPPORTED = "FILE_UNSUPPORTED"
    FILE_TOO_LARGE = "FILE_TOO_LARGE"
    STORAGE_LIMIT = "STORAGE_LIMIT"
    DOCUMENT_LIMIT = "DOCUMENT_LIMIT"
    STORAGE_UNAVAILABLE = "STORAGE_UNAVAILABLE"
    IDEMPOTENCY_CONFLICT = "IDEMPOTENCY_CONFLICT"
    PACKET_LIMIT = "PACKET_LIMIT"
    PACKET_INPUT_LIMIT = "PACKET_INPUT_LIMIT"
    REVISION_CONFLICT = "REVISION_CONFLICT"
    DRAFT_CONFLICT = "DRAFT_CONFLICT"


class ErrorDetail(Contract):
    code: ErrorCode
    message: str
    retryable: bool = False
    current_revision: int | None = None


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


class SessionUser(Contract):
    id: UUID
    display_name: str


class SessionResponse(Contract):
    user: SessionUser | None = None
    csrf_token: str | None = None
    expires_at: UTCDateTime | None = None
    login_available: bool = False


class TextDocumentInput(Contract):
    text: str = Field(min_length=1, max_length=10_000)
    filename: str = Field(default="pasted-text.txt", min_length=1, max_length=255)


class DocumentResponse(Contract):
    id: UUID
    packet_id: UUID
    kind: Literal["pdf", "text"]
    filename: str
    byte_size: int = Field(ge=0)
    sha256: Sha256
    parse_status: Literal["uploading", "parsing", "ready", "rejected", "failed"]
    parser_version: str | None
    page_count: int | None = Field(default=None, ge=1)
    parse_error_code: str | None = None
    parse_error_page: int | None = Field(default=None, ge=1)
    created_at: UTCDateTime


class DocumentPageResponse(Contract):
    document_id: UUID
    page_number: int = Field(ge=1)
    normalized_text: str
    text_hash: Sha256
    parse_quality: Literal["ready", "empty", "unreadable", "failed"]
    parser_version: str


class CreatePacketInput(Contract):
    title: str = Field(min_length=1, max_length=200)
    synthetic_data_ack: Literal[True]


class UpdatePacketInput(Contract):
    title: str = Field(min_length=1, max_length=200)


class PacketResponse(Contract):
    id: UUID
    title: str
    state: Literal["empty", "collecting", "ready"]
    current_revision: int = Field(ge=0)
    review_version: int = Field(ge=0)
    synthetic_data_ack: bool
    created_at: UTCDateTime
    updated_at: UTCDateTime
    expires_at: UTCDateTime


class PacketListResponse(Contract):
    items: list[PacketResponse]
    next_cursor: str | None


class PacketDraftResponse(Contract):
    packet_id: UUID
    selected_document_ids: list[UUID]
    last_location: Literal["documents", "review", "handoff"]
    base_revision: int = Field(ge=0)
    draft_version: int = Field(ge=0)
    updated_at: UTCDateTime


class SavePacketDraftInput(Contract):
    expected_draft_version: int = Field(ge=0)
    base_revision: int = Field(ge=0)
    selected_document_ids: list[UUID] = Field(max_length=5)
    last_location: Literal["documents", "review", "handoff"]


class PacketDetailResponse(PacketResponse):
    current_document_ids: list[UUID]
    documents: list[DocumentResponse]
    draft: PacketDraftResponse


class SaveRevisionInput(Contract):
    expected_revision: int = Field(ge=0)
    document_ids: list[UUID] = Field(max_length=5)


class RevisionDocumentResponse(Contract):
    id: UUID
    kind: Literal["pdf", "text"]
    filename: str
    sha256: Sha256
    parser_version: str
    page_count: int | None
    byte_size: int


class RevisionResponse(Contract):
    id: UUID
    packet_id: UUID
    revision_number: int = Field(ge=1)
    manifest_hash: Sha256
    documents: list[RevisionDocumentResponse]
    is_current: bool
    created_at: UTCDateTime


class PacketDeleteResponse(Contract):
    id: UUID
    status: Literal["pending_cleanup"] = "pending_cleanup"


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


class MembershipResponse(Contract):
    environment: Literal["test"] = "test"
    valid_until: UTCDateTime | None = None
    remaining: int = Field(ge=0)
    reserved: int = Field(ge=0)
    real_ai_allowed: bool


class CreateRunInput(Contract):
    revision_id: UUID
    checklist_version: str = Field(min_length=1, max_length=100)


class RunResponse(Contract):
    id: UUID
    packet_id: UUID
    revision_id: UUID
    state: RunState
    mode: Literal["fake", "real", "replay", "precomputed"]
    stale: bool
    phase: Literal["pending", "reserved", "dispatched", "complete", "failed", "unknown", "cancelled"]
    checklist_version: str
    prompt_version: str
    schema_version: str
    model_requested: str | None
    model_reported: str | None
    created_at: UTCDateTime
    finished_at: UTCDateTime | None
    lease_expires_at: UTCDateTime | None
    error_code: str | None
    usage: dict[str, int] | None
    result: ReviewResult | None = None
