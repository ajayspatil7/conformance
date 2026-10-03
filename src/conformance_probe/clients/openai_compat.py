"""Direct OpenAI-compatible endpoint (self-hosted vLLM reference, direct provider cross-checks)."""

from __future__ import annotations

import httpx

from .base import HttpChatClient


class OpenAICompatClient(HttpChatClient):
    def __init__(
        self,
        base_url: str,
        api_key: str | None = None,
        name: str = "direct",
        timeout_s: float = 300.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        super().__init__(base_url, api_key, timeout_s, transport)
        self.name = name
