"""Bounded reviewer inputs; provenance is assigned only by the server."""
from typing import Annotated, Literal
from uuid import UUID
from pydantic import Field, model_validator
from ..schemas import Contract, UTCDateTime, Sha256

ReviewMode = Literal["assisted", "manual"]
Text = Annotated[str, Field(min_length=1, max_length=4000)]
FieldName = Annotated[str, Field(pattern=r"^[a-z][a-z0-9_.]{0,79}$")]


class ResolutionInput(Contract):
    expected_review_version: int = Field(ge=0)
    action: Literal["resolve", "dismiss", "defer", "reopen"]
    reason: str = Field(default="", max_length=4000)
    corrected_value: Text | None = None
    linked_evidence_ids: list[UUID] = Field(default_factory=list, max_length=100)

    @model_validator(mode="after")
    def validate_reason(self):
        if self.action in {"dismiss", "defer"} and not self.reason.strip():
            raise ValueError("Reason required")
        if self.corrected_value is not None and not self.corrected_value.strip():
            raise ValueError("Correction cannot be blank")
        return self


class ReviewContext(Contract):
    mode: ReviewMode
    run_id: UUID | None = None
    expected_review_version: int = Field(ge=0)

    @model_validator(mode="after")
    def validate_context(self):
        if (self.mode == "manual") != (self.run_id is None):
            raise ValueError("Manual mode has no run; assisted mode requires a run")
        return self


class HandoffDraftInput(ReviewContext):
    expected_revision: int = Field(ge=1)
    fields: dict[FieldName, Text] = Field(max_length=40)

    @model_validator(mode="after")
    def validate_fields(self):
        if any(not value.strip() for value in self.fields.values()):
            raise ValueError("Field cannot be blank")
        return self


class ConfirmInput(ReviewContext):
    revision_id: UUID


class ReviewEvent(Contract):
    id: UUID
    packet_id: UUID
    revision_id: UUID
    run_id: UUID | None
    actor_id: UUID
    review_version: int
    kind: Literal["resolution", "draft", "confirmation"]
    created_at: UTCDateTime
    content: dict


class ReviewHistory(Contract):
    items: list[ReviewEvent]
    next_cursor: str | None = None


class HandoffDraftResponse(Contract):
    draft: ReviewEvent | None
    stale: bool


class SnapshotResponse(Contract):
    id: UUID
    packet_id: UUID
    revision_id: UUID
    run_id: UUID | None
    review_version: int
    confirmed_by: UUID
    confirmed_at: UTCDateTime
    payload: dict
    payload_hash: Sha256
    has_unresolved: bool
    historical: bool
