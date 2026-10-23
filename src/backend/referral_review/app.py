"""Isolated /api/v1 application; no legacy imports, DDL, model or payment calls."""

from uuid import uuid4
import time

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from . import CONTRACT_VERSION
from .config import ConfigurationError, Settings, load_settings
from .errors import ApiError, error_response, install_error_handlers, logger
from .schemas import Capabilities, ErrorCode, ErrorEnvelope, ReadinessResponse
from .identity.routes import auth_router
from .identity.service import DATABASE_FAILURES, configured_identity
from .identity.authorization import protect_request
from .documents import configured_documents
from .documents.routes import document_router
from .handoff import Handoff
from .handoff.routes import handoff_router
from .reviews import Reviews
from .reviews.routes import review_router
from .runs import Runs
from .runs.routes import run_router
from .billing import Billing, configured as billing_configured
from .billing.routes import billing_router
from .usage import Usage
from .usage.routes import usage_router
from .packets import Packets
from .packets.routes import packet_router
from .lifecycle.routes import lifecycle_router
from .operations.routes import operations_router
from .operations.readiness import probe
from .operations import telemetry
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
    app.state.billing = Billing(identity) if identity is not None and billing_configured(config) else None
    app.include_router(billing_router())
    app.state.usage = Usage(identity) if identity is not None else None
    app.state.runs = Runs(identity) if identity is not None else None
    app.state.reviews = Reviews(identity) if identity is not None else None
    app.state.handoff = Handoff(identity) if identity is not None else None
    app.include_router(handoff_router())
    app.include_router(review_router())
    app.include_router(run_router())
    app.include_router(usage_router())
    app.include_router(auth_router(identity))
    app.include_router(document_router())
    app.include_router(packet_router())
    app.include_router(lifecycle_router())
    app.include_router(operations_router())

    @app.middleware("http")
    async def request_metadata(request: Request, call_next):
        request.state.request_id = uuid4()  # Never trust an arbitrary inbound logging identifier.
        context = telemetry.request_id.set(request.state.request_id)
        started = time.monotonic()
        try:
            await run_in_threadpool(protect_request, request)
            response = await call_next(request)
        except ApiError as exc:
            response = error_response(request, exc.code, current_revision=exc.current_revision, current_review_version=exc.current_review_version)
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
        telemetry.emit("request", status=response.status_code,
            error_code=getattr(request.state, "error_code", None),
            duration_ms=int((time.monotonic() - started) * 1000))
        telemetry.request_id.reset(context)
        return response

    @app.get("/capabilities", response_model=Capabilities, operation_id="get_capabilities")
    def capabilities():
        real_configured = False
        if app.state.identity is not None:
            try:
                config.require_real_ai_configuration()
                real_configured = True
            except ConfigurationError:
                pass
        return Capabilities(contract_version=CONTRACT_VERSION, mode=config.mode,
            real_ai_execution_available=real_configured,
            payments_available=app.state.billing is not None,
            workspace_available=app.state.identity is not None and config.mode != "bundled_demo",
            sandbox_execution_available=app.state.runs is not None and config.mode != "bundled_demo")

    @app.get("/readiness", response_model=ReadinessResponse, responses={503: {"model": ReadinessResponse}}, operation_id="get_readiness")
    def readiness():
        body = probe(config, app.state.identity)
        return JSONResponse(body.model_dump(mode="json"), status_code=200 if body.status == "ready" else 503)

    return app
