"""Offline authored gold, parser read-back, schema and packaging regressions."""

import copy
import json
from pathlib import Path
import subprocess
import sys

import pytest
from pydantic import ValidationError

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "scripts"))

from referral_fixture_schema import Checklist, DemoReview, Gold, Manifest, Packet
from referral_fixture_validation import local_path, validate_corpus, validate_packet, validate_public
from referral_fixtures import FIXTURES, GENERATOR, digest, generated_differences, json_bytes, occurrence_offset


def load_packet(key):
    path = FIXTURES / key.split("-")[0] / key / "packet.json"
    return path, Packet.model_validate_json(path.read_bytes())


def test_complete_corpus():
    packets = validate_corpus(FIXTURES)
    assert len(packets) == 30
    assert sum(p.gold.result is None for p in packets) == 7


@pytest.mark.parametrize("key", [f"dev-{n:02}" for n in range(1, 11)] + [f"test-{n:02}" for n in range(1, 21)])
def test_each_packet(key):
    path, packet = load_packet(key)
    checklist = Checklist.model_validate_json((FIXTURES / "checklist.json").read_bytes())
    validate_packet(path.parent, packet, checklist)


@pytest.mark.parametrize("key", ["dev-01", "dev-02", "dev-03"])
def test_public_states(key):
    _, packet = load_packet(key)
    validate_public(FIXTURES, packet)


def test_deterministic_regeneration():
    subprocess.run([sys.executable, str(ROOT / "scripts/referral_fixtures.py"), "--check"], check=True)


def test_toolchain_upgrade_preserves_archived_provenance_without_hiding_content_drift():
    import pypdf

    archived = (FIXTURES / "manifest.json").read_bytes()
    current = json.loads(archived)
    current.update(parser_version=f"pypdf-{pypdf.__version__}/text-v1", generator_version=GENERATOR)
    existing = {"manifest.json": archived, "source.pdf": b"frozen source"}
    fresh = {"manifest.json": json_bytes(current), "source.pdf": b"frozen source"}
    assert generated_differences(existing, fresh) == []
    assert generated_differences(existing, fresh | {"source.pdf": b"changed source"}) == ["source.pdf"]
    changed = copy.deepcopy(current)
    changed["entries"][0]["sha256"] = "0" * 64
    assert generated_differences(existing, fresh | {"manifest.json": json_bytes(changed)}) == ["manifest.json"]
    unknown = json.loads(archived)
    unknown["parser_version"] = "unverified-parser"
    assert generated_differences(existing | {"manifest.json": json_bytes(unknown)}, fresh) == ["manifest.json"]


def test_wrong_quote_offsets_and_hash_are_rejected():
    path, original = load_packet("dev-01")
    checklist = Checklist.model_validate_json((FIXTURES / "checklist.json").read_bytes())
    for attribute, value in [("text_hash", "0" * 64), ("start_cp", 0), ("quote", "fabricated source")]:
        packet = copy.deepcopy(original)
        setattr(packet.gold.result.evidence[0], attribute, value)
        with pytest.raises(AssertionError):
            validate_packet(path.parent, packet, checklist)


def test_missing_labels_have_no_invented_evidence():
    _, packet = load_packet("test-11")
    assert len(packet.gold.result.findings) == 2
    assert all(not f.fact_ids and not f.evidence_ids for f in packet.gold.result.findings)
    assert all("successfully parsed" in f.message for f in packet.gold.result.findings)


def test_unknown_none_missing_are_distinct():
    _, unknown = load_packet("dev-02")
    _, negative = load_packet("test-01")
    _, missing = load_packet("test-11")
    allergy = lambda p: [f for f in p.gold.result.facts if f.field_key == "allergies"]
    assert allergy(unknown)[0].assertion_status == "unknown"
    assert allergy(negative)[0].assertion_status == "explicitly_none"
    assert not allergy(missing)
    assert unknown.gold.checklist["C07"] == "needs_clarification"
    assert negative.gold.checklist["C07"] == "satisfied"
    assert missing.gold.checklist["C07"] == "missing"


def test_ambiguous_date_is_not_normalized():
    _, packet = load_packet("test-04")
    fact = next(f for f in packet.gold.result.facts if f.field_key == "patient.dob")
    assert fact.value_normalized is None and fact.value_raw.startswith("03/04/")
    assert not packet.gold.result.findings


def test_different_dates_not_conflicts_and_same_date_opposition_is():
    for key in ["dev-03", "test-03"]:
        _, packet = load_packet(key)
        assert not packet.gold.result.findings
        assert len({f.temporal_context for f in packet.gold.result.facts if f.field_key == "medications"}) == 2
    _, packet = load_packet("test-12")
    assert packet.gold.result.findings[0].kind == "statement_difference"


def test_duplicate_occurrence_and_cross_page_are_local():
    _, repeat = load_packet("test-05")
    facts = [f for f in repeat.gold.result.facts if f.field_key == "allergies"]
    assert len(facts[0].evidence_ids) == 2
    spans = [e for e in repeat.gold.result.evidence if e.id in facts[0].evidence_ids]
    assert spans[0].quote == spans[1].quote and spans[0].start_cp != spans[1].start_cp
    _, cross = load_packet("test-14")
    fact = next(f for f in cross.gold.result.facts if f.field_key == "report.description")
    assert {e.page_number for e in cross.gold.result.evidence if e.id in fact.evidence_ids} == {1, 2}
    with pytest.raises(ValueError):
        occurrence_offset("one quote", "quote", 1)


def test_astral_character_offsets_are_codepoints_not_utf16():
    path, packet = load_packet("dev-08")
    evidence = next(e for e in packet.gold.result.evidence if e.quote.startswith("DOB:"))
    text = (path.parent / packet.documents[0].pages[0].text_path).read_text()
    assert "🧪" in text[:evidence.start_cp]
    assert len(text[:evidence.start_cp].encode("utf-16-le")) // 2 > evidence.start_cp
    assert text[evidence.start_cp:evidence.end_cp] == evidence.quote


def test_invalid_checklist_version_and_rule_set_rejected():
    raw = json.loads((FIXTURES / "checklist.json").read_text())
    for mutate in [
        lambda d: d.update(version="outpatient-referral-demo@2"),
        lambda d: d["rules"].pop(),
        lambda d: d["rules"].append(d["rules"][0]),
    ]:
        bad = copy.deepcopy(raw)
        mutate(bad)
        with pytest.raises(ValidationError):
            Checklist.model_validate(bad)


def test_blocked_packet_cannot_have_success_result_or_missing_labels():
    _, packet = load_packet("test-17")
    gold = packet.gold.model_dump(mode="json")
    gold["checklist"]["C07"] = "missing"
    with pytest.raises(ValidationError):
        Gold.model_validate(gold)
    gold = packet.gold.model_dump(mode="json")
    gold["automated_review_allowed"] = True
    with pytest.raises(ValidationError):
        Gold.model_validate(gold)


def test_demo_cannot_confirm_open_items_or_omit_reasons():
    raw = json.loads((FIXTURES / "public/dev-01/review-after.json").read_text())
    for mutate in [
        lambda d: d["resolutions"][0].update(status="open"),
        lambda d: d["resolutions"][0].update(reason=" "),
        lambda d: d.update(has_unresolved=False),
        lambda d: d.update(confirmed_at=None),
    ]:
        bad = copy.deepcopy(raw)
        mutate(bad)
        with pytest.raises(ValidationError):
            DemoReview.model_validate(bad)


def test_held_out_cannot_become_public_and_paths_cannot_escape():
    raw = json.loads((FIXTURES / "manifest.json").read_text())
    next(e for e in raw["entries"] if e["split"] == "test")["public_demo"] = True
    with pytest.raises(ValidationError):
        Manifest.model_validate(raw)
    for path in ["../../.env", "/etc/passwd"]:
        with pytest.raises(ValueError):
            local_path(FIXTURES, path)
    assert "fixtures/referral-review/" in (ROOT / ".vercelignore").read_text()
    assert sorted(p.name for p in (FIXTURES / "public").iterdir()) == ["dev-01", "dev-02", "dev-03"]
    for path in (ROOT / "src/frontend").rglob("*.ts*"):
        if {"node_modules", ".next"}.intersection(path.parts):
            continue
        assert "fixtures/referral-review/test" not in path.read_text()


def test_frozen_split_and_checklist_lock():
    lock = json.loads((FIXTURES / "freeze.json").read_text())
    assert digest((FIXTURES / "checklist.json").read_bytes()) == lock["checklist_sha256"]
    manifest = Manifest.model_validate_json((FIXTURES / "manifest.json").read_bytes())
    assert {e.key: e.sha256 for e in manifest.entries if e.split == "test"} == lock["test_packets"]
