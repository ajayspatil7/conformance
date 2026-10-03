"""OpenRouter client that pins exactly one provider.

Routing fields (verified 2026-10-03 against https://openrouter.ai/docs/features/provider-routing):
`provider.order`, `provider.allow_fallbacks`, `provider.require_parameters`.
Endpoint listing: GET /api/v1/models/{author}/{slug}/endpoints (verified live; the docs pages
for it were not fetchable, so the response shape was checked against a real response).
"""

from __future__ import annotations

from typing import Any

import httpx
from pydantic import BaseModel

from ..config import OPENROUTER_BASE_URL
from .base import HttpChatClient


def provider_routing(provider: str, require_parameters: bool = True) -> dict[str, Any]:
    return {
        "order": [provider],
        "allow_fallbacks": False,
        "require_parameters": require_parameters,
    }


class OpenRouterClient(HttpChatClient):
    def __init__(
        self,
        provider: str,
        api_key: str | None,
        base_url: str = OPENROUTER_BASE_URL,
        timeout_s: float = 300.0,
        transport: httpx.AsyncBaseTransport | None = None,
        require_parameters: bool = True,
    ) -> None:
        super().__init__(base_url, api_key, timeout_s, transport)
        self.name = provider
        self.provider = provider
        self.route = "openrouter"
        self.expected_provider = provider
        self.require_parameters = require_parameters

    def prepare(self, payload: dict[str, Any]) -> dict[str, Any]:
        return {**payload, "provider": provider_routing(self.provider, self.require_parameters)}


class EndpointInfo(BaseModel):
    provider_name: str
    tag: str | None = None
    quantization: str | None = None
    context_length: int | None = None
    prompt_price_per_m: float | None = None
    completion_price_per_m: float | None = None
    supported_parameters: list[str] = []


def _per_m(value: Any) -> float | None:
    return float(value) * 1_000_000 if value not in (None, "") else None


def parse_endpoints(body: dict[str, Any]) -> list[EndpointInfo]:
    out = []
    for e in (body.get("data") or {}).get("endpoints", []):
        pricing = e.get("pricing") or {}
        out.append(
            EndpointInfo(
                provider_name=e["provider_name"],
                tag=e.get("tag"),
                quantization=e.get("quantization"),
                context_length=e.get("context_length"),
                prompt_price_per_m=_per_m(pricing.get("prompt")),
                completion_price_per_m=_per_m(pricing.get("completion")),
                supported_parameters=e.get("supported_parameters") or [],
            )
        )
    return out


def list_endpoints(
    model: str,
    api_key: str | None = None,
    base_url: str = OPENROUTER_BASE_URL,
    transport: httpx.BaseTransport | None = None,
) -> list[EndpointInfo]:
    """List providers serving `model` (free, read-only call)."""
    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
    with httpx.Client(timeout=30.0, headers=headers, transport=transport) as http:
        r = http.get(f"{base_url.rstrip('/')}/models/{model}/endpoints")
        r.raise_for_status()
        return parse_endpoints(r.json())
