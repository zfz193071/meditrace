"""Stable, non-sensitive HTTP error responses for the mounted referral application."""

import logging
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException

from .schemas import ErrorCode, ErrorDetail, ErrorEnvelope

logger = logging.getLogger("meditrace.referral")
ERRORS = {
    ErrorCode.MEMBERSHIP_REQUIRED: (403, "An active test membership is required."),
    ErrorCode.QUOTA_EXHAUSTED: (409, "Membership quota is exhausted."),
    ErrorCode.BUDGET_EXHAUSTED: (409, "AI budget is unavailable."),
    ErrorCode.RUN_ACTIVE: (409, "Concurrent execution capacity is exhausted."),
    ErrorCode.RATE_LIMITED: (429, "Request rate limit reached."),
    ErrorCode.USAGE_CONFLICT: (409, "Usage operation conflicts with its recorded state."),
    ErrorCode.AUTH_REQUIRED: (401, "Authentication required."),
    ErrorCode.FORBIDDEN: (403, "Access denied."),
    ErrorCode.NOT_FOUND: (404, "Resource not found."),
    ErrorCode.METHOD_NOT_ALLOWED: (405, "Method not allowed."),
    ErrorCode.SCHEMA_INVALID: (422, "Request does not match the required schema."),
    ErrorCode.REAL_AI_NOT_ALLOWED: (403, "Real AI execution is unavailable."),
    ErrorCode.SERVICE_NOT_READY: (503, "Service is not ready."),
    ErrorCode.INTERNAL_ERROR: (500, "An internal error occurred."),
    ErrorCode.OAUTH_FAILED: (400, "Sign-in could not be completed."),
    ErrorCode.FILE_UNSUPPORTED: (422, "Upload one text PDF or paste supported text."),
    ErrorCode.FILE_TOO_LARGE: (413, "Document exceeds the input limit."),
    ErrorCode.STORAGE_LIMIT: (409, "Storage capacity is exhausted."),
    ErrorCode.DOCUMENT_LIMIT: (409, "Document capacity is exhausted."),
    ErrorCode.STORAGE_UNAVAILABLE: (503, "Private storage is unavailable."),
    ErrorCode.IDEMPOTENCY_CONFLICT: (409, "Request key is in use or belongs to different input."),
    ErrorCode.PACKET_LIMIT: (409, "Packet capacity is exhausted."),
    ErrorCode.PACKET_INPUT_LIMIT: (409, "Combined packet input exceeds the limit."),
    ErrorCode.REVISION_CONFLICT: (409, "Packet revision changed; refresh before saving."),
    ErrorCode.DRAFT_CONFLICT: (409, "Saved draft changed; refresh before saving."),
}


class ApiError(Exception):
    def __init__(self, code: ErrorCode, *, current_revision: int | None = None):
        self.code = code
        self.current_revision = current_revision
        super().__init__(code.value)


def error_response(request: Request, code: ErrorCode, *, current_revision: int | None = None) -> JSONResponse:
    status, message = ERRORS[code]
    request_id = getattr(request.state, "request_id", uuid4())
    body = ErrorEnvelope(error=ErrorDetail(code=code, message=message,
        current_revision=current_revision), request_id=request_id)
    return JSONResponse(body.model_dump(mode="json", exclude_none=True), status_code=status, headers={
        "X-Request-ID": str(request_id), "Cache-Control": "private, no-store",
    })


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def domain_error(request: Request, exc: ApiError):
        return error_response(request, exc.code, current_revision=exc.current_revision)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, _exc: RequestValidationError):
        # Pydantic's default response contains rejected input; never echo document content.
        return error_response(request, ErrorCode.SCHEMA_INVALID)

    @app.exception_handler(HTTPException)
    async def http_error(request: Request, exc: HTTPException):
        code = next((code for code, (status, _) in ERRORS.items() if status == exc.status_code), ErrorCode.INTERNAL_ERROR)
        return error_response(request, code)

    @app.exception_handler(Exception)
    async def unexpected_error(request: Request, _exc: Exception):
        # No exception repr/traceback: provider failures can embed secrets or input text.
        logger.error("referral_request_failed request_id=%s", getattr(request.state, "request_id", "unknown"))
        return error_response(request, ErrorCode.INTERNAL_ERROR)
