"""Shared authorization Interface for subsequent packet Modules."""

from uuid import UUID

from fastapi import Request
from starlette.routing import Match

from ..errors import ApiError
from ..schemas import ErrorCode
from .service import DATABASE_FAILURES


def require_owner(request: Request, connection, packet_id: UUID):
    identity = request.app.state.identity
    if identity is None:
        raise ApiError(ErrorCode.AUTH_REQUIRED)
    try:
        return identity.require_owner(connection, request.cookies.get(identity.session_cookie), packet_id)
    except DATABASE_FAILURES:
        raise ApiError(ErrorCode.SERVICE_NOT_READY) from None


def protect_request(request: Request):
    """Default policy for registered routes; unknown paths keep normal 404/405.

    There are deliberately NO path-prefix exemptions. MT-17/18 must add explicit
    signature/maintenance authentication when their dedicated routes are built.
    OAuth uses GET + state/nonce/PKCE, not a blanket /auth/* exemption.
    """
    route = next((r for r in request.app.routes if r.matches(request.scope)[0] == Match.FULL), None)
    if route is None:
        return
    identity = request.app.state.identity
    origin = request.headers.getlist("origin")
    # Included routers need not expose .path. Normalize the ASGI mount prefix.
    path = request.scope["path"]
    root = request.scope.get("root_path", "")
    if root and path.startswith(root + "/"):
        path = path[len(root):]
    if path == "/internal/operations" and request.method in {"GET", "POST"}:
        from ..operations.routes import require_operator
        require_operator(request)
        return
    # These exact POST routes authenticate raw signatures / operator bearer in their handlers.
    if request.method == "POST" and path in {"/billing/webhook", "/internal/maintenance"}:
        return
    if (path not in {"/capabilities", "/readiness", "/auth/github/callback"}
        and origin and (identity is None or origin != [identity.settings.site_origin])):
        raise ApiError(ErrorCode.FORBIDDEN)
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        if identity is None:
            raise ApiError(ErrorCode.AUTH_REQUIRED)
        identity.require_mutation(request)
