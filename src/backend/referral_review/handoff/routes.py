from typing import Literal
from uuid import UUID
from fastapi import APIRouter, Request, Response
from ..errors import ApiError
from ..schemas import ErrorCode
from .contracts import HandoffView


def handoff_router():
    router = APIRouter()

    def service(request):
        identity, handoff = request.app.state.identity, request.app.state.handoff
        if identity is None or handoff is None:
            raise ApiError(ErrorCode.AUTH_REQUIRED)
        return handoff, request.cookies.get(identity.session_cookie)

    @router.get("/packets/{packet_id}/snapshots/{snapshot_id}/handoff", response_model=HandoffView, operation_id="get_handoff")
    def get_handoff(request: Request, packet_id: UUID, snapshot_id: UUID):
        handoff, token = service(request)
        return handoff.get(token, packet_id, snapshot_id)

    @router.get("/packets/{packet_id}/snapshots/{snapshot_id}/export", response_class=Response, operation_id="export_handoff",
        responses={200: {"content": {"application/pdf": {"schema": {"type": "string", "format": "binary"}},
                                     "text/plain": {"schema": {"type": "string"}}}}})
    def export_handoff(request: Request, packet_id: UUID, snapshot_id: UUID, format: Literal["pdf", "txt"]):
        handoff, token = service(request)
        data = handoff.export(token, packet_id, snapshot_id, format)
        return Response(data, media_type="application/pdf" if format == "pdf" else "text/plain; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="referral-{snapshot_id}.{format}"',
                "Cache-Control": "private, no-store", "Content-Security-Policy": "sandbox"})

    return router
