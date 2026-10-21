"""MT-06 synthetic parser corpus; no model or browser calls."""

import json
from io import BytesIO
from pathlib import Path
import subprocess

import pytest

from referral_review.documents import parser
from referral_review.documents.text_rules import EvidenceInvalid, locate_quote, normalize_text, text_hash, verify_anchor

ROOT = Path(__file__).resolve().parents[4]
FIXTURES = ROOT / "fixtures/referral-review"


def test_unicode_offset_golden_matches_typescript_fixture():
    golden = json.loads((FIXTURES / "offsets-golden.json").read_text())
    page = normalize_text(golden["source"])
    anchor = locate_quote(page, golden["quote"], before=golden["before"])
    assert page == golden["normalized"]
    assert (anchor.start_cp, anchor.end_cp, anchor.text_hash) == (
        golden["start_cp"], golden["end_cp"], golden["text_hash"])
    verify_anchor(page, anchor)
    with pytest.raises(EvidenceInvalid, match="ambiguous"):
        locate_quote(page, golden["quote"])
    with pytest.raises(EvidenceInvalid):
        verify_anchor(page + "!", anchor)


def test_pasted_text_is_one_frozen_page():
    parsed = parser.parse_text("A\r\n李😀é".encode())
    assert parsed.status == "ready" and parsed.page_count == 1
    assert parsed.pages[0].normalized_text == "A\n李😀é"
    assert parsed.pages[0].text_hash == text_hash("A\n李😀é")
    assert parser.parse_text(("A" * 10_001).encode()).issue_code == "TEXT_UNSUPPORTED"


@pytest.mark.parametrize("name,expected,count", [
    ("public/dev-01/sources/document-1.pdf", None, 1),
    ("test/test-14/sources/document-2.pdf", None, 2),
    ("dev/dev-10/sources/document-2.pdf", "PDF_UNREADABLE_PAGE", 1),
    ("test/test-15/sources/document-2.pdf", "PDF_DAMAGED", None),
    ("test/test-18/sources/document-2.pdf", "PDF_ENCRYPTED", None),
    ("test/test-20/sources/document-2.pdf", "PDF_PAGE_LIMIT", 26),
])
def test_pdf_corpus(name, expected, count):
    parsed = parser.parse_pdf((FIXTURES / name).read_bytes())
    assert parsed.issue_code == expected
    assert parsed.page_count == count
    if expected is None:
        assert len(parsed.pages) == count
        assert all(p.text_hash == text_hash(p.normalized_text) for p in parsed.pages)
    if expected == "PDF_UNREADABLE_PAGE":
        assert parsed.issue_page == 1
        assert parsed.pages[0].parse_quality == "unreadable"


def test_timeout_kills_only_created_worker(monkeypatch):
    class Worker:
        returncode = None
        killed = False
        def communicate(self, body=None, timeout=None):
            if body is not None:
                raise subprocess.TimeoutExpired("worker", timeout)
            return b"", b""
        def kill(self):
            self.killed = True
    worker = Worker()
    monkeypatch.setattr(parser.subprocess, "Popen", lambda *args, **kwargs: worker)
    parsed = parser.parse_pdf(b"%PDF-1.7\n")
    assert parsed.issue_code == "PDF_TIMEOUT" and worker.killed


def test_worker_response_and_input_are_bounded(monkeypatch):
    assert parser.parse_pdf(b"a" * (2 * 1024 * 1024 + 1)).issue_code == "PDF_RESOURCE_LIMIT"
    class Worker:
        returncode = 0
        def communicate(self, body=None, timeout=None):
            return b"x" * (parser.MAX_WORKER_OUTPUT_BYTES + 1), b""
    monkeypatch.setattr(parser.subprocess, "Popen", lambda *args, **kwargs: Worker())
    assert parser.parse_pdf(b"%PDF-1.7\n").issue_code == "PDF_RESOURCE_LIMIT"


def test_blank_page_is_distinct_from_compressed_content_limit():
    from pypdf import PdfWriter
    from pypdf.generic import DecodedStreamObject, NameObject

    blank = PdfWriter()
    blank.add_blank_page(width=200, height=200)
    data = BytesIO()
    blank.write(data)
    parsed = parser.parse_pdf(data.getvalue())
    assert parsed.status == "ready" and parsed.pages[0].parse_quality == "empty"

    bomb = PdfWriter()
    page = bomb.add_blank_page(width=200, height=200)
    stream = DecodedStreamObject()
    stream.set_data(b" " * (parser.MAX_CONTENT_STREAM_BYTES + 1))
    page[NameObject("/Contents")] = bomb._add_object(stream.flate_encode())
    data = BytesIO()
    bomb.write(data)
    assert len(data.getvalue()) < 2 * 1024 * 1024
    parsed = parser.parse_pdf(data.getvalue())
    assert parsed.issue_code == "PDF_CONTENT_LIMIT" and parsed.issue_page == 1


def test_mixed_text_and_image_is_not_trusted_as_complete_text():
    from PIL import Image
    from reportlab.pdfgen import canvas

    data = BytesIO()
    page = canvas.Canvas(data)
    page.drawString(40, 700, "Extractable referral text")
    page.drawInlineImage(Image.new("RGB", (2, 2), "black"), 40, 600)
    page.save()
    parsed = parser.parse_pdf(data.getvalue())
    assert parsed.issue_code == "PDF_UNREADABLE_PAGE"
    assert parsed.issue_page == 1 and parsed.pages[0].parse_quality == "unreadable"
    assert "Extractable" in parsed.pages[0].normalized_text
