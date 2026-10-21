"""Checklist input is the complete immutable revision manifest, not selected excerpts."""
from typing import Literal
from uuid import UUID

from pydantic import Field

from ..schemas import Contract, DocumentPageResponse, FieldKey, Finding

CHECKLIST_VERSION = "outpatient-referral-demo@1"


class ManifestDocument(Contract):
    id: UUID
    title: str = Field(min_length=1)
    kind: Literal["pdf", "text"]
    parse_status: Literal["ready", "uploading", "parsing", "rejected", "failed"]
    page_count: int = Field(ge=1)
    pages: list[DocumentPageResponse]


class ChecklistManifest(Contract):
    revision_id: UUID
    documents: list[ManifestDocument] = Field(min_length=1, max_length=5)


class DifferenceCandidate(Contract):
    """Untrusted hint; never supplies a message, severity or medical conclusion."""
    field_key: FieldKey
    fact_ids: list[UUID] = Field(min_length=2, max_length=2)


class ChecklistEvaluation(Contract):
    checklist_version: str = CHECKLIST_VERSION
    revision_id: UUID
    checked_document_ids: list[UUID]
    checked_pages: int
    coverage: str
    assessments: dict[str, Literal["satisfied", "missing", "needs_clarification", "needs_review", "not_applicable"]]
    findings: list[Finding]
    fingerprints: dict[UUID, str]
