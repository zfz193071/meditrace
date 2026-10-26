from fastapi import APIRouter, Request, Response
from fastapi.responses import RedirectResponse

from ..errors import ApiError
from ..schemas import ErrorCode, SessionResponse
from .github import ISSUER
from .service import DATABASE_FAILURES


def auth_router(identity=None):
    router = APIRouter(prefix="/auth")

    @router.get("/session", response_model=SessionResponse, operation_id="get_session")
    def session(request: Request):
        if identity is None:
            return SessionResponse()
        try:
            return identity.session(request.cookies.get(identity.session_cookie))
        except DATABASE_FAILURES:
            raise ApiError(ErrorCode.SERVICE_NOT_READY) from None

    @router.get("/github/start", status_code=302, response_class=RedirectResponse, operation_id="start_github_login")
    def start(request: Request, return_path: str = "/workspace"):
        if identity is None:
            raise ApiError(ErrorCode.SERVICE_NOT_READY)
        try:
            login = identity.start(return_path)
        except DATABASE_FAILURES:
            raise ApiError(ErrorCode.SERVICE_NOT_READY) from None
        response = RedirectResponse(login.url, status_code=302)
        response.set_cookie(identity.nonce_cookie, login.nonce, max_age=600,
            secure=identity.secure_cookie, httponly=True, samesite="lax", path="/")
        response.headers["Referrer-Policy"] = "no-referrer"
        return response

    @router.get("/github/callback", status_code=303, response_class=RedirectResponse, operation_id="complete_github_login")
    def callback(request: Request):
        if identity is None:
            raise ApiError(ErrorCode.SERVICE_NOT_READY)
        try:
            query = request.query_params
            if any(len(query.getlist(k)) > 1 for k in query) or set(query) - {"code", "state", "iss", "error", "error_description", "error_uri"}:
                raise ApiError(ErrorCode.OAUTH_FAILED)
            # RFC 9207: compare the decoded issuer exactly, before exchanging
            # any code. This GitHub-only client also accepts legacy responses
            # without iss; it never discovers endpoints from response input.
            if "iss" in query and query["iss"] != ISSUER:
                raise ApiError(ErrorCode.OAUTH_FAILED)
            login = identity.complete(state=query.get("state", ""),
                nonce=request.cookies.get(identity.nonce_cookie, ""),
                code=query.get("code"), denied="error" in query,
                old_token=request.cookies.get(identity.session_cookie))
            response = RedirectResponse(login.return_path, status_code=303)
            response.set_cookie(identity.session_cookie, login.token, max_age=7 * 24 * 3600,
                secure=identity.secure_cookie, httponly=True, samesite="lax", path="/")
        except ApiError:
            # Only an allowlisted error marker reaches the UI, never provider details.
            response = RedirectResponse("/login?error=oauth_failed", status_code=303)
        except DATABASE_FAILURES:
            response = RedirectResponse("/login?error=service_unavailable", status_code=303)
        response.delete_cookie(identity.nonce_cookie, path="/", secure=identity.secure_cookie,
                               httponly=True, samesite="lax")
        response.headers["Referrer-Policy"] = "no-referrer"
        return response

    @router.post("/logout", status_code=204, operation_id="logout_session")
    def logout(request: Request):
        if identity is None:
            raise ApiError(ErrorCode.AUTH_REQUIRED)
        try:
            identity.require_mutation(request)
            identity.logout(request.cookies[identity.session_cookie])
        except DATABASE_FAILURES:
            raise ApiError(ErrorCode.SERVICE_NOT_READY) from None
        response = Response(status_code=204)
        response.delete_cookie(identity.session_cookie, path="/", secure=identity.secure_cookie,
                               httponly=True, samesite="lax")
        return response

    return router
