import asyncio

import httpx
import pytest

from conformance_probe.clients.openai_compat import OpenAICompatClient
from conformance_probe.clients.openrouter import OpenRouterClient, list_endpoints, parse_endpoints


def test_openrouter_pins_provider_and_sends_auth():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["auth"] = request.headers["authorization"]
        seen["url"] = str(request.url)
        seen["body"] = request.read()
        return httpx.Response(200, json={"choices": []})

    async def go():
        c = OpenRouterClient("DeepInfra", "k", transport=httpx.MockTransport(handler))
        body = c.prepare({"model": "m", "messages": []})
        resp = await c.chat(body)
        await c.aclose()
        return body, resp

    body, resp = asyncio.run(go())
    assert body["provider"] == {
        "order": ["DeepInfra"],
        "allow_fallbacks": False,
        "require_parameters": True,
    }
    assert seen["auth"] == "Bearer k"
    assert seen["url"].endswith("/chat/completions")
    assert resp.status_code == 200


def test_openai_compat_has_no_routing_fields():
    c = OpenAICompatClient("http://localhost:8000/v1", name="ref")
    assert c.prepare({"model": "m"}) == {"model": "m"}


def test_transport_error_is_captured():
    def handler(request):
        raise httpx.ConnectError("boom")

    async def go():
        c = OpenAICompatClient("http://x/v1", transport=httpx.MockTransport(handler))
        return await c.chat({})

    resp = asyncio.run(go())
    assert resp.status_code is None and "ConnectError" in resp.error


SAMPLE = {
    "data": {
        "endpoints": [
            {
                "provider_name": "DeepInfra",
                "tag": "deepinfra/fp8",
                "quantization": "fp8",
                "context_length": 40960,
                "pricing": {"prompt": "0.0000001", "completion": "0.0000003"},
                "supported_parameters": ["tools", "temperature"],
            }
        ]
    }
}


def test_parse_and_list_endpoints():
    eps = parse_endpoints(SAMPLE)
    assert eps[0].prompt_price_per_m == pytest.approx(0.1)
    assert eps[0].completion_price_per_m == pytest.approx(0.3)

    def handler(request):
        assert request.url.path.endswith("/models/qwen/x/endpoints")
        return httpx.Response(200, json=SAMPLE)

    got = list_endpoints("qwen/x", transport=httpx.MockTransport(handler))
    assert got[0].provider_name == "DeepInfra"
