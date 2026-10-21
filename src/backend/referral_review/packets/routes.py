"""Owner-only packet HTTP interface; every write is CSRF and key protected."""

from uuid import UUID

from fastapi import APIRouter, Header, Request

from ..errors import ApiError
from ..schemas import (CreatePacketInput, ErrorCode, PacketDeleteResponse,
    PacketDetailResponse, PacketDraftResponse, PacketListResponse, PacketResponse,
    RevisionResponse, SavePacketDraftInput, SaveRevisionInput, UpdatePacketInput)


def packet_router():
    router = APIRouter(prefix="/packets")

    def service(request):
        identity = request.app.state.identity
        packets = request.app.state.packets
        if identity is None or packets is None:
            raise ApiError(ErrorCode.AUTH_REQUIRED)
        return packets, request.cookies.get(identity.session_cookie)

    @router.post("", response_model=PacketResponse, status_code=201, operation_id="create_packet")
    def create_packet(request: Request, body: CreatePacketInput, idempotency_key: str = Header(...)):
        packets, token = service(request)
        return packets.create(token, body.title, idempotency_key)

    @router.get("", response_model=PacketListResponse, operation_id="list_packets")
    def list_packets(request: Request, cursor: str | None = None, limit: int = 20):
        packets, token = service(request)
        return packets.list(token, cursor, limit)

    @router.get("/{packet_id}", response_model=PacketDetailResponse, operation_id="get_packet")
    def get_packet(request: Request, packet_id: UUID):
        packets, token = service(request)
        return packets.get(token, packet_id)

    @router.patch("/{packet_id}", response_model=PacketResponse, operation_id="update_packet")
    def update_packet(request: Request, packet_id: UUID, body: UpdatePacketInput,
                      idempotency_key: str = Header(...)):
        packets, token = service(request)
        return packets.rename(token, packet_id, body.title, idempotency_key)

    @router.delete("/{packet_id}", response_model=PacketDeleteResponse,
                   status_code=202, operation_id="delete_packet")
    def delete_packet(request: Request, packet_id: UUID, idempotency_key: str = Header(...)):
        packets, token = service(request)
        return packets.delete(token, packet_id, idempotency_key)

    @router.get("/{packet_id}/draft", response_model=PacketDraftResponse,
                operation_id="get_packet_draft")
    def get_packet_draft(request: Request, packet_id: UUID):
        packets, token = service(request)
        return packets.get_draft(token, packet_id)

    @router.put("/{packet_id}/draft", response_model=PacketDraftResponse,
                operation_id="save_packet_draft")
    def save_packet_draft(request: Request, packet_id: UUID, body: SavePacketDraftInput,
                          idempotency_key: str = Header(...)):
        packets, token = service(request)
        return packets.save_draft(token, packet_id, body, idempotency_key)

    @router.post("/{packet_id}/revisions", response_model=RevisionResponse,
                 status_code=201, operation_id="save_packet_revision")
    def save_packet_revision(request: Request, packet_id: UUID, body: SaveRevisionInput,
                             idempotency_key: str = Header(...)):
        packets, token = service(request)
        return packets.save_revision(token, packet_id, body, idempotency_key)

    @router.get("/{packet_id}/revisions/{revision_number}", response_model=RevisionResponse,
                operation_id="get_packet_revision")
    def get_packet_revision(request: Request, packet_id: UUID, revision_number: int):
        packets, token = service(request)
        if revision_number < 1:
            raise ApiError(ErrorCode.NOT_FOUND)
        return packets.get_revision(token, packet_id, revision_number)

    return router
