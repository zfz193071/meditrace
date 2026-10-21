"""Isolated /api/v1 application; no legacy imports, DDL, model or payment calls."""

from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from . import CONTRACT_VERSION
from .config import Settings, load_settings
from .errors import ApiError, error_response, install_error_handlers, logger
from .schemas import Capabilities, ErrorCode, ErrorEnvelope, ReadinessResponse
from .identity.routes import auth_router
from .identity.service import DATABASE_FAILURES, configured_identity
from .identity.authorization import protect_request
from .documents import configured_documents
from .documents.routes import document_router
from .packets import Packets
from .packets.routes import packet_router
from starlette.concurrency import run_in_threadpool


def create_app(settings: Settings | None = None, *, identity=None, documents=None) -> FastAPI:
    config = settings if settings is not None else load_settings()
    app = FastAPI(
        title="MediTrace Referral Review API",
        version=CONTRACT_VERSION,
        description="Referral identity, private documents and packet revisions. Review, model and payment workflows are not complete yet.",
        servers=[{"url": "/api/v1"}],
        docs_url=None, redoc_url=None,
        responses={
            404: {"model": ErrorEnvelope},
            401: {"model": ErrorEnvelope},
            403: {"model": ErrorEnvelope},
            422: {"model": ErrorEnvelope},
            500: {"model": ErrorEnvelope},
            503: {"model": ErrorEnvelope},
        },
    )
    install_error_handlers(app)
    identity = identity if identity is not None else configured_identity(config)
    app.state.identity = identity
    app.state.documents = documents if documents is not None else configured_documents(config, identity)
    app.state.packets = Packets(identity) if identity is not None else None
    app.include_router(auth_router(identity))
    app.include_router(document_router())
    app.include_router(packet_router())

    @app.middleware("http")
    async def request_metadata(request: Request, call_next):
        request.state.request_id = uuid4()  # Never trust an arbitrary inbound logging identifier.
        try:
            await run_in_threadpool(protect_request, request)
            response = await call_next(request)
        except ApiError as exc:
            response = error_response(request, exc.code, current_revision=exc.current_revision)
        except DATABASE_FAILURES:
            response = error_response(request, ErrorCode.SERVICE_NOT_READY)
        except Exception:
            # Catch before ServerErrorMiddleware re-raises to the ASGI server,
            # where a provider exception could otherwise enter a traceback log.
            logger.error("referral_request_failed request_id=%s", request.state.request_id)
            response = error_response(request, ErrorCode.INTERNAL_ERROR)
        response.headers["X-Request-ID"] = str(request.state.request_id)
        response.headers["Cache-Control"] = "private, no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
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
