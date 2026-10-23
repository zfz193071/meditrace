"""Account deletion uses session + CSRF; maintenance uses only operator Bearer."""
import hmac

from fastapi import APIRouter, Header, Request, Response

from ..errors import ApiError
from ..schemas import Contract, ErrorCode
from pydantic import Field
from typing import Literal
from .service import Lifecycle


class AccountDeleteInput(Contract):
    confirmation: Literal["DELETE"]


class AccountDeleteResponse(Contract):
    state: Literal["cleanup_pending"] = "cleanup_pending"


class MaintenanceInput(Contract):
    limit: int = Field(200, ge=1, le=200)
    cursor: Literal["continue"] | None = None


class MaintenanceResponse(Contract):
    processed: int
    failed: int
    exhausted: int
    backlog: int
    cursor: Literal["continue"] | None


def lifecycle_router():
    router = APIRouter()

    def service(request):
        identity = request.app.state.identity
        if identity is None:
            raise ApiError(ErrorCode.SERVICE_NOT_READY)
        return Lifecycle(identity, request.app.state.documents, request.app.state.billing)

    @router.delete("/account", response_model=AccountDeleteResponse, status_code=202, operation_id="delete_account")
    def delete_account(request: Request, response: Response, body: AccountDeleteInput,
                       idempotency_key: str = Header(...)):
        lifecycle = service(request)
        identity = lifecycle.identity
        lifecycle.delete_account(request.cookies.get(identity.session_cookie), idempotency_key)
        response.delete_cookie(identity.session_cookie, path="/", secure=identity.secure_cookie,
                               httponly=True, samesite="lax")
        return AccountDeleteResponse()

    @router.post("/internal/maintenance", response_model=MaintenanceResponse, operation_id="run_maintenance")
    def maintenance(request: Request, body: MaintenanceInput = MaintenanceInput()):
        lifecycle = service(request)
        secret = lifecycle.identity.settings.maintenance_token
        supplied = request.headers.getlist("authorization")
        if not secret or len(supplied) != 1 or not hmac.compare_digest(
                supplied[0].encode(), ("Bearer " + secret.get_secret_value()).encode()):
            raise ApiError(ErrorCode.FORBIDDEN)
        return lifecycle.maintain(body.limit)

    return router
