"""One dispatch, no retries. No provider body, source text or credentials in errors/logs."""
import asyncio
from dataclasses import dataclass
import json
from typing import Protocol

import httpx
from pydantic import SecretStr, ValidationError

from .contracts import TokenUsage


@dataclass(frozen=True)
class ProviderReply:
    content: str
    model_reported: str | None
    request_id: str | None
    usage: TokenUsage | None


class ExtractionError(Exception):
    def __init__(self, code, *, reply=None):
        self.code = code
        # Preserve billing metadata even if content is invalid; never attach source content.
        self.usage = reply.usage if reply else None
        self.model_reported = reply.model_reported if reply else None
        self.provider_request_id = reply.request_id if reply else None
        super().__init__(code)


class ModelAdapter(Protocol):
    mode: str

    async def complete(self, request: dict) -> ProviderReply: ...


class DeepSeekAdapter:
    mode = "real"

    def __init__(self, api_key: SecretStr, *, transport=None):
        self._key = api_key
        self._transport = transport

    async def complete(self, request):
        try:
            async with asyncio.timeout(120):
                async with httpx.AsyncClient(transport=self._transport, timeout=120,
                                            follow_redirects=False, trust_env=False) as client:
                    async with client.stream("POST", "https://api.deepseek.com/chat/completions",
                        json=request, headers={"Authorization": "Bearer " + self._key.get_secret_value()}) as response:
                        if response.status_code != 200:
                            raise ExtractionError("MODEL_UNAVAILABLE")
                        body = bytearray()
                        async for chunk in response.aiter_bytes():
                            body.extend(chunk)
                            if len(body) > 256_000:
                                raise ExtractionError("MODEL_INVALID_OUTPUT")
                        data = json.loads(body)
            usage = None
            if data.get("usage") is not None:
                try:
                    usage = TokenUsage.model_validate(data["usage"])
                except ValidationError:
                    pass  # Unknown usage must retain the upper-bound reservation, never become zero.
            reported, request_id = data.get("model"), data.get("id")
            if not isinstance(reported, str) or not reported or not isinstance(request_id, str) or not request_id:
                raise ExtractionError("MODEL_INVALID_OUTPUT")
            reply = ProviderReply("", reported, request_id, usage)
            choices = data["choices"]
            if not isinstance(choices, list) or len(choices) != 1:
                raise ExtractionError("MODEL_INVALID_OUTPUT", reply=reply)
            choice = choices[0]
            if choice["finish_reason"] == "length":
                raise ExtractionError("MODEL_TRUNCATED", reply=reply)
            message = choice["message"]
            if (choice["finish_reason"] != "stop" or message.get("tool_calls")
                or message.get("role") != "assistant" or not isinstance(message.get("content"), str)):
                raise ExtractionError("MODEL_INVALID_OUTPUT", reply=reply)
            return ProviderReply(message["content"], reported, request_id, usage)
        except ExtractionError:
            raise
        except (TimeoutError, httpx.TimeoutException):
            raise ExtractionError("MODEL_TIMEOUT") from None
        except httpx.HTTPError:
            raise ExtractionError("MODEL_UNAVAILABLE") from None
        except (ValueError, KeyError, TypeError, AttributeError, RecursionError):
            raise ExtractionError("MODEL_INVALID_OUTPUT") from None


class FakeAdapter:
    """Explicit supplied synthetic output, not a heuristic pretending to extract facts."""
    mode = "fake"

    def __init__(self, output, *, scenario="normal"):
        self.output = output
        self.scenario = scenario
        self.calls = 0

    async def complete(self, request):
        self.calls += 1
        reply = ProviderReply(json.dumps(self.output), "fake-extraction-v1", "fake-request",
                              None if self.scenario == "usage_missing" else TokenUsage(
                                  prompt_tokens=10, completion_tokens=10, total_tokens=20))
        if self.scenario in ("timeout", "truncated"):
            raise ExtractionError({"timeout": "MODEL_TIMEOUT", "truncated": "MODEL_TRUNCATED"}[self.scenario], reply=reply)
        if self.scenario == "invalid_json":
            return ProviderReply("{", reply.model_reported, reply.request_id, reply.usage)
        if self.scenario == "false_quote":
            output = json.loads(reply.content)
            for fact in output["facts"]:
                for source in fact["sources"]:
                    source["quote"] = "fabricated source quote"
            return ProviderReply(json.dumps(output), reply.model_reported, reply.request_id, reply.usage)
        if self.scenario not in ("normal", "usage_missing"):
            raise ValueError("Unknown fake scenario")
        return reply
