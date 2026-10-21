"""Deterministic intake rules. No I/O, model calls, medical judgment or fuzzy identity merge."""
from datetime import date
from hashlib import sha256
from itertools import combinations
import json
import re
from uuid import NAMESPACE_URL, uuid5

from ..documents.text_rules import Anchor, verify_anchor
from ..extraction.contracts import Extraction
from ..schemas import Finding
from .contracts import CHECKLIST_VERSION, ChecklistEvaluation, ChecklistManifest, DifferenceCandidate

RULE_FIELDS = {
    "C01": ("patient.name",), "C02": ("patient.dob",),
    "C03": ("referrer.name", "referrer.contact"), "C04": ("recipient",),
    "C05": ("referral.reason",), "C06": ("medications",), "C07": ("allergies",),
    "C08": ("attachment_reference",),
}


class ChecklistError(ValueError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def normalized(value):
    return " ".join(value.split()).casefold()


def complete_date(raw):
    # No locale guessing; slash dates remain recorded but incomparable.
    raw = raw.strip()
    try:
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", raw):
            return date.fromisoformat(raw).isoformat()
        months = {name.casefold(): n for n, name in enumerate((
            "January", "February", "March", "April", "May", "June", "July", "August",
            "September", "October", "November", "December"), 1)}
        month_first = re.fullmatch(r"([A-Za-z]+) (\d{1,2}), (\d{4})", raw)
        day_first = re.fullmatch(r"(\d{1,2}) ([A-Za-z]+) (\d{4})", raw)
        if month_first:
            month, day, year = month_first.groups()
        elif day_first:
            day, month, year = day_first.groups()
        else:
            return None
        if month.casefold() in months:
            return date(int(year), months[month.casefold()], int(day)).isoformat()
    except ValueError:
        pass
    return None


def directly_opposed(a, b):
    if a.field_key != b.field_key or a.field_key not in ("medications", "allergies"):
        return False
    # Unknown, absent time, ambiguous dates and different dates cannot establish a conflict.
    time = complete_date(a.temporal_context or "")
    if not time or time != complete_date(b.temporal_context or ""):
        return False
    if "unknown" in (a.assertion_status, b.assertion_status):
        return False
    for negative, positive in ((a, b), (b, a)):
        if positive.assertion_status != "stated":
            continue
        neg, pos = normalized(negative.value_raw), normalized(positive.value_raw)
        if negative.assertion_status == "explicitly_none":
            if negative.field_key == "allergies" and re.search(r"\bno known allergies\b", neg):
                return bool(re.search(r"\b(?:allergic to|allergy to)\s+\w", pos))
            if negative.field_key == "medications" and re.search(r"\bno current medications\b", neg):
                return bool(re.search(r"\b(?:currently )?taking\s+\w", pos))
        # A specific negated drug must match that drug, not a different treatment.
        match = re.search(r"\bnot taking (.+?)[.]?$", neg)
        taking = re.search(r"\b(?:currently )?taking (.+)$", pos)
        if match and taking and "not taking" not in pos:
            drug = match[1].rstrip(".")
            if taking[1] == drug or taking[1].startswith(drug + " "):
                # Require a dose or sentence boundary after the exact name, not an extended drug name.
                suffix = taking[1][len(drug):].strip()
                if not suffix or suffix == "." or re.match(r"^\d+(?:\.\d+)?\s", suffix):
                    return True
    return False


def _validate(extraction, manifest):
    if extraction.revision_id != manifest.revision_id:
        raise ChecklistError("CHECKLIST_INPUT_INVALID")
    documents = {d.id: d for d in manifest.documents}
    if len(documents) != len(manifest.documents):
        raise ChecklistError("CHECKLIST_INPUT_INVALID")
    pages = {}
    for doc in manifest.documents:
        if (doc.parse_status != "ready" or len(doc.pages) != doc.page_count
            or {p.page_number for p in doc.pages} != set(range(1, doc.page_count + 1))):
            raise ChecklistError("PARSE_COVERAGE_INCOMPLETE")
        for page in doc.pages:
            if page.document_id != doc.id:
                raise ChecklistError("CHECKLIST_INPUT_INVALID")
            if page.parse_quality not in ("ready", "empty"):
                raise ChecklistError("PARSE_COVERAGE_INCOMPLETE")
            pages[(doc.id, page.page_number)] = page
    from ..extraction.contracts import ExtractionRevision
    ExtractionRevision(revision_id=manifest.revision_id, pages=list(pages.values()))
    evidence = {e.id: e for e in extraction.evidence}
    facts = {f.id: f for f in extraction.facts}
    if len(evidence) != len(extraction.evidence) or len(facts) != len(extraction.facts):
        raise ChecklistError("CHECKLIST_INPUT_INVALID")
    for e in evidence.values():
        page = pages.get((e.document_id, e.page_number))
        if page is None or page.parse_quality != "ready":
            raise ChecklistError("CHECKLIST_INPUT_INVALID")
        verify_anchor(page.normalized_text, Anchor(e.start_cp, e.end_cp, e.quote, e.text_hash))
    for fact in facts.values():
        if not set(fact.evidence_ids).issubset(evidence):
            raise ChecklistError("CHECKLIST_INPUT_INVALID")
    return evidence, facts, len(pages)


def evaluate(extraction: Extraction, manifest: ChecklistManifest,
             checklist: str = CHECKLIST_VERSION, *, candidates: tuple[DifferenceCandidate, ...] = ()) -> ChecklistEvaluation:
    if checklist != CHECKLIST_VERSION:
        raise ChecklistError("CHECKLIST_UNSUPPORTED")
    try:
        extraction = Extraction.model_validate(extraction.model_dump(mode="json"))
        manifest = ChecklistManifest.model_validate(manifest.model_dump(mode="json"))
        evidence, facts, page_count = _validate(extraction, manifest)
        candidates = tuple(DifferenceCandidate.model_validate(c.model_dump(mode="json")) for c in candidates)
    except ChecklistError:
        raise
    except (ValueError, AttributeError, TypeError):
        raise ChecklistError("CHECKLIST_INPUT_INVALID") from None
    checked = sorted((d.id for d in manifest.documents), key=str)
    coverage = f"Checked all {len(checked)} supplied, successfully parsed documents ({page_count} pages) in this revision."
    findings, fingerprints = [], {}
    assessments = {}
    by_field = {field: sorted((f for f in facts.values() if f.field_key == field), key=lambda f: str(f.id))
                for fields in RULE_FIELDS.values() for field in fields}

    def add(rule, kind, fields, selected, message):
        fact_ids = sorted({f.id for f in selected}, key=str)
        evidence_ids = sorted({eid for f in selected for eid in f.evidence_ids}, key=str)
        payload = dict(revision=str(manifest.revision_id), checklist=checklist, rule=rule, kind=kind,
                       fields=sorted(fields), facts=list(map(str, fact_ids)), evidence=list(map(str, evidence_ids)),
                       checked=list(map(str, checked)))
        fingerprint = sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
        fid = uuid5(NAMESPACE_URL, "meditrace:checklist:" + fingerprint)
        if fid in fingerprints:
            return
        fingerprints[fid] = fingerprint
        findings.append(Finding(id=fid, rule_id=rule, checklist_version=checklist, kind=kind,
            field_keys=sorted(fields), fact_ids=fact_ids, evidence_ids=evidence_ids,
            checked_document_ids=checked, message=message + " " + coverage))

    for rule, fields in RULE_FIELDS.items():
        assessments[rule] = "satisfied"
        if rule == "C08":
            continue
        missing = [field for field in fields if not by_field[field]]
        if missing:
            assessments[rule] = "missing"
            add(rule, "missing", missing, [], "Not found in the supplied, successfully parsed material: " + ", ".join(missing) + ".")
        unknown = [f for field in fields for f in by_field[field] if f.assertion_status == "unknown"]
        if unknown:
            if not missing:
                assessments[rule] = "needs_clarification"
            add(rule, "unknown", {f.field_key for f in unknown}, unknown, "Recorded as unknown; clarification is needed.")

    for rule, field in (("C01", "patient.name"), ("C02", "patient.dob")):
        comparable = [(f, normalized(f.value_raw) if rule == "C01" else complete_date(f.value_raw))
                      for f in by_field[field] if f.assertion_status == "stated"]
        comparable = [(f, value) for f, value in comparable if value]
        if len({value for _, value in comparable}) > 1:
            assessments[rule] = "needs_review"
            add(rule, "identity_mismatch", [field], [f for f, _ in comparable],
                "Recorded identity values differ; verify both sources without selecting or merging an identity.")

    # Hints never add an unchecked pair; the engine already examines all eligible pairs.
    for candidate in candidates:
        pair = [facts.get(fid) for fid in candidate.fact_ids]
        if any(f is None or f.field_key != candidate.field_key for f in pair):
            raise ChecklistError("CHECKLIST_INPUT_INVALID")
    for rule, field in (("C06", "medications"), ("C07", "allergies")):
        for a, b in combinations(by_field[field], 2):
            if directly_opposed(a, b):
                assessments[rule] = "needs_review"
                add(rule, "statement_difference", [field], [a, b],
                    "Directly opposing statements share the same explicit date; verify both sources.")

    claims = [f for f in by_field["attachment_reference"] if f.assertion_status == "stated"]
    assessments["C08"] = "not_applicable" if not claims else "satisfied"
    for claim in claims:
        # Exact title only; short, partial, fuzzy or multiple matches remain unresolved.
        match = re.fullmatch(r"(.+?)\s+is attached[.]?", claim.value_raw.strip(), re.I)
        title = normalized(match[1]) if match else None
        source_docs = {evidence[eid].document_id for eid in claim.evidence_ids}
        matches = [d for d in manifest.documents if d.id not in source_docs and normalized(d.title) == title]
        if not title or len(matches) != 1:
            assessments["C08"] = "needs_review"
            add("C08", "attachment_unmatched", ["attachment_reference"], [claim],
                "No unambiguous matching attachment was found in this packet; verify with the sender. This does not establish whether an examination occurred.")
    findings.sort(key=lambda f: (f.rule_id, f.kind, tuple(f.field_keys), str(f.id)))
    return ChecklistEvaluation(revision_id=manifest.revision_id, checked_document_ids=checked,
        checked_pages=page_count, coverage=coverage, assessments=assessments,
        findings=findings, fingerprints={f.id: fingerprints[f.id] for f in findings})
