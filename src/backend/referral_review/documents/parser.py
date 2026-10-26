"""Bounded PDF subprocess and stable page-result transport."""

from dataclasses import dataclass
import json
from pathlib import Path
import subprocess
import sys

from .text_rules import normalize_text, text_hash

MAX_PAGES = 25
MAX_PAGE_CODEPOINTS = 12_000
MAX_DOCUMENT_CODEPOINTS = 30_000
MAX_CONTENT_STREAM_BYTES = 1_000_000
MAX_WORKER_OUTPUT_BYTES = 200_000
PARSER_TIMEOUT_SECONDS = 20
BACKEND = Path(__file__).resolve().parents[2]
PDF_PARSER_VERSION = "pypdf-6.21.2/text-v1"


@dataclass(frozen=True)
class ParsedPage:
    page_number: int
    normalized_text: str
    text_hash: str
    parse_quality: str


@dataclass(frozen=True)
class ParseResult:
    parser_version: str
    page_count: int | None
    pages: tuple[ParsedPage, ...]
    issue_code: str | None = None
    issue_page: int | None = None

    @property
    def status(self):
        return "rejected" if self.issue_code else "ready"


def rejected(code, page=None, *, parser_version=PDF_PARSER_VERSION, page_count=None):
    return ParseResult(parser_version, page_count, (), code, page)


def parse_text(body: bytes) -> ParseResult:
    try:
        original = body.decode("utf-8", errors="strict")
        normalized = normalize_text(original)
        if not normalized.strip() or len(original) > 10_000 or len(normalized) > 10_000:
            return rejected("TEXT_UNSUPPORTED", 1, parser_version="text-v1", page_count=1)
        page = ParsedPage(1, normalized, text_hash(normalized), "ready")
        return ParseResult("text-v1", 1, (page,))
    except UnicodeError:
        return rejected("TEXT_UNSUPPORTED", 1, parser_version="text-v1", page_count=1)


def parse_pdf(body: bytes, *, timeout=PARSER_TIMEOUT_SECONDS, runner=None) -> ParseResult:
    """Run only our fixed worker; stderr is discarded to avoid leaking PDF data.

    The worker sets its own CPU/address-space/pypdf decoding bounds. This parent
    imposes the wall deadline, kills only the created child, and accepts a small
    validated response. No supplied PDF path reaches the filesystem.
    """
    command = [sys.executable, "-m", "referral_review.documents.pdf_worker"]
    if len(body) > 2 * 1024 * 1024:
        return rejected("PDF_RESOURCE_LIMIT")
    if runner is not None:
        return runner(body, timeout)
    process = None
    try:
        process = subprocess.Popen(command, cwd=BACKEND, env={
            "PYTHONHASHSEED": "0", "PYTHONNOUSERSITE": "1"},
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        output, _ = process.communicate(body, timeout=timeout)
        if process.returncode != 0 or len(output) > MAX_WORKER_OUTPUT_BYTES:
            return rejected("PDF_RESOURCE_LIMIT")
        value = json.loads(output)
        pages = tuple(ParsedPage(**page) for page in value["pages"])
        result = ParseResult(value["parser_version"], value["page_count"], pages,
                             value.get("issue_code"), value.get("issue_page"))
        if (result.parser_version != PDF_PARSER_VERSION or
            result.page_count is not None and (result.page_count < 1 or result.page_count > 100_000) or
            result.status == "ready" and (result.page_count is None or len(pages) != result.page_count or
                                           any(p.parse_quality not in ("ready", "empty") for p in pages)) or
            result.status == "rejected" and result.issue_code not in {
                "PDF_DAMAGED", "PDF_ENCRYPTED", "PDF_PAGE_LIMIT", "PDF_TEXT_LIMIT",
                "PDF_UNREADABLE_PAGE", "PDF_CONTENT_LIMIT", "PDF_RESOURCE_LIMIT"} or
            result.issue_page is not None and (result.page_count is None or result.issue_page < 1 or
                                               result.issue_page > result.page_count) or
            len(pages) > MAX_PAGES or sum(len(p.normalized_text) for p in pages) > MAX_DOCUMENT_CODEPOINTS or
            any(p.page_number != index or p.text_hash != text_hash(p.normalized_text)
                or p.normalized_text != normalize_text(p.normalized_text)
                or p.parse_quality not in ("ready", "empty", "unreadable", "failed")
                for index, p in enumerate(pages, 1))):
            return rejected("PDF_RESOURCE_LIMIT")
        return result
    except subprocess.TimeoutExpired:
        if process is not None:
            process.kill()
            try:
                process.communicate(timeout=5)
            except subprocess.TimeoutExpired:
                pass
        return rejected("PDF_TIMEOUT")
    except (OSError, ValueError, KeyError, TypeError, UnicodeError):
        if process is not None and process.poll() is None:
            process.kill()
            try:
                process.communicate(timeout=5)
            except subprocess.TimeoutExpired:
                pass
        return rejected("PARSER_UNAVAILABLE")
