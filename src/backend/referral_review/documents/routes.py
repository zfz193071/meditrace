"""Bounded multipart/text intake; never accepts a remote URL or object key."""

import json
import re
import unicodedata
from urllib.parse import quote
from uuid import UUID

import anyio
from fastapi import APIRouter, Header, Request, Response
from pydantic import ValidationError
from starlette.concurrency import run_in_threadpool
from starlette.datastructures import UploadFile
from starlette.formparsers import MultiPartException, MultiPartParser

from ..errors import ApiError
from ..identity.service import DATABASE_FAILURES
from ..schemas import DocumentPageResponse, DocumentResponse, ErrorCode, ErrorEnvelope, TextDocumentInput
from .storage import MAX_BYTES, StorageUnavailable


def validate_filename(value, kind):
    value = unicodedata.normalize("NFC", value)
    if (not value.strip() or len(value) > 255 or value.startswith(".") or ".." in value
        or any(char in value for char in '/\\:%<>"|?*')
        or any(unicodedata.category(char).startswith("C") for char in value)
        or not value.lower().endswith(".pdf" if kind == "pdf" else ".txt")):
        raise ApiError(ErrorCode.FILE_UNSUPPORTED)
    return value


async def bounded_stream(request, maximum):
    lengths = request.headers.getlist("content-length")
    if len(lengths) > 1 or (lengths and not re.fullmatch(r"[0-9]{1,10}", lengths[0])):
        raise ApiError(ErrorCode.SCHEMA_INVALID)
    declared = int(lengths[0]) if lengths else None
    if declared is not None and declared > maximum:
        raise ApiError(ErrorCode.FILE_TOO_LARGE)
    received = 0
    async for chunk in request.stream():
        received += len(chunk)
        if received > maximum:
            raise ApiError(ErrorCode.FILE_TOO_LARGE)
        yield chunk
    if declared is not None and received != declared:
        raise ApiError(ErrorCode.SCHEMA_INVALID)


async def read_input(request, kind):
    if kind == "text":
        raw = bytearray()
        async for chunk in bounded_stream(request, 120_000 + 16_384):
            raw.extend(chunk)
        try:
            value = TextDocumentInput.model_validate(json.loads(raw.decode("utf-8")))
            if not value.text.strip() or any(unicodedata.category(c) == "Cs" or c == "\x00" for c in value.text):
                raise ValueError()
            body = value.text.encode("utf-8")
        except (ValidationError, ValueError, UnicodeError, RecursionError):
            raise ApiError(ErrorCode.FILE_UNSUPPORTED) from None
        return validate_filename(value.filename, kind), body
    # Parse only after a reservation exists. Bound actual receive bytes, not just
    # Content-Length or UploadFile.size. Small uploads remain in private memory.
    parser = MultiPartParser(request.headers, bounded_stream(request, MAX_BYTES + 16_384),
                             max_files=1, max_fields=0)
    parser.spool_max_size = MAX_BYTES + 16_384
    try:
        form = await parser.parse()
        try:
            entries = form.multi_items()
            if len(entries) != 1 or entries[0][0] != "file" or not isinstance(entries[0][1], UploadFile):
                raise ApiError(ErrorCode.FILE_UNSUPPORTED)
            file = entries[0][1]
            filename = validate_filename(file.filename or "", kind)
            if file.content_type != "application/pdf":
                raise ApiError(ErrorCode.FILE_UNSUPPORTED)
            body = await file.read(MAX_BYTES + 1)
            if len(body) > MAX_BYTES:
                raise ApiError(ErrorCode.FILE_TOO_LARGE)
            if not re.match(rb"%PDF-[12]\.[0-9][\r\n]", body):
                raise ApiError(ErrorCode.FILE_UNSUPPORTED)
            return filename, body
        finally:
            await form.close()
    except MultiPartException:
        raise ApiError(ErrorCode.FILE_UNSUPPORTED) from None
    finally:
        # Starlette closes on multipart errors; also close on custom size errors,
        # disconnects and cancellations while the parser is still receiving.
        for file in parser._files_to_close_on_error:
            file.close()


def document_router():
    router = APIRouter(prefix="/packets/{packet_id}/documents")

    def service(request):
        identity = request.app.state.identity
        if identity is None:
            raise ApiError(ErrorCode.AUTH_REQUIRED)
        if request.app.state.documents is None:
            raise ApiError(ErrorCode.STORAGE_UNAVAILABLE)
        return request.app.state.documents, request.cookies.get(identity.session_cookie)

    @router.post("", response_model=DocumentResponse, status_code=201, operation_id="upload_document",
        responses={409: {"model": ErrorEnvelope, "description": "Capacity or idempotency conflict"},
                   413: {"model": ErrorEnvelope, "description": "Input too large"}},
        openapi_extra={"requestBody": {"required": True, "content": {
            "application/json": {"schema": TextDocumentInput.model_json_schema()},
            "multipart/form-data": {"schema": {"type": "object", "required": ["file"],
                "additionalProperties": False, "properties": {"file": {"type": "string", "format": "binary"}}}},
        }}})
    async def upload_document(request: Request, packet_id: UUID, idempotency_key: str = Header(...)):
        documents, token = service(request)
        media = request.headers.get("content-type", "").split(";", 1)[0].strip().lower()
        if media not in ("application/json", "multipart/form-data") or request.headers.get("content-encoding", "identity") != "identity":
            raise ApiError(ErrorCode.FILE_UNSUPPORTED)
        kind = "text" if media == "application/json" else "pdf"
        upload = await run_in_threadpool(documents.begin, token, packet_id, kind, idempotency_key)
        attempted = False
        try:
            with anyio.fail_after(60):
                filename, body = await read_input(request, kind)
            attempted = True
            return await run_in_threadpool(documents.finish, token, upload, filename, kind, body)
        except BaseException as exc:
            # Shield compensation on a disconnected/cancelled request. If DB is
            # down the durable intent is enough for subsequent reconciliation.
            with anyio.CancelScope(shield=True):
                await run_in_threadpool(documents.abort, upload, object_attempted=attempted)
            if isinstance(exc, (StorageUnavailable, *DATABASE_FAILURES, TimeoutError)):
                raise ApiError(ErrorCode.STORAGE_UNAVAILABLE) from None
            raise

    @router.get("/{document_id}", response_model=DocumentResponse, operation_id="get_document")
    def get_document(request: Request, packet_id: UUID, document_id: UUID):
        documents, token = service(request)
        return documents.get(token, packet_id, document_id)

    @router.get("/{document_id}/pages/{page_number}", response_model=DocumentPageResponse,
                operation_id="get_document_page")
    def get_document_page(request: Request, packet_id: UUID, document_id: UUID, page_number: int):
        documents, token = service(request)
        if page_number < 1:
            raise ApiError(ErrorCode.NOT_FOUND)
        return documents.get_page(token, packet_id, document_id, page_number)

    @router.get("/{document_id}/original", response_class=Response, operation_id="download_document",
        responses={200: {"content": {"application/pdf": {}, "text/plain": {}}}})
    def download_document(request: Request, packet_id: UUID, document_id: UUID):
        documents, token = service(request)
        try:
            document, body = documents.read_original(token, packet_id, document_id)
        except StorageUnavailable:
            raise ApiError(ErrorCode.STORAGE_UNAVAILABLE) from None
        return Response(body, media_type="application/pdf" if document.kind == "pdf" else "text/plain; charset=utf-8",
            headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(document.filename, safe='')}",
                     "Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff",
                     "Content-Security-Policy": "sandbox"})

    return router
