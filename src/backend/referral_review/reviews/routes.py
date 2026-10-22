"""Owner-only review API. Shared middleware applies session, origin and CSRF checks."""
from uuid import UUID
from fastapi import APIRouter, Header, Request
from ..errors import ApiError
from ..schemas import ErrorCode
from .contracts import (ConfirmInput, HandoffDraftInput, HandoffDraftResponse, ResolutionInput,
    ReviewEvent, ReviewHistory, SnapshotResponse, RunReviewState)


def review_router():
    router = APIRouter()

    def service(request):
        identity, reviews = request.app.state.identity, request.app.state.reviews
        if identity is None or reviews is None:
            raise ApiError(ErrorCode.AUTH_REQUIRED)
        return reviews, request.cookies.get(identity.session_cookie)

    @router.get("/runs/{run_id}/review", response_model=RunReviewState, operation_id="get_run_review_state")
    def get_run_review_state(request: Request, run_id: UUID):
        reviews, token = service(request)
        return reviews.state(token, run_id)

    @router.post("/runs/{run_id}/findings/{finding_id}/resolutions", response_model=ReviewEvent,
                 status_code=201, operation_id="resolve_finding")
    def resolve_finding(request: Request, run_id: UUID, finding_id: UUID, body: ResolutionInput,
                        idempotency_key: str = Header(...)):
        reviews, token = service(request)
        return reviews.resolve(token, run_id, finding_id, body, idempotency_key)

    @router.put("/packets/{packet_id}/handoff-draft", response_model=ReviewEvent, operation_id="save_handoff_draft")
    def save_handoff_draft(request: Request, packet_id: UUID, body: HandoffDraftInput, idempotency_key: str = Header(...)):
        reviews, token = service(request)
        return reviews.save_draft(token, packet_id, body, idempotency_key)

    @router.get("/packets/{packet_id}/handoff-draft", response_model=HandoffDraftResponse, operation_id="get_handoff_draft")
    def get_handoff_draft(request: Request, packet_id: UUID):
        reviews, token = service(request)
        return reviews.get_draft(token, packet_id)

    @router.post("/packets/{packet_id}/confirm", response_model=SnapshotResponse, status_code=201, operation_id="confirm_review")
    def confirm_review(request: Request, packet_id: UUID, body: ConfirmInput, idempotency_key: str = Header(...)):
        reviews, token = service(request)
        return reviews.confirm(token, packet_id, body, idempotency_key)

    @router.get("/packets/{packet_id}/snapshots/{snapshot_id}", response_model=SnapshotResponse, operation_id="get_review_snapshot")
    def get_review_snapshot(request: Request, packet_id: UUID, snapshot_id: UUID):
        reviews, token = service(request)
        return reviews.snapshot(token, packet_id, snapshot_id)

    @router.get("/packets/{packet_id}/review-history", response_model=ReviewHistory, operation_id="list_review_history")
    def list_review_history(request: Request, packet_id: UUID, cursor: str | None = None, limit: int = 20):
        reviews, token = service(request)
        return reviews.history(token, packet_id, cursor, limit)

    return router
