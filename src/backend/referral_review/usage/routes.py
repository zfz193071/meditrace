from fastapi import APIRouter, Request

from ..errors import ApiError
from ..schemas import ErrorCode, MembershipResponse


def usage_router():
    router = APIRouter()

    @router.get("/membership", response_model=MembershipResponse, operation_id="get_membership")
    def membership(request: Request):
        identity, usage = request.app.state.identity, request.app.state.usage
        if identity is None or usage is None:
            raise ApiError(ErrorCode.AUTH_REQUIRED)
        return usage.membership(request.cookies.get(identity.session_cookie))

    return router
