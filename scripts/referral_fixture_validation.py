"""Read-only cross-file checks for fixture integrity, not model quality scores."""

import io
import json
from pathlib import Path

from pypdf import PdfReader
from pypdf.errors import PdfReadError

from referral_fixtures import digest, generated_paths, normalize
from referral_fixture_schema import Checklist, DemoReview, Document, Manifest, Packet, RULE_IDS
from referral_review.schemas import ReviewResult


def local_path(directory: Path, relative: str) -> Path:
    path = (directory / relative).resolve()
    if Path(relative).is_absolute() or not path.is_relative_to(directory.resolve()):
        raise ValueError("Fixture path escapes its directory")
    return path


def validate_document(directory: Path, doc: Document):
    raw = local_path(directory, doc.source_path).read_bytes()
    assert len(raw) == doc.byte_size and digest(raw) == doc.sha256
    if doc.fixture_variant == "corrupt":
        try:
            PdfReader(io.BytesIO(raw))
        except PdfReadError:
            assert not doc.pages and doc.expected_gate == "CORRUPT_PDF"
            return
        raise AssertionError("Corrupt fixture unexpectedly parsed")
    if doc.kind == "pdf":
        reader = PdfReader(io.BytesIO(raw))
        if doc.fixture_variant == "encrypted":
            assert reader.is_encrypted and not doc.pages and doc.expected_gate == "ENCRYPTED_PDF"
            return
        assert not reader.is_encrypted
        extracted = [normalize(p.extract_text()) for p in reader.pages]
    else:
        extracted = [normalize(raw.decode())]
    assert len(extracted) == len(doc.pages)
    for i, (text, page) in enumerate(zip(extracted, doc.pages, strict=True), 1):
        assert page.number == i
        stored = local_path(directory, page.text_path).read_text()
        assert stored == text and digest(stored.encode()) == page.text_hash
        assert page.quality == ("text" if text.strip() else "unreadable")
        if page.quality == "text":
            assert "SYNTHETIC" in text
    if doc.fixture_variant == "scan":
        assert all(not t.strip() for t in extracted)
        assert all("/XObject" in p["/Resources"] for p in reader.pages)
    elif doc.fixture_variant == "mixed":
        assert len(extracted) == 2 and extracted[0].strip() and not extracted[1].strip()
        assert "/XObject" in reader.pages[1]["/Resources"]
    elif doc.fixture_variant == "oversized":
        assert len(raw) > 2 * 1024 * 1024 and len(extracted) == 1
    elif doc.fixture_variant == "too_many_pages":
        assert len(extracted) == 26
    else:
        assert doc.expected_gate is None
        assert all(t.strip() for t in extracted)
        if doc.kind == "pdf":
            assert len(raw) <= 2 * 1024 * 1024
        else:
            assert len(extracted[0]) <= 10_000


def validate_packet(directory: Path, packet: Packet, checklist: Checklist):
    assert packet.key.startswith(packet.split + "-")
    assert len({d.id for d in packet.documents}) == len(packet.documents)
    docs = {d.id: d for d in packet.documents}
    for doc in docs.values():
        validate_document(directory, doc)
    if packet.gold.expected_rejection:
        assert packet.gold.expected_rejection in {d.expected_gate for d in docs.values()}
        assert not packet.public_demo
        return
    assert all(not d.expected_gate for d in docs.values())
    assert sum(len(d.pages) for d in docs.values()) <= 25
    assert sum(d.byte_size for d in docs.values() if d.kind == "pdf") <= 10 * 1024 * 1024
    assert sum(len(local_path(directory, p.text_path).read_text()) for d in docs.values() for p in d.pages) <= 30_000
    result = packet.gold.result
    assert result is not None
    evidence = {e.id: e for e in result.evidence}
    facts = {f.id: f for f in result.facts}
    for e in evidence.values():
        doc = docs[e.document_id]
        page = doc.pages[e.page_number - 1]
        text = local_path(directory, page.text_path).read_text()
        assert e.text_hash == page.text_hash
        assert 0 <= e.start_cp < e.end_cp <= len(text)
        assert text[e.start_cp:e.end_cp] == e.quote
    rules = {r.id: r for r in checklist.rules}
    assert set(packet.gold.rationale_by_id) == {str(i.id) for i in [*result.facts, *result.findings]}
    assert {eid for f in result.facts for eid in f.evidence_ids} == set(evidence)
    for f in result.findings:
        assert set(f.checked_document_ids) == set(docs)
        assert set(f.field_keys).issubset(rules[f.rule_id].fields)
        assert "successfully parsed documents" in f.message
        assert packet.gold.rationale_by_id[str(f.id)] in f.message
        if f.kind == "missing":
            assert not f.evidence_ids and not f.fact_ids
            assert not any(fact.field_key in f.field_keys for fact in facts.values())
            assert packet.gold.checklist[f.rule_id] == "missing"
        else:
            assert f.fact_ids and f.evidence_ids
            assert set(f.evidence_ids) == {eid for fid in f.fact_ids for eid in facts[fid].evidence_ids}
        if f.kind == "identity_mismatch":
            assert len(f.fact_ids) >= 2 and len({facts[i].value_raw for i in f.fact_ids}) >= 2
        if f.kind == "unknown":
            assert all(facts[i].assertion_status == "unknown" for i in f.fact_ids)
            assert packet.gold.checklist[f.rule_id] == "needs_clarification"
        if f.kind == "statement_difference":
            times = {facts[i].temporal_context for i in f.fact_ids}
            assert None not in times and len(times) == 1
    for rule_id, state in packet.gold.checklist.items():
        issues = [f for f in result.findings if f.rule_id == rule_id]
        if state in {"satisfied", "not_applicable"}:
            assert not issues
        else:
            assert issues
        if state == "satisfied" and rule_id != "C08":
            assert set(rules[rule_id].fields).issubset({f.field_key for f in result.facts})
    if "clean" in packet.tags:
        assert not result.findings
    # Safety checks for this deliberately fictional dataset, not generic PHI detection.
    for fact in result.facts:
        if fact.field_key in {"patient.name", "referrer.name"}:
            assert fact.value_raw.startswith("Synthetic ")
        if fact.field_key == "referrer.contact":
            assert fact.value_raw.endswith("@example.invalid")


def validate_public(root: Path, packet: Packet):
    directory = root / "public" / packet.key
    result = ReviewResult.model_validate_json((directory / "run.json").read_bytes())
    assert result == packet.gold.result and packet.split == "dev"
    docs = json.loads((directory / "documents.json").read_text())
    assert docs["packet_id"] == str(packet.id) and docs["synthetic"] is True and docs["mode"] == "precomputed"
    assert docs["documents"] == [d.model_dump(mode="json") for d in packet.documents]
    for doc in packet.documents:
        validate_document(directory, doc)
    for name in ["before", "after"]:
        review = DemoReview.model_validate_json((directory / f"review-{name}.json").read_bytes())
        assert review.packet_id == packet.id and review.run_id == result.run_id and review.revision_id == result.revision_id
        assert {r.finding_id for r in review.resolutions} == {f.id for f in result.findings}
        assert review.status == ("draft" if name == "before" else "confirmed")
        assert all(r.status == ("open" if name == "before" else "unresolved") for r in review.resolutions)
        identity_ids = {f.id for f in result.findings if f.kind == "identity_mismatch"}
        assert review.identity_unresolved == any(r.finding_id in identity_ids and r.status == "unresolved" for r in review.resolutions)
        if name == "after" and review.has_unresolved:
            assert review.heading == "Reviewed — unresolved items remain"


def validate_corpus(root: Path):
    manifest = Manifest.model_validate_json((root / "manifest.json").read_bytes())
    checklist = Checklist.model_validate_json((root / "checklist.json").read_bytes())
    assert manifest.checklist_sha256 == digest((root / "checklist.json").read_bytes())
    paths = generated_paths(root)
    assert set(manifest.files) == set(paths) - {"manifest.json"}
    for name, hash_value in manifest.files.items():
        assert digest(local_path(root, name).read_bytes()) == hash_value
    packets = []
    for entry in manifest.entries:
        path = local_path(root, entry.packet_path)
        assert digest(path.read_bytes()) == entry.sha256
        packet = Packet.model_validate_json(path.read_bytes())
        assert (packet.key, packet.split, packet.public_demo) == (entry.key, entry.split, entry.public_demo)
        validate_packet(path.parent, packet, checklist)
        if entry.public_demo:
            validate_public(root, packet)
        packets.append(packet)
    assert len({p.id for p in packets}) == 30
    assert len({d.id for p in packets for d in p.documents}) == sum(len(p.documents) for p in packets)
    assert sum(p.split == "test" and p.gold.result is not None and not p.gold.result.findings for p in packets) >= 5
    review = json.loads((root / "operator-review-template.json").read_text())
    assert {e["key"] for e in review["entries"]} == {p.key for p in packets}
    hashes = {e.key: e.sha256 for e in manifest.entries}
    for entry in review["entries"]:
        assert entry["packet_sha256"] == hashes[entry["key"]]
        assert entry["status"] == "pending" and entry["reviewer"] is None
    return packets
