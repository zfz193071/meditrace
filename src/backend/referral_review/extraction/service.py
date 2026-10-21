"""Pure extraction orchestration. Caller must authorize revision and reserve usage first.

The runs module supplies membership, budget, dispatch CAS and recovery controls.
"""
import json
import re
from uuid import uuid4

from pydantic import ValidationError

from ..documents.text_rules import EvidenceInvalid, locate_quote
from ..schemas import Evidence, Fact
from .adapters import ExtractionError, ModelAdapter
from .contracts import Extraction, ExtractionRevision, ModelOutput
from .prompt import build_request

# Byte-level tokenization cannot produce more text tokens than UTF-8 bytes.
# Count the ENTIRE JSON request plus 1024 tokens for message/control framing.
# Deliberately rejects some otherwise valid long packets rather than truncating.
MAX_INPUT_TOKENS = 16_000
FRAME_TOKEN_ALLOWANCE = 1024
DATE = re.compile(r"\b(?:\d{4}-\d{2}-\d{2}|\d{1,2}/\d{1,2}/\d{2,4}|(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2}(?:,?\s+\d{4})?)\b", re.I)
UNKNOWN = re.compile(r"\b(?:unknown|unclear|not known|not sure|uncertain)\b", re.I)
NONE = re.compile(r"\b(?:none|no known|no current|not taking|no medications|no allergies)\b", re.I)


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON key")
        result[key] = value
    return result


def validate_output(content, revision):
    """Minimum lexical support, not proof of semantic accuracy (MT-20 measures that)."""
    parsed = ModelOutput.model_validate(json.loads(content, object_pairs_hook=_unique_object))
    pages = {(p.document_id, p.page_number): p for p in revision.pages}
    facts, evidence = [], []
    for item in parsed.facts:
        if item.value_normalized not in (None, item.value_raw):
            raise ValueError("Unsupported normalization")
        raw = item.value_raw
        if not raw.strip():
            raise ValueError("Empty fact")
        if item.assertion_status == "unknown" and not UNKNOWN.search(raw):
            raise ValueError("Unsupported unknown assertion")
        if item.assertion_status == "explicitly_none" and not NONE.search(raw):
            raise ValueError("Unsupported absence assertion")
        if UNKNOWN.search(raw) and item.assertion_status != "unknown":
            raise ValueError("Lost uncertainty")
        if NONE.search(raw) and item.assertion_status != "explicitly_none":
            raise ValueError("Lost negation")
        if item.field_key == "patient.dob" and re.fullmatch(r"\d{4}-\d{2}-\d{2}", raw):
            from datetime import date
            date.fromisoformat(raw)
        ids = []
        for source in item.sources:
            page = pages.get((source.document_id, source.page_number))
            if page is None or page.parse_quality != "ready":
                raise EvidenceInvalid("Source not in revision")
            anchor = locate_quote(page.normalized_text, source.quote, before=source.before, after=source.after)
            if raw not in anchor.quote or (item.temporal_context is not None and (
                not item.temporal_context.strip() or item.temporal_context not in anchor.quote)):
                raise ValueError("Fact not supported by quote")
            if item.field_key in ("medications", "report.description"):
                # Retain the full original line around the excerpt, including dose/date/negation.
                start = page.normalized_text.rfind("\n", 0, anchor.start_cp) + 1
                end = page.normalized_text.find("\n", anchor.end_cp)
                line = page.normalized_text[start:end if end >= 0 else None]
                if raw != line or any(d not in (item.temporal_context or "") for d in DATE.findall(line)):
                    raise ValueError("Incomplete dated or measured statement")
            eid = uuid4()
            evidence.append(Evidence(id=eid, document_id=source.document_id,
                page_number=source.page_number, start_cp=anchor.start_cp, end_cp=anchor.end_cp,
                quote=anchor.quote, text_hash=anchor.text_hash))
            ids.append(eid)
        facts.append(Fact(id=uuid4(), field_key=item.field_key, value_raw=raw,
            value_normalized=item.value_normalized, assertion_status=item.assertion_status,
            temporal_context=item.temporal_context, evidence_ids=ids))
    return facts, evidence


async def extract(revision: ExtractionRevision, model_config, adapter: ModelAdapter,
                  *, max_output_tokens=6000) -> Extraction:
    # Revalidate even model_construct / mutated input before any network dispatch.
    try:
        revision = ExtractionRevision.model_validate(revision.model_dump(mode="json"))
    except (ValueError, AttributeError):
        raise ExtractionError("EXTRACTION_INPUT_INVALID") from None
    if adapter.mode == "real":
        model_config.require_real_ai_configuration()
    model_id = model_config.model_id if adapter.mode == "real" else "fake-extraction-v1"
    request, _ = prepare_request(revision, model_id, max_output_tokens)
    reply = await adapter.complete(request)
    try:
        if len(reply.content.encode("utf-8")) > 128_000:
            raise ValueError("Output limit")
        facts, evidence = validate_output(reply.content, revision)
    except (ValidationError, ValueError, TypeError, RecursionError):
        raise ExtractionError("MODEL_INVALID_OUTPUT", reply=reply) from None
    return Extraction(revision_id=revision.revision_id, mode=adapter.mode,
        model_requested=model_id, model_reported=reply.model_reported,
        provider_request_id=reply.request_id, usage=reply.usage, facts=facts, evidence=evidence)


def prepare_request(revision: ExtractionRevision, model_id: str, max_output_tokens=6000):
    """Shared complete-request upper bound for preflight reservation and actual extraction."""
    if type(max_output_tokens) is not int or not 1 <= max_output_tokens <= 6000:
        raise ExtractionError("MODEL_INPUT_LIMIT")
    request = build_request(revision, model_id, max_output_tokens)
    bound = len(json.dumps(request, ensure_ascii=False).encode("utf-8")) + FRAME_TOKEN_ALLOWANCE
    if bound > MAX_INPUT_TOKENS:
        raise ExtractionError("MODEL_INPUT_LIMIT")
    return request, bound
