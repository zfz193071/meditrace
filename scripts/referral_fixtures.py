#!/usr/bin/env python3
"""Deterministically build/check offline synthetic fixtures; never loads .env.

Run with src/backend/.venv/bin/python. --check regenerates into a temporary
directory and compares artifact bytes and manifest content without modifying the
checked corpus. The original v1 toolchain provenance is retained across upgrades.
"""

import argparse
import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unicodedata
from uuid import NAMESPACE_URL, uuid5

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src/backend"))

import pypdf
import reportlab
from PIL import Image, ImageDraw, ImageFont
from pypdf import PdfReader, PdfWriter
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

from referral_review import CONTRACT_VERSION
from referral_review.schemas import Evidence, Fact, Finding, ReviewResult
from referral_fixture_data import Case, Source, cases
from referral_fixture_schema import (
    Checklist, DemoReview, Document, Gold, Manifest, Packet, Page, Resolution, RULE_IDS, VERSION,
)

FIXTURES = ROOT / "fixtures/referral-review"
STAMP = "2026-10-20T00:00:00Z"
GENERATOR = f"fixture-v1/reportlab-{reportlab.Version}/pypdf-{pypdf.__version__}"
FONT_DIR = Path(reportlab.__file__).parent / "fonts"
NOTICE = "SYNTHETIC - fictional training material, not clinical guidance"


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def uid(key: str):
    return uuid5(NAMESPACE_URL, f"https://example.invalid/meditrace/fixtures/v1/{key}")


def json_bytes(value) -> bytes:
    if hasattr(value, "model_dump"):
        value = value.model_dump(mode="json")
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode()


def write(path: Path, data: bytes):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def normalize(text: str) -> str:
    return unicodedata.normalize("NFC", text.replace("\r\n", "\n").replace("\r", "\n"))


def pdf_bytes(source: Source) -> bytes:
    """One fixed layout, embedded licensed Unicode font, invariant metadata."""
    pdfmetrics.registerFont(TTFont("FixtureVera", str(FONT_DIR / "Vera.ttf")))
    buffer = io.BytesIO()
    doc = canvas.Canvas(buffer, pagesize=(612, 792), invariant=1, pageCompression=1)
    doc.setTitle(source.title)
    doc.setAuthor("MediTrace synthetic fixture generator")
    doc.setSubject("Synthetic fixture only - no real patients")
    pages = source.pages
    if source.kind == "mixed":
        pages = [source.pages[0], ["Synthetic raster-only second page"]]
    if source.kind == "too_many_pages":
        pages = [[f"Synthetic page {n} of 26"] for n in range(1, 27)]
    for number, lines in enumerate(pages, 1):
        raster = source.kind == "scan" or (source.kind == "mixed" and number == 2)
        if raster:
            image = Image.new("RGB", (1224, 1584), "white")
            draw = ImageDraw.Draw(image)
            font = ImageFont.truetype(str(FONT_DIR / "Vera.ttf"), 22)
            for i, line in enumerate([NOTICE, source.title, *lines, f"Page {number}"]):
                draw.text((88, 90 + i * 40), line, fill="#182d3c", font=font)
            doc.drawImage(ImageReader(image), 0, 0, width=612, height=792)
        else:
            doc.setFillColorRGB(0.08, 0.21, 0.29)
            doc.setFont("FixtureVera", 9)
            doc.drawString(44, 752, NOTICE)
            doc.setFont("FixtureVera", 16)
            doc.drawString(44, 716, source.title)
            doc.setStrokeColorRGB(0.4, 0.65, 0.68)
            doc.line(44, 700, 568, 700)
            doc.setFont("FixtureVera", 10)
            for i, line in enumerate(lines):
                # Reject overflow instead of silently clipping/wrapping evidence.
                if pdfmetrics.stringWidth(line, "FixtureVera", 10) > 524 or i >= 29:
                    raise ValueError(f"Fixture line exceeds page layout: {source.title}")
                doc.drawString(44, 675 - i * 20, line)
            doc.setFont("FixtureVera", 9)
            doc.drawString(44, 35, f"Page {number}")
        doc.showPage()
    doc.save()
    raw = buffer.getvalue()
    if source.kind in {"encrypted", "oversized"}:
        writer = PdfWriter(clone_from=PdfReader(io.BytesIO(raw)))
        if source.kind == "encrypted":
            # Deterministic obsolete encryption ONLY as a rejection test fixture.
            writer.encrypt("synthetic-only", algorithm="RC4-128")
        else:
            writer.add_metadata({"/SyntheticPadding": "x" * (2 * 1024 * 1024)})
        out = io.BytesIO()
        writer.write(out)
        raw = out.getvalue()
    return raw


def build_document(directory: Path, key: str, number: int, source: Source) -> Document:
    stem = f"document-{number}"
    kind = "text" if source.kind == "text" else "pdf"
    if kind == "text":
        raw = normalize("\n".join([NOTICE, source.title, *source.pages[0]]) + "\n").encode()
        texts = [raw.decode()]
    elif source.kind == "corrupt":
        raw = b"%PDF-1.7\n% SYNTHETIC deliberately truncated fixture\n1 0 obj\n<< /Broken"
        texts = []
    else:
        raw = pdf_bytes(source)
        reader = PdfReader(io.BytesIO(raw))
        texts = [] if reader.is_encrypted else [normalize(p.extract_text()) for p in reader.pages]
    path = f"sources/{stem}.{ 'txt' if kind == 'text' else 'pdf'}"
    write(directory / path, raw)
    pages = []
    for page_num, text in enumerate(texts, 1):
        text_path = f"pages/{stem}-{page_num}.txt"
        write(directory / text_path, text.encode())
        pages.append(Page(number=page_num, text_path=text_path,
            text_hash=digest(text.encode()), quality="text" if text.strip() else "unreadable"))
    gate = {
        "scan": "SCANNED_PAGE", "mixed": "UNREADABLE_NONEMPTY_PAGE",
        "corrupt": "CORRUPT_PDF", "encrypted": "ENCRYPTED_PDF",
        "oversized": "PDF_TOO_LARGE", "too_many_pages": "PACKET_PAGE_LIMIT",
    }.get(source.kind)
    return Document(id=uid(f"{key}/document/{number}"), title=source.title,
        kind=kind, source_path=path, sha256=digest(raw), byte_size=len(raw),
        pages=pages, fixture_variant=source.kind, expected_gate=gate)


def occurrence_offset(text: str, quote: str, occurrence: int) -> int:
    offset = -1
    for _ in range(occurrence + 1):
        offset = text.find(quote, offset + 1)
        if offset < 0:
            raise ValueError("Authored quote occurrence not found")
    return offset


def build_gold(case: Case, docs: list[Document], directory: Path) -> Gold:
    if case.rejection:
        return Gold(automated_review_allowed=False, expected_rejection=case.rejection,
            result=None, checklist={r: "blocked" for r in RULE_IDS}, rationale_by_id={})
    facts, evidence, rationale, lookup = [], [], {}, {}
    for doc_index, (source, document) in enumerate(zip(case.docs, docs, strict=True)):
        for mark_index, mark in enumerate(source.marks):
            fact_id = uid(f"{case.key}/fact/{doc_index}/{mark_index}")
            anchors = [(mark.page, mark.quote, mark.occurrence), *mark.extra_anchors]
            evidence_ids = []
            for anchor_index, (page_num, quote, occurrence) in enumerate(anchors):
                page = document.pages[page_num - 1]
                text = (directory / page.text_path).read_text()
                offset = occurrence_offset(text, quote, occurrence)
                item = Evidence(id=uid(f"{fact_id}/evidence/{anchor_index}"),
                    document_id=document.id, page_number=page_num, start_cp=offset,
                    end_cp=offset + len(quote), quote=quote, text_hash=page.text_hash)
                evidence.append(item)
                evidence_ids.append(item.id)
            fact = Fact(id=fact_id, field_key=mark.field, value_raw=mark.value,
                value_normalized=mark.normalized, assertion_status=mark.status,
                temporal_context=mark.time, evidence_ids=evidence_ids)
            facts.append(fact)
            lookup.setdefault((doc_index, mark.field), []).append(fact)
            rationale[str(fact_id)] = (
                f"Authored annotation of {mark.field}; read the linked exact source span(s). "
                f"Preserve assertion status '{mark.status}' and raw wording; no clinical inference."
            )
    findings = []
    checks = {r: "satisfied" for r in RULE_IDS}
    checks["C08"] = "satisfied" if case.matched_attachment else "not_applicable"
    coverage = f"Checked all {len(docs)} supplied, successfully parsed documents ({sum(len(d.pages) for d in docs)} pages)."
    for i, issue in enumerate(case.issues):
        selected = [lookup[(doc_i, key)][n] for doc_i, key, n in issue.refs]
        finding = Finding(id=uid(f"{case.key}/finding/{i}"), rule_id=issue.rule,
            checklist_version=VERSION, kind=issue.kind, field_keys=issue.fields,
            fact_ids=[f.id for f in selected],
            evidence_ids=[e for f in selected for e in f.evidence_ids],
            checked_document_ids=[d.id for d in docs],
            message=f"{issue.reason} {coverage}")
        findings.append(finding)
        rationale[str(finding.id)] = issue.reason
        checks[issue.rule] = {"missing": "missing", "unknown": "needs_clarification"}.get(issue.kind, "needs_review")
    result = ReviewResult(run_id=uid(f"{case.key}/run"), revision_id=uid(f"{case.key}/revision/1"),
        mode="precomputed", created_at=STAMP, checklist_version=VERSION,
        prompt_version="authored-fixture-no-model@1", schema_version=CONTRACT_VERSION,
        facts=facts, evidence=evidence, findings=findings)
    return Gold(automated_review_allowed=True, expected_rejection=None, result=result,
        checklist=checks, rationale_by_id=rationale)


def build_public(packet: Packet, directory: Path, public: Path):
    result = packet.gold.result
    assert result is not None and packet.split == "dev"
    write(public / "documents.json", json_bytes({
        "packet_id": str(packet.id), "key": packet.key, "title": packet.title,
        "synthetic": True, "mode": "precomputed",
        "documents": [d.model_dump(mode="json") for d in packet.documents],
    }))
    for doc in packet.documents:
        for path in [doc.source_path, *(p.text_path for p in doc.pages)]:
            write(public / path, (directory / path).read_bytes())
    write(public / "run.json", json_bytes(result))
    for completed in [False, True]:
        resolutions = [Resolution(finding_id=f.id,
            status="unresolved" if completed else "open",
            reason=("Synthetic demonstration: sender clarification is still required; "
                    "no new source was supplied.") if completed else None) for f in result.findings]
        unresolved = completed and bool(result.findings)
        review = DemoReview(schema_version="demo-review-fixture-v1", illustrative_not_actual_review=True,
            packet_id=packet.id, run_id=result.run_id, revision_id=result.revision_id,
            review_version=len(resolutions) + 1 if completed else 0,
            status="confirmed" if completed else "draft", resolutions=resolutions,
            confirmed_at=STAMP if completed else None, has_unresolved=unresolved,
            identity_unresolved=completed and any(f.kind == "identity_mismatch" for f in result.findings),
            heading=("Reviewed — unresolved items remain" if unresolved else "Reviewed") if completed else "Review in progress")
        write(public / ("review-after.json" if completed else "review-before.json"), json_bytes(review))


def build(output: Path):
    checklist_raw = (FIXTURES / "checklist.json").read_bytes()
    checklist = Checklist.model_validate_json(checklist_raw)
    write(output / "checklist.json", checklist_raw)
    entries, reviews = [], []
    for case in cases():
        split = case.key.split("-")[0]
        directory = output / split / case.key
        docs = [build_document(directory, case.key, i, src) for i, src in enumerate(case.docs, 1)]
        packet = Packet(schema_version="fixture-v1", id=uid(case.key), key=case.key, split=split,
            title=case.title, synthetic=True, tags=case.tags, public_demo=case.public,
            documents=docs, gold=build_gold(case, docs, directory))
        raw = json_bytes(packet)
        path = f"{split}/{case.key}/packet.json"
        write(output / path, raw)
        entries.append(dict(key=case.key, split=split, packet_path=path,
            sha256=digest(raw), public_demo=case.public))
        reviews.append(dict(key=case.key, packet_sha256=digest(raw), status="pending",
            reviewer=None, reviewed_at=None, observations=None))
        if case.public:
            build_public(packet, directory, output / "public" / case.key)
    write(output / "operator-review-template.json", json_bytes({
        "annotation_version": "synthetic-referral@1", "entries": reviews,
        "instructions": "Copy outside generated files; inspect all facts, findings, missing scopes and source pages; record actual reviewer and date. Do not claim expert review.",
    }))
    write(output / "fixture.schema.json", json_bytes({
        name: cls.model_json_schema() for name, cls in [
            ("checklist", Checklist), ("packet", Packet), ("demo_review", DemoReview), ("manifest", Manifest)]
    }))
    write(output / "BITSTREAM-VERA-LICENSE.txt", (FONT_DIR / "bitstream-vera-license.txt").read_bytes())
    files = {name: digest(raw) for name, raw in generated_paths(output).items() if name != "manifest.json"}
    manifest = Manifest(schema_version="fixture-manifest-v1", corpus_version="synthetic-referral@1",
        checklist_version=checklist.version, checklist_sha256=digest(checklist_raw),
        annotation_status="provisional_operator_review_pending", test_split_policy="held_out_from_prompts_not_secret",
        parser_version=f"pypdf-{pypdf.__version__}/text-v1",
        generator_version=GENERATOR, entries=entries, files=files)
    write(output / "manifest.json", json_bytes(manifest))


def generated_paths(directory: Path):
    # Docs, license and review records are authored files, never overwritten.
    return {p.relative_to(directory).as_posix(): p.read_bytes()
        for name in ["dev", "test", "public"] for p in (directory / name).rglob("*") if p.is_file()} | {
        name: (directory / name).read_bytes() for name in [
            "checklist.json", "manifest.json", "fixture.schema.json",
            "operator-review-template.json", "BITSTREAM-VERA-LICENSE.txt",
        ] if (directory / name).exists()
    }


def generated_differences(existing: dict[str, bytes], fresh: dict[str, bytes]) -> list[str]:
    """Only the known archived v1 toolchain labels may differ after regeneration.

    Original source bytes, pages, labels, hashes, schema and manifest entries must
    still match exactly. Never rewrite frozen data or claim it used today's parser.
    """
    compared = dict(fresh)
    if "manifest.json" in existing and "manifest.json" in fresh:
        archived = json.loads(existing["manifest.json"])
        regenerated = json.loads(fresh["manifest.json"])
        historical = {
            "parser_version": "pypdf-6.21.1/text-v1",
            "generator_version": "fixture-v1/reportlab-4.5.1/pypdf-6.21.1",
        }
        current = {"parser_version": f"pypdf-{pypdf.__version__}/text-v1", "generator_version": GENERATOR}
        if (archived.get("corpus_version") == regenerated.get("corpus_version") == "synthetic-referral@1"
                and all(archived.get(k) == v for k, v in historical.items())
                and all(regenerated.get(k) == v for k, v in current.items())):
            compared["manifest.json"] = json_bytes(regenerated | historical)
    return sorted(k for k in existing.keys() | compared.keys() if existing.get(k) != compared.get(k))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--output-root", type=Path)
    args = parser.parse_args()
    if args.write == args.check:
        parser.error("Choose exactly one of --write or --check")
    output = args.output_root or FIXTURES
    if args.write:
        build(output)
        print("Generated 30 synthetic packets and 3 precomputed demos. Operator review pending.")
    else:
        with tempfile.TemporaryDirectory(prefix="rr-fixtures-") as tmp:
            expected = Path(tmp)
            build(expected)
            existing, fresh = generated_paths(output), generated_paths(expected)
            changed = generated_differences(existing, fresh)
            if changed:
                print("Fixture drift: " + ", ".join(changed))
                return 1
        print(f"Fixture artifacts and manifest content match (30 packets, 3 demos); "
              f"archived toolchain provenance retained, checked with {GENERATOR}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
