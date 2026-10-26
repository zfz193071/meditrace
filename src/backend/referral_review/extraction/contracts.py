"""Versioned extraction boundary; source pages come from an authorized revision loader."""
from typing import Literal
from uuid import UUID

from pydantic import ConfigDict, Field, model_validator

from ..schemas import Contract, DocumentPageResponse, Evidence, Fact, FieldKey

PROMPT_VERSION = "referral-extract-v1"
SCHEMA_VERSION = "extraction-v1"


class ExtractionRevision(Contract):
    revision_id: UUID
    pages: list[DocumentPageResponse] = Field(min_length=1, max_length=25)

    @model_validator(mode="after")
    def valid_pages(self):
        from ..documents.text_rules import normalize_text, text_hash
        keys = [(p.document_id, p.page_number) for p in self.pages]
        if len(set(keys)) != len(keys) or len({k[0] for k in keys}) > 5:
            raise ValueError("Invalid revision members")
        if sum(len(p.normalized_text) for p in self.pages) > 30_000:
            raise ValueError("Revision text limit exceeded")
        for p in self.pages:
            if (p.parse_quality not in ("ready", "empty") or p.parser_version not in (
                    "text-v1", "pypdf-6.21.1/text-v1", "pypdf-6.21.2/text-v1")
                or normalize_text(p.normalized_text) != p.normalized_text
                or text_hash(p.normalized_text) != p.text_hash):
                raise ValueError("Invalid source page")
        return self


class ModelQuote(Contract):
    document_id: UUID
    page_number: int = Field(ge=1, strict=True)
    quote: str = Field(min_length=1, max_length=30_000)
    before: str = Field(default="", max_length=1000)
    after: str = Field(default="", max_length=1000)


class ModelFact(Contract):
    field_key: FieldKey
    value_raw: str = Field(min_length=1, max_length=4000)
    value_normalized: str | None
    assertion_status: Literal["stated", "explicitly_none", "unknown"]
    temporal_context: str | None
    sources: list[ModelQuote] = Field(min_length=1, max_length=10)


class ModelOutput(Contract):
    facts: list[ModelFact] = Field(max_length=200)


class TokenUsage(Contract):
    model_config = ConfigDict(extra="ignore", strict=True, hide_input_in_errors=True)
    prompt_tokens: int = Field(ge=0)
    completion_tokens: int = Field(ge=0)
    total_tokens: int = Field(ge=0)

    @model_validator(mode="after")
    def sum_matches(self):
        if self.total_tokens != self.prompt_tokens + self.completion_tokens:
            raise ValueError("Invalid usage")
        return self


class Extraction(Contract):
    revision_id: UUID
    mode: Literal["fake", "real"]
    prompt_version: str = PROMPT_VERSION
    schema_version: str = SCHEMA_VERSION
    model_requested: str
    model_reported: str | None
    provider_request_id: str | None
    usage: TokenUsage | None
    facts: list[Fact]
    evidence: list[Evidence]
