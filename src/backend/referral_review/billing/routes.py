"""Exact webhook and maintenance authentication; no blanket public path exemption."""
import hmac
from uuid import UUID

from fastapi import APIRouter, Header, Request
from starlette.concurrency import run_in_threadpool

from ..errors import ApiError
from ..schemas import BillingEventResponse, CheckoutInput, ErrorCode, OrderResponse


def billing_router():
    router = APIRouter()

    def service(request):
        billing = request.app.state.billing
        if billing is None:
            raise ApiError(ErrorCode.BILLING_DISABLED)
        return billing

    @router.post("/billing/checkout", response_model=OrderResponse, operation_id="create_checkout")
    def create_checkout(request: Request, body: CheckoutInput, idempotency_key: str = Header(...)):
        billing = service(request)
        return billing.create_checkout(request.cookies.get(billing.identity.session_cookie), body.return_path, idempotency_key)

    @router.get("/billing/orders/{order_id}", response_model=OrderResponse, operation_id="get_order")
    def get_order(request: Request, order_id: UUID):
        billing = service(request)
        return billing.get(request.cookies.get(billing.identity.session_cookie), order_id)

    @router.post("/billing/webhook", response_model=BillingEventResponse, operation_id="billing_webhook")
    async def webhook(request: Request):
        billing = service(request)
        raw = bytearray()
        async for chunk in request.stream():
            raw.extend(chunk)
            if len(raw) > 256_000:
                raise ApiError(ErrorCode.EVENT_REJECTED)
        signatures = request.headers.getlist("stripe-signature")
        if len(signatures) != 1:
            raise ApiError(ErrorCode.EVENT_REJECTED)
        await run_in_threadpool(billing.receive, bytes(raw), signatures[0])
        return BillingEventResponse()

    @router.post("/internal/maintenance", operation_id="run_maintenance")
    def maintenance(request: Request):
        billing = service(request)
        secret = billing.settings.maintenance_token
        supplied = request.headers.getlist("authorization")
        if not secret or len(supplied) != 1 or not hmac.compare_digest(
                supplied[0].encode(), ("Bearer " + secret.get_secret_value()).encode()):
            raise ApiError(ErrorCode.FORBIDDEN)
        return {"billing": billing.recover()}

    return router
