"""One serializable handoff model shared by screen, clipboard, text and PDF."""
from typing import Literal
from uuid import UUID
from pydantic import Field
from ..schemas import Contract, Sha256, UTCDateTime


class HandoffSection(Contract):
    heading: str
    paragraphs: list[str]


class HandoffView(Contract):
    schema_version: Literal["handoff-v1"] = "handoff-v1"
    snapshot_id: UUID
    packet_id: UUID
    revision_id: UUID
    review_version: int = Field(ge=0)
    confirmed_at: UTCDateTime
    payload_hash: Sha256
    historical: bool
    title: str
    status: str
    warnings: list[str]
    sections: list[HandoffSection]
