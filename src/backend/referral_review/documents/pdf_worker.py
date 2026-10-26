"""Child process for pypdf only. Never import this in the web process."""

import json
import os
import platform
import resource
import sys

from .parser import (MAX_CONTENT_STREAM_BYTES, MAX_DOCUMENT_CODEPOINTS,
                     MAX_PAGE_CODEPOINTS, MAX_PAGES, PDF_PARSER_VERSION)
from .text_rules import normalize_text, text_hash

VERSION = PDF_PARSER_VERSION


def _limits():
    # CPU and memory limits constrain decompression/extraction before a child can
    # monopolize a server process. macOS may refuse RLIMIT_AS.
    resource.setrlimit(resource.RLIMIT_CPU, (18, 19))
    address = 512 * 1024 * 1024
    try:
        resource.setrlimit(resource.RLIMIT_AS, (address, address))
    except (ValueError, OSError):
        # macOS can reject RLIMIT_AS even for the current child. The page,
        # decoder, output, CPU and wall-clock limits remain mandatory there.
        if platform.system() != "Darwin":
            raise


def _configure_pypdf():
    from pypdf import Configuration

    for name in ("zlib_maximum_output_length", "lzw_maximum_output_length",
                 "run_length_maximum_output_length", "jbig2_maximum_output_length",
                 "brotli_maximum_output_length", "array_based_stream_maximum_output_length",
                 "image_maximum_buffer_size", "maximum_declared_stream_length"):
        setattr(Configuration, name, 2_000_000)
    Configuration.stream_decoding_work_maximum_length = 4_000_000
    Configuration.array_maximum_element_count = 10_000
    Configuration.dictionary_maximum_element_count = 10_000
    Configuration.page_tree_maximum_depth = 32
    Configuration.xform_maximum_invocations_per_extraction = 100


def _page(number, text, quality):
    normalized = normalize_text(text)
    return {"page_number": number, "normalized_text": normalized,
            "text_hash": text_hash(normalized), "parse_quality": quality}


def _result(count=None, pages=None, code=None, issue_page=None):
    return {"parser_version": VERSION, "page_count": count, "pages": pages or [],
            "issue_code": code, "issue_page": issue_page}


def parse(body):
    from io import BytesIO
    from pypdf import PdfReader

    if len(body) > 2 * 1024 * 1024 or not body.startswith(b"%PDF-"):
        return _result(code="PDF_DAMAGED")
    try:
        reader = PdfReader(BytesIO(body), strict=True)
        if reader.is_encrypted:
            return _result(code="PDF_ENCRYPTED")
        count = len(reader.pages)
        if count == 0:
            return _result(code="PDF_DAMAGED")
        if count > MAX_PAGES:
            return _result(count, code="PDF_PAGE_LIMIT")
    except Exception:
        return _result(code="PDF_DAMAGED")
    pages = []
    total_codepoints = 0
    issue_code = issue_page = None
    for index in range(1, count + 1):
        try:
            page = reader.pages[index - 1]
            contents = page.get_contents()
            content = contents.get_data() if contents is not None else b""
            if len(content) > MAX_CONTENT_STREAM_BYTES:
                raise ValueError("content stream limit")
            # Accessing image metadata can decode an image; pypdf and process
            # limits still apply. Any image on the page is conservatively unsafe
            # for automatic review, including mixed image + extractable text.
            has_image = len(page.images) > 0
            text = normalize_text(page.extract_text() or "")
            total_codepoints += len(text)
            if len(text) > MAX_PAGE_CODEPOINTS or total_codepoints > MAX_DOCUMENT_CODEPOINTS:
                issue_code, issue_page = "PDF_TEXT_LIMIT", index
                pages.append(_page(index, "", "failed"))
                break
            quality = "unreadable" if has_image else "ready" if text.strip() else "unreadable" if content.strip() else "empty"
            pages.append(_page(index, text, quality))
            if quality == "unreadable" and issue_code is None:
                issue_code, issue_page = "PDF_UNREADABLE_PAGE", index
        except (Exception, MemoryError):
            issue_code, issue_page = "PDF_CONTENT_LIMIT", index
            pages.append(_page(index, "", "failed"))
            break
    if len(pages) < count:
        pages.extend(_page(index, "", "failed") for index in range(len(pages) + 1, count + 1))
    return _result(count, pages, issue_code, issue_page)


def main():
    try:
        _configure_pypdf()
        _limits()
        body = sys.stdin.buffer.read(2 * 1024 * 1024 + 1)
        result = parse(body)
        encoded = json.dumps(result, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        if len(encoded) > 200_000:
            result = _result(code="PDF_RESOURCE_LIMIT")
            encoded = json.dumps(result).encode()
        while encoded:
            encoded = encoded[os.write(1, encoded):]
    except BaseException:
        os.write(1, json.dumps(_result(code="PDF_RESOURCE_LIMIT")).encode())


if __name__ == "__main__":
    main()
