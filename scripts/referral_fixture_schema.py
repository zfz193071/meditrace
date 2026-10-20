"""Strict offline fixture schemas; these are not new production API endpoints."""

from typing import Literal
from uuid import UUID

from pydantic import Field, model_validator

from referral_review.schemas import Contract, FieldKey, ReviewResult, Sha256, UTCDateTime

VERSION = "outpatient-referral-demo@1"
RULE_IDS = tuple(f"C0{i}" for i in range(1, 9))
CheckState = Literal["satisfied", "missing", "needs_clarification", "needs_review", "not_applicable", "blocked"]


class Rule(Contract):
    id: str = Field(pattern=r"^C0[1-8]$")
    fields: list[FieldKey] = Field(min_length=1)
    requirement: str
    presence: Literal["all", "any", "explicit_attachment_only"]
    unknown_behavior: Literal["preserve", "clarify"] = "preserve"
    safeguards: list[str] = Field(min_length=1)


class Checklist(Contract):
    version: Literal["outpatient-referral-demo@1"]
    title: str
    demonstration_only: Literal[True]
    clinical_standard: Literal[False]
    rules: list[Rule]

    @model_validator(mode="after")
    def ordered_rules(self):
        if tuple(r.id for r in self.rules) != RULE_IDS:
            raise ValueError("Exactly C01 through C08, in order, are required")
        return self


class Page(Contract):
    number: int = Field(ge=1)
    text_path: str
    text_hash: Sha256
    quality: Literal["text", "unreadable"]


class Document(Contract):
    id: UUID
    title: str
    kind: Literal["pdf", "text"]
    source_path: str
    sha256: Sha256
    byte_size: int = Field(gt=0)
    pages: list[Page]
    fixture_variant: str
    expected_gate: str | None = None


class Gold(Contract):
    automated_review_allowed: bool
    expected_rejection: str | None
    result: ReviewResult | None
    checklist: dict[str, CheckState]
    rationale_by_id: dict[str, str]
    operator_review: Literal["pending"] = "pending"

    @model_validator(mode="after")
    def result_gate(self):
        if set(self.checklist) != set(RULE_IDS):
            raise ValueError("Every checklist item needs an explicit label")
        if self.automated_review_allowed:
            if self.result is None or self.expected_rejection is not None:
                raise ValueError("Readable gold must contain a result and no rejection")
            if self.result.mode != "precomputed" or self.result.checklist_version != VERSION:
                raise ValueError("Gold is precomputed for the fixed checklist")
        elif self.result is not None or not self.expected_rejection:
            raise ValueError("Blocked input must not masquerade as a successful result")
        elif set(self.checklist.values()) != {"blocked"}:
            raise ValueError("Unreadable input cannot support missing/negative labels")
        return self


class Packet(Contract):
    schema_version: Literal["fixture-v1"]
    id: UUID
    key: str = Field(pattern=r"^(dev|test)-[0-9]{2}$")
    split: Literal["dev", "test"]
    title: str
    synthetic: Literal[True]
    tags: list[str]
    public_demo: bool
    documents: list[Document] = Field(min_length=1, max_length=5)
    gold: Gold


class Resolution(Contract):
    finding_id: UUID
    status: Literal["open", "resolved", "dismissed", "unresolved"]
    reason: str | None = None

    @model_validator(mode="after")
    def reason_required(self):
        if self.status in {"dismissed", "unresolved"} and not (self.reason or "").strip():
            raise ValueError("Dismissed/unresolved decisions require a reason")
        return self


class DemoReview(Contract):
    schema_version: Literal["demo-review-fixture-v1"]
    illustrative_not_actual_review: Literal[True]
    packet_id: UUID
    run_id: UUID
    revision_id: UUID
    review_version: int = Field(ge=0)
    status: Literal["draft", "confirmed"]
    resolutions: list[Resolution]
    confirmed_at: UTCDateTime | None
    has_unresolved: bool
    identity_unresolved: bool
    heading: str

    @model_validator(mode="after")
    def coherent_review(self):
        if len({r.finding_id for r in self.resolutions}) != len(self.resolutions):
            raise ValueError("Duplicate finding resolutions")
        if self.status == "confirmed":
            if not self.confirmed_at or any(r.status == "open" for r in self.resolutions):
                raise ValueError("Confirmed review needs a timestamp and no open items")
        elif self.confirmed_at:
            raise ValueError("Draft is not confirmed")
        if self.has_unresolved != any(r.status == "unresolved" for r in self.resolutions):
            raise ValueError("Unresolved flag does not match resolutions")
        if self.identity_unresolved and not self.has_unresolved:
            raise ValueError("Identity flag requires an unresolved item")
        return self


class Entry(Contract):
    key: str
    split: Literal["dev", "test"]
    packet_path: str
    sha256: Sha256
    public_demo: bool


class Manifest(Contract):
    schema_version: Literal["fixture-manifest-v1"]
    corpus_version: Literal["synthetic-referral@1"]
    checklist_version: Literal["outpatient-referral-demo@1"]
    checklist_sha256: Sha256
    annotation_status: Literal["provisional_operator_review_pending"]
    test_split_policy: Literal["held_out_from_prompts_not_secret"]
    parser_version: str
    generator_version: str
    entries: list[Entry]
    files: dict[str, Sha256]

    @model_validator(mode="after")
    def split_counts(self):
        if len({e.key for e in self.entries}) != len(self.entries):
            raise ValueError("Duplicate packet IDs")
        if sum(e.split == "dev" for e in self.entries) != 10 or sum(e.split == "test" for e in self.entries) != 20:
            raise ValueError("Expected exactly 10 dev and 20 test packets")
        public = [e for e in self.entries if e.public_demo]
        if len(public) != 3 or any(e.split != "dev" for e in public):
            raise ValueError("Exactly three development cases may be public")
        return self
