"""Stripe test-only adapter. No provider payloads or credentials enter logs/storage."""
import hashlib
import hmac
import json
import re
import time
from contextvars import ContextVar
from urllib.parse import urlsplit

import httpx

from ..errors import ApiError
from ..schemas import ErrorCode

maintenance_deadline = ContextVar("stripe_maintenance_deadline", default=None)

EVENT_TYPES = {
    "checkout.session.completed", "checkout.session.async_payment_succeeded",
    "checkout.session.async_payment_failed", "checkout.session.expired",
    "charge.refunded", "charge.dispute.created", "charge.dispute.closed",
}


def rejected():
    return ApiError(ErrorCode.EVENT_REJECTED)


def identifier(value, prefix):
    if not isinstance(value, str) or not re.fullmatch(prefix + r"[A-Za-z0-9_]{1,180}", value):
        raise rejected()
    return value


def checkout_url(value):
    parsed = urlsplit(value or "")
    if (parsed.scheme != "https" or parsed.hostname != "checkout.stripe.com"
            or parsed.username or parsed.password or parsed.port not in (None, 443)):
        raise rejected()
    return value


def verify_event(raw, signature, secret, now):
    if len(raw) > 256_000 or not signature or len(signature) > 4096:
        raise rejected()
    try:
        parts = [part.split("=", 1) for part in signature.split(",")]
        timestamps = [value for key, value in parts if key == "t"]
        if len(timestamps) != 1 or abs(now.timestamp() - int(timestamps[0])) > 300:
            raise ValueError()
        expected = hmac.new(secret.encode(), timestamps[0].encode() + b"." + raw, hashlib.sha256).hexdigest()
        if not any(hmac.compare_digest(expected, value) for key, value in parts if key == "v1"):
            raise ValueError()
        event = json.loads(raw)
        if not isinstance(event, dict):
            raise ValueError()
        identifier(event["id"], "evt_")
        if event["livemode"] is not False or not isinstance(event["created"], int) or event["created"] > now.timestamp() + 300:
            raise ValueError()
        obj = event["data"]["object"]
        if not isinstance(obj, dict) or obj.get("livemode") is not False:
            raise ValueError()
        if event["type"] not in EVENT_TYPES:
            raise ValueError()
        prefix = "cs_test_" if event["type"].startswith("checkout.") else ("dp_" if "dispute" in event["type"] else "ch_")
        identifier(obj["id"], prefix)
        return event
    except (ValueError, TypeError, KeyError):
        raise rejected() from None


class StripeTest:
    def __init__(self, settings, *, transport=None):
        self.settings, self.transport = settings, transport
        if not settings.stripe_secret_key or not settings.stripe_secret_key.get_secret_value().startswith(("sk_test_", "rk_test_")):
            raise ApiError(ErrorCode.BILLING_DISABLED)

    def _request(self, method, path, *, data=None, params=None, key=None):
        deadline = maintenance_deadline.get()
        remaining = deadline - time.monotonic() if deadline is not None else 60
        if remaining <= 0:
            raise ApiError(ErrorCode.PAYMENT_PENDING)
        headers = {"Authorization": "Bearer " + self.settings.stripe_secret_key.get_secret_value()}
        if key:
            headers["Idempotency-Key"] = key
        try:
            with httpx.Client(transport=self.transport, timeout=min(15, remaining / 4), follow_redirects=False) as client:
                response = client.request(method, "https://api.stripe.com/v1/" + path,
                                          data=data, params=params, headers=headers)
                response.raise_for_status()
                result = response.json()
                if not isinstance(result, dict) or result.get("livemode") is True:
                    raise rejected()
                return result
        except (httpx.HTTPError, ValueError):
            raise ApiError(ErrorCode.PAYMENT_PENDING) from None

    def create(self, order, detail):
        price = self._request("GET", "prices/" + identifier(order["price_id"], "price_"))
        if (price.get("livemode") is not False or price.get("active") is not True
                or price.get("type") != "one_time" or price.get("unit_amount") != order["amount"]
                or price.get("currency") != order["currency"]):
            raise rejected()
        base = self.settings.site_origin + "/account/payment?order=" + str(order["id"])
        result = self._request("POST", "checkout/sessions", key="rr-order-" + str(order["id"]), data={
            "mode": "payment", "line_items[0][price]": order["price_id"], "line_items[0][quantity]": "1",
            "client_reference_id": str(order["id"]), "metadata[order_id]": str(order["id"]),
            "payment_intent_data[metadata][order_id]": str(order["id"]),
            "success_url": base, "cancel_url": base,
            "expires_at": str(int(detail["expires_at"].timestamp())),
        })
        identifier(result.get("id"), "cs_test_")
        checkout_url(result.get("url"))
        if result.get("livemode") is not False or result.get("client_reference_id") != str(order["id"]):
            raise rejected()
        return result

    def session(self, session_id):
        result = self._request("GET", "checkout/sessions/" + identifier(session_id, "cs_test_"),
            params={"expand[]": "payment_intent.latest_charge"})
        items = self._request("GET", "checkout/sessions/" + session_id + "/line_items", params={"limit": 2})
        if items.get("has_more") or len(items.get("data", [])) != 1:
            raise rejected()
        item = items["data"][0]
        price = item.get("price") or {}
        if item.get("quantity") != 1 or price.get("livemode") is not False:
            raise rejected()
        result["verified_price_id"] = price.get("id")
        return result

    def resolve(self, event_type, object_id):
        if event_type.startswith("checkout."):
            return self.session(object_id)
        if "dispute" in event_type:
            dispute = self._request("GET", "disputes/" + identifier(object_id, "dp_"))
            if dispute.get("livemode") is not False:
                raise rejected()
            object_id = dispute.get("charge")
        charge = self._request("GET", "charges/" + identifier(object_id, "ch_"))
        if charge.get("livemode") is not False:
            raise rejected()
        intent = identifier(charge.get("payment_intent"), "pi_")
        sessions = self._request("GET", "checkout/sessions", params={"payment_intent": intent, "limit": 2})
        if sessions.get("has_more") or len(sessions.get("data", [])) != 1:
            raise rejected()
        result = self.session(sessions["data"][0]["id"])
        if not isinstance(result.get("payment_intent"), dict) or result["payment_intent"].get("id") != intent:
            raise rejected()
        return result
