"""Explicit execution only. GET is read-only and never reconciles or dispatches."""
from uuid import UUID
from fastapi import APIRouter, Header, Request, Response
from starlette.concurrency import run_in_threadpool

from ..errors import ApiError
from ..schemas import CreateRunInput, ErrorCode, RunResponse


def run_router():
    router = APIRouter()

    def service(request):
        identity, runs = request.app.state.identity, request.app.state.runs
        if identity is None or runs is None:
            raise ApiError(ErrorCode.AUTH_REQUIRED)
        return runs, request.cookies.get(identity.session_cookie)

    @router.post("/packets/{packet_id}/runs", response_model=RunResponse, status_code=201, operation_id="create_run")
    def create(request: Request, packet_id: UUID, body: CreateRunInput, idempotency_key: str = Header(...)):
        runs, token = service(request)
        return runs.create(token, packet_id, body, idempotency_key)

    @router.get("/runs/{run_id}", response_model=RunResponse, operation_id="get_run")
    def get(request: Request, run_id: UUID):
        runs, token = service(request)
        return runs.get(token, run_id)

    @router.post("/runs/{run_id}/execute", response_model=RunResponse, responses={202: {"model": RunResponse}}, operation_id="execute_run")
    async def execute(request: Request, response: Response, run_id: UUID, idempotency_key: str = Header(...)):
        runs, token = service(request)
        await run_in_threadpool(runs.bind_operation, token, run_id, "execute", idempotency_key)
        result = await runs.execute(token, run_id)
        if result.state == "running":
            response.status_code = 202
        return result

    @router.post("/runs/{run_id}/cancel", response_model=RunResponse, operation_id="cancel_run")
    def cancel(request: Request, run_id: UUID, idempotency_key: str = Header(...)):
        runs, token = service(request)
        runs.bind_operation(token, run_id, "cancel", idempotency_key)
        return runs.cancel(token, run_id)

    @router.post("/runs/{run_id}/reconcile", response_model=RunResponse, operation_id="reconcile_run")
    def reconcile(request: Request, run_id: UUID, idempotency_key: str = Header(...)):
        runs, token = service(request)
        runs.bind_operation(token, run_id, "reconcile", idempotency_key)
        return runs.reconcile(token, run_id)

    return router
