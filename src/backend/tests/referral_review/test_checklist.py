"""Rules run on authored development facts, never model requests or frozen test labels."""
import json
from pathlib import Path
from uuid import uuid4

import pytest

from referral_review.checklist import ChecklistError, ChecklistManifest, DifferenceCandidate, evaluate
from referral_review.extraction.contracts import Extraction

FIXTURES = Path(__file__).resolve().parents[4] / "fixtures/referral-review/dev"


def load_case(key):
    root = FIXTURES / key
    data = json.loads((root / "packet.json").read_text())
    result = data["gold"]["result"]
    extraction = Extraction(revision_id=result["revision_id"], mode="fake", model_requested="authored-fixture",
        model_reported=None, provider_request_id=None, usage=None, facts=result["facts"], evidence=result["evidence"])
    docs = []
    for doc in data["documents"]:
        docs.append(dict(id=doc["id"], title=doc["title"], kind=doc["kind"], parse_status="ready",
            page_count=len(doc["pages"]), pages=[dict(document_id=doc["id"], page_number=p["number"],
                normalized_text=(root / p["text_path"]).read_text(), text_hash=p["text_hash"],
                parse_quality="ready", parser_version="text-v1") for p in doc["pages"]]))
    return extraction, ChecklistManifest(revision_id=extraction.revision_id, documents=docs), data["gold"]


@pytest.mark.parametrize("key", [f"dev-{n:02}" for n in range(1, 10)])
def test_development_golden_rules(key):
    extraction, manifest, gold = load_case(key)
    result = evaluate(extraction, manifest)
    assert result.assessments == gold["checklist"]
    signature = lambda fs: sorted((f["rule_id"], f["kind"], tuple(f["field_keys"])) for f in fs)
    assert signature(result.model_dump(mode="json")["findings"]) == signature(gold["result"]["findings"])
    for finding in result.findings:
        assert set(finding.checked_document_ids) == {d.id for d in manifest.documents}
        assert result.coverage in finding.message
        if finding.kind == "missing":
            assert finding.evidence_ids == finding.fact_ids == []
        if finding.kind in ("identity_mismatch", "statement_difference"):
            assert len(finding.fact_ids) >= 2 and len(finding.evidence_ids) >= 2


def test_repeated_and_permuted_inputs_have_stable_results():
    extraction, manifest, _ = load_case("dev-01")
    original = evaluate(extraction, manifest).model_dump(mode="json")
    assert original == evaluate(extraction, manifest).model_dump(mode="json")
    extraction.facts.reverse()
    extraction.evidence.reverse()
    manifest.documents.reverse()
    assert original == evaluate(extraction, manifest).model_dump(mode="json")


@pytest.mark.parametrize("mutation,code", [("version", "CHECKLIST_UNSUPPORTED"),
    ("rejected", "PARSE_COVERAGE_INCOMPLETE"), ("unreadable", "PARSE_COVERAGE_INCOMPLETE"),
    ("missing_page", "PARSE_COVERAGE_INCOMPLETE"), ("hash", "CHECKLIST_INPUT_INVALID"),
    ("foreign", "CHECKLIST_INPUT_INVALID"), ("revision", "CHECKLIST_INPUT_INVALID"),
    ("duplicate", "CHECKLIST_INPUT_INVALID"), ("missing_evidence", "CHECKLIST_INPUT_INVALID")])
def test_invalid_coverage_never_becomes_missing_findings(mutation, code):
    extraction, manifest, _ = load_case("dev-01")
    version = "outpatient-referral-demo@1"
    if mutation == "version": version = "unknown"
    if mutation == "rejected": manifest.documents[0].parse_status = "rejected"
    if mutation == "unreadable": manifest.documents[0].pages[0].parse_quality = "unreadable"
    if mutation == "missing_page": manifest.documents[0].page_count += 1
    if mutation == "hash": manifest.documents[0].pages[0].text_hash = "0" * 64
    if mutation == "foreign": extraction.evidence[0].document_id = uuid4()
    if mutation == "revision": manifest.revision_id = uuid4()
    if mutation == "duplicate": extraction.facts.append(extraction.facts[0])
    if mutation == "missing_evidence": extraction.facts[0].evidence_ids = [uuid4()]
    with pytest.raises(ChecklistError, match=code): evaluate(extraction, manifest, version)


def test_unknown_none_and_not_provided_distinct():
    extraction, manifest, _ = load_case("dev-02")
    assert evaluate(extraction, manifest).assessments["C07"] == "needs_clarification"
    assert evaluate(extraction, manifest).assessments["C06"] == "satisfied"
    extraction.facts = [f for f in extraction.facts if f.field_key != "allergies"]
    assert evaluate(extraction, manifest).assessments["C07"] == "missing"


def test_candidates_cannot_create_different_date_conflict():
    extraction, manifest, _ = load_case("dev-03")
    meds = [f for f in extraction.facts if f.field_key == "medications"]
    candidate = DifferenceCandidate(field_key="medications", fact_ids=[f.id for f in meds])
    assert evaluate(extraction, manifest, candidates=(candidate,)).findings == []
    candidate.fact_ids[0] = uuid4()
    with pytest.raises(ChecklistError, match="CHECKLIST_INPUT_INVALID"):
        evaluate(extraction, manifest, candidates=(candidate,))


def test_ambiguous_or_missing_time_cannot_create_conflict():
    extraction, manifest, _ = load_case("dev-06")
    meds = [f for f in extraction.facts if f.field_key == "medications"]
    for time in (None, "03/04/2026", "current"):
        for f in meds: f.temporal_context = time
        assert not any(f.kind == "statement_difference" for f in evaluate(extraction, manifest).findings)


def test_ambiguous_dob_not_normalized_from_model_value():
    extraction, manifest, _ = load_case("dev-01")
    dob = [f for f in extraction.facts if f.field_key == "patient.dob"]
    dob[0].value_raw = "03/04/1980"
    dob[0].value_normalized = "1980-03-04"
    # Rules intentionally use raw dates; upstream extraction validates raw support.
    assert not any(f.kind == "identity_mismatch" for f in evaluate(extraction, manifest).findings)


def test_name_normalization_never_fuzzy_merges():
    extraction, manifest, _ = load_case("dev-03")
    name = next(f for f in extraction.facts if f.field_key == "patient.name")
    second = name.model_copy(deep=True)
    second.id = uuid4()
    second.value_raw = "  " + name.value_raw.upper().replace(" ", "  ") + " "
    extraction.facts.append(second)
    assert not any(f.kind == "identity_mismatch" for f in evaluate(extraction, manifest).findings)
    second.value_raw = "Different Name"
    assert any(f.kind == "identity_mismatch" for f in evaluate(extraction, manifest).findings)


def test_ambiguous_attachment_titles_remain_unmatched():
    extraction, manifest, _ = load_case("dev-03")
    report = next(d for d in manifest.documents if "Report" in d.title)
    duplicate = report.model_copy(deep=True)
    duplicate.id = uuid4()
    for page in duplicate.pages: page.document_id = duplicate.id
    manifest.documents.append(duplicate)
    result = evaluate(extraction, manifest)
    assert result.assessments["C08"] == "needs_review"
    finding = next(f for f in result.findings if f.kind == "attachment_unmatched")
    assert "does not establish" in finding.message


def test_dose_change_without_explicit_opposition_is_not_a_conflict():
    from referral_review.checklist.service import directly_opposed
    extraction, _, _ = load_case("dev-03")
    meds = [f.model_copy(deep=True) for f in extraction.facts if f.field_key == "medications"]
    meds[1].temporal_context = meds[0].temporal_context
    assert not directly_opposed(*meds)


def test_fixed_rule_fields_match_versioned_checklist():
    from referral_review.checklist.service import RULE_FIELDS
    checklist = json.loads((FIXTURES.parent / "checklist.json").read_text())
    assert {r["id"]: tuple(r["fields"]) for r in checklist["rules"]} == RULE_FIELDS
    assert checklist["version"] == "outpatient-referral-demo@1"


@pytest.mark.parametrize("negative,positive,opposed", [
    ("not taking FictionalMed B.", "currently taking FictionalMed B 2 mg daily.", True),
    ("not taking FictionalMed B.", "currently taking FictionalMed C 2 mg daily.", False),
    ("not taking FictionalMed B.", "currently taking FictionalMed B Plus 2 mg daily.", False),
    ("not taking FictionalMed B.", "not taking FictionalMed B 2 mg daily.", False),
])
def test_opposition_requires_exact_drug_not_just_negation(negative, positive, opposed):
    from referral_review.checklist.service import directly_opposed
    extraction, _, _ = load_case("dev-06")
    a, b = [f.model_copy(deep=True) for f in extraction.facts if f.field_key == "medications"]
    a.value_raw, b.value_raw = negative, positive
    a.assertion_status, b.assertion_status = "explicitly_none", "stated"
    assert directly_opposed(a, b) is opposed


@pytest.mark.parametrize("raw,expected", [("June 15, 1980", "1980-06-15"),
    ("15 June 1980", "1980-06-15"), ("03/04/1980", None), ("1980-02-30", None)])
def test_date_normalization_is_explicit_and_locale_independent(raw, expected):
    from referral_review.checklist.service import complete_date
    assert complete_date(raw) == expected
