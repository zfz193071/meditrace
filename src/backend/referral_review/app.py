"""Isolated /api/v1 application; no legacy imports, DDL, model or payment calls."""

from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from . import CONTRACT_VERSION
from .config import Settings, load_settings
from .errors import error_response, install_error_handlers, logger
from .schemas import Capabilities, ErrorCode, ErrorEnvelope, ReadinessResponse


def create_app(settings: Settings | None = None) -> FastAPI:
    config = settings if settings is not None else load_settings()
    app = FastAPI(
        title="MediTrace Referral Review API",
        version=CONTRACT_VERSION,
        description="MT-01 foundation. Business workflows are not implemented yet.",
        servers=[{"url": "/api/v1"}],
        docs_url=None, redoc_url=None,
        responses={
            404: {"model": ErrorEnvelope},
            422: {"model": ErrorEnvelope},
            500: {"model": ErrorEnvelope},
        },
    )
    install_error_handlers(app)

    @app.middleware("http")
    async def request_metadata(request: Request, call_next):
        request.state.request_id = uuid4()  # Never trust an arbitrary inbound logging identifier.
        try:
            response = await call_next(request)
        except Exception:
            # Catch before ServerErrorMiddleware re-raises to the ASGI server,
            # where a provider exception could otherwise enter a traceback log.
            logger.error("referral_request_failed request_id=%s", request.state.request_id)
            response = error_response(request, ErrorCode.INTERNAL_ERROR)
        response.headers["X-Request-ID"] = str(request.state.request_id)
        response.headers["Cache-Control"] = "private, no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response

    @app.get("/capabilities", response_model=Capabilities, operation_id="get_capabilities")
    def capabilities():
        return Capabilities(contract_version=CONTRACT_VERSION, mode=config.mode)

    @app.get("/readiness", response_model=ReadinessResponse, responses={503: {"model": ReadinessResponse}}, operation_id="get_readiness")
    def readiness():
        # MT-02/03/19 supply real checks. Never pretend an unimplemented schema is ready.
        body = ReadinessResponse(
            status="not_ready", schema_version=None, checklist_version=None,
            checks={"database": "not_checked", "migrations": "not_implemented", "checklist": "not_implemented"},
        )
        return JSONResponse(body.model_dump(mode="json"), status_code=503)

    return app
