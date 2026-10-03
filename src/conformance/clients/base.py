"""Shared chat-completions client plumbing."""

from __future__ import annotations

import time
from typing import Any, Protocol

import httpx
from pydantic import BaseModel


class ChatResponse(BaseModel):
    status_code: int | None = None
    body: dict[str, Any] | None = None
    latency_s: float = 0.0
    error: str | None = None


class ChatClient(Protocol):
    name: str

    def prepare(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Return the exact body that will be sent (adds provider-routing fields)."""

    async def chat(self, payload: dict[str, Any]) -> ChatResponse: ...

    async def aclose(self) -> None: ...


class HttpChatClient:
    """POST {base_url}/chat/completions. Never retries; the runner owns retry policy."""

    name = "http"
    route = "direct"
    expected_provider: str | None = None  # provider the request is pinned to, if any

    def __init__(
        self,
        base_url: str,
        api_key: str | None,
        timeout_s: float = 300.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        self._http = httpx.AsyncClient(timeout=timeout_s, headers=headers, transport=transport)

    def prepare(self, payload: dict[str, Any]) -> dict[str, Any]:
        return payload

    async def chat(self, payload: dict[str, Any]) -> ChatResponse:
        start = time.perf_counter()
        try:
            r = await self._http.post(f"{self.base_url}/chat/completions", json=payload)
        except httpx.HTTPError as exc:
            return ChatResponse(error=f"{type(exc).__name__}: {exc}", latency_s=_since(start))
        try:
            body = r.json()
        except ValueError:
            body = None
        return ChatResponse(status_code=r.status_code, body=body, latency_s=_since(start))

    async def aclose(self) -> None:
        await self._http.aclose()


def _since(start: float) -> float:
    return time.perf_counter() - start
