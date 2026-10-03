import asyncio

import httpx
import pytest

from conformance.budget import Ledger, actual_cost
from conformance.clients.openai_compat import OpenAICompatClient
from conformance.clients.vercel_gateway import VercelGatewayClient
from conformance.probes import get_probe
from conformance.probes.base import provider_matches, reported_cost_of, served_provider_of
from conformance.runner import load_results, run_probe


def body(**extra):
    b = {
        "choices": [{"message": {"role": "assistant", "content": "ok"}, "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 10, "completion_tokens": 5},
    }
    b.update(extra)
    return b


GATEWAY_META = {"gateway": {"routing": {"finalProvider": "deepinfra"}, "cost": "0.0021"}}


def test_gateway_client_pins_with_only():
    c = VercelGatewayClient("deepinfra", "k")
    sent = c.prepare({"model": "alibaba/qwen3.8-27b", "messages": []})
    assert sent["providerOptions"] == {"gateway": {"only": ["deepinfra"]}}
    assert c.name == "gateway-deepinfra" and c.route == "gateway"
    assert c.base_url == "https://ai-gateway.vercel.sh/v1"


@pytest.mark.parametrize(
    "b, served",
    [
        (body(provider="DeepInfra"), "DeepInfra"),  # OpenRouter
        (body(providerMetadata=GATEWAY_META), "deepinfra"),  # documented gateway key
        (body(provider_metadata=GATEWAY_META), "deepinfra"),
        (
            {"choices": [{"message": {"content": "x", "provider_metadata": GATEWAY_META}}]},
            "deepinfra",
        ),
        (body(), None),
        (None, None),
    ],
)
def test_served_provider_of(b, served):
    assert served_provider_of(b) == served


def test_reported_cost_of():
    assert reported_cost_of(body(providerMetadata=GATEWAY_META)) == pytest.approx(0.0021)
    assert reported_cost_of({"usage": {"cost": 0}}) == 0.0
    assert reported_cost_of(body()) is None
    assert actual_cost({"prompt_tokens": 1_000_000}, 9.0, 9.0, reported=0.5) == 0.5


@pytest.mark.parametrize(
    "expected, served, ok",
    [
        ("deepinfra", "DeepInfra", True),
        ("ModelRun", "ModelRun", True),
        ("mancer", "Mancer 2", True),
        ("deepinfra", "Novita", False),
        ("deepinfra", None, None),
    ],
)
def test_provider_matches(expected, served, ok):
    assert provider_matches(expected, served) is ok


def _run(client, tmp_path):
    async def nosleep(_):
        return None

    async def go():
        probe = get_probe("params")
        cases = [c for c in probe.load_cases() if c.id == "stop-digit"]
        try:
            return await run_probe(
                probe, client, "m", 2, Ledger(tmp_path / "s.jsonl", 5), tmp_path / "runs",
                1.0, 1.0, 1, nosleep, cases=cases,
            )  # fmt: skip
        finally:
            await client.aclose()

    return asyncio.run(go())


def test_runner_flags_rerouting_and_uses_gateway_cost(tmp_path):
    served = iter(["deepinfra", "novita"])

    def handler(request):
        meta = {"gateway": {"routing": {"finalProvider": next(served)}, "cost": "0.002"}}
        return httpx.Response(200, json=body(providerMetadata=meta))

    client = VercelGatewayClient("deepinfra", "k", transport=httpx.MockTransport(handler))
    path, manifest = _run(client, tmp_path)
    results = load_results([path])
    assert sorted(r.score["provider_match"] for r in results) == [False, True]
    assert {r.served_provider for r in results} == {"deepinfra", "novita"}
    assert all(r.cost_usd == pytest.approx(0.002) for r in results)
    assert manifest.route == "gateway" and manifest.provider == "gateway-deepinfra"
    assert path.name.endswith("_params_gateway-deepinfra.jsonl")


def test_direct_route_sends_no_key_and_no_provider_check(tmp_path):
    seen = {}

    def handler(request):
        seen["auth"] = request.headers.get("authorization")
        return httpx.Response(200, json=body())

    client = OpenAICompatClient(
        "http://localhost:8000/v1", None, name="reference", transport=httpx.MockTransport(handler)
    )
    path, manifest = _run(client, tmp_path)
    assert seen["auth"] is None
    assert all("provider_match" not in r.score for r in load_results([path]))
    assert manifest.route == "direct" and manifest.base_url == "http://localhost:8000/v1"
