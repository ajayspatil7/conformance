"""Vercel AI Gateway client that pins exactly one provider.

Pinning: `providerOptions.gateway.only = [slug]` restricts routing *and fallbacks* to that provider
(verified 2026-10-03 at
https://vercel.com/docs/ai-gateway/models-and-providers/provider-filtering-and-ordering).
The serving provider is reported in `gateway.routing.finalProvider` of the provider metadata and
the cost in `gateway.cost`. Endpoint listing: GET /v1/models/{author}/{slug}/endpoints, same shape
as OpenRouter's (checked live), so `openrouter.parse_endpoints` is reused.
"""

from __future__ import annotations

from typing import Any

import httpx

from ..config import GATEWAY_BASE_URL
from .base import HttpChatClient


def gateway_routing(provider: str) -> dict[str, Any]:
    return {"gateway": {"only": [provider]}}


class VercelGatewayClient(HttpChatClient):
    def __init__(
        self,
        provider: str,
        api_key: str | None,
        base_url: str = GATEWAY_BASE_URL,
        timeout_s: float = 300.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        super().__init__(base_url, api_key, timeout_s, transport)
        # Result files and stats keep routes apart: "gateway-deepinfra" vs OpenRouter "DeepInfra".
        self.name = f"gateway-{provider}"
        self.provider = provider
        self.route = "gateway"
        self.expected_provider = provider

    def prepare(self, payload: dict[str, Any]) -> dict[str, Any]:
        return {**payload, "providerOptions": gateway_routing(self.provider)}
