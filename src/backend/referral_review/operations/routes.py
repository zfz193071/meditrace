"""Exact operator route, authenticated independently of browser sessions/CSRF."""
import hmac
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Request
from pydantic import Field

from ..errors import ApiError
from ..schemas import Contract, ErrorCode
from .service import Operations
from .contracts import OperationsStatus


def require_operator(request):
    identity = request.app.state.identity
    secret = identity.settings.maintenance_token if identity else None
    supplied = request.headers.getlist("authorization")
    if not secret or len(supplied) != 1 or not hmac.compare_digest(
            supplied[0].encode(), ("Bearer " + secret.get_secret_value()).encode()):
        raise ApiError(ErrorCode.FORBIDDEN)
    # Credentials and operation bodies must never travel in a query string.
    if any(key not in {"run_id", "request_id"} for key in request.query_params):
        raise ApiError(ErrorCode.SCHEMA_INVALID)
    return identity


class Reconcile(Contract):
    action: Literal["reconcile"]
    run_id: UUID
    apply: Literal[True]


class RetryPayment(Contract):
    action: Literal["retry_payment"]
    event_id: str = Field(pattern=r"^evt_[A-Za-z0-9_]{1,180}$")
    apply: Literal[True]


class RetryCleanup(Contract):
    action: Literal["retry_cleanup"]
    job_id: UUID
    retry_exhausted: bool = False
    apply: Literal[True]


def operations_router():
    router = APIRouter()

    def service(request):
        return Operations(require_operator(request), request.app.state.documents, request.app.state.billing)

    @router.get("/internal/operations", response_model=OperationsStatus, operation_id="query_operations")
    def status(request: Request, run_id: UUID | None = None, request_id: UUID | None = None):
        return service(request).status(run_id=run_id, request_id=request_id)

    @router.post("/internal/operations", response_model=OperationsStatus, operation_id="apply_operation")
    def apply(request: Request, body: Annotated[Reconcile | RetryPayment | RetryCleanup, Field(discriminator="action")]):
        ops = service(request)
        if body.action == "reconcile":
            return ops.reconcile(body.run_id)
        if body.action == "retry_payment":
            return ops.retry_payment(body.event_id)
        return ops.retry_cleanup(body.job_id, retry_exhausted=body.retry_exhausted)

    return router
