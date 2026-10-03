import asyncio
import json

import httpx
import pytest

from conformance.budget import BudgetExceeded, Ledger
from conformance.clients.base import ChatResponse
from conformance.clients.openrouter import OpenRouterClient
from conformance.probes import get_probe
from conformance.runner import load_results, run_probe, should_retry


def ok_body():
    return {
        "choices": [{"message": {"role": "assistant", "content": "hi"}, "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 10, "completion_tokens": 5, "cost": 0.001},
    }


def run(handler, tmp_path, repeats=2, cap=60.0, probe="params"):
    async def go():
        client = OpenRouterClient("P", "k", transport=httpx.MockTransport(handler))
        ledger = Ledger(tmp_path / "spend.jsonl", cap)

        async def nosleep(_):
            return None

        try:
            return await run_probe(
                get_probe(probe),
                client,
                "m",
                repeats,
                ledger,
                tmp_path / "runs",
                1.0,
                1.0,
                2,
                nosleep,
            )
        finally:
            await client.aclose()

    return asyncio.run(go())


def test_should_retry_only_429_and_5xx():
    assert should_retry(ChatResponse(status_code=429))
    assert should_retry(ChatResponse(status_code=503))
    assert not should_retry(ChatResponse(status_code=400))
    assert not should_retry(ChatResponse(status_code=None, error="x"))


def test_run_writes_jsonl_manifest_and_ledger(tmp_path):
    path, manifest = run(lambda r: httpx.Response(200, json=ok_body()), tmp_path)
    results = load_results([path])
    assert len(results) == 8  # 4 cases x 2 repeats
    assert results[0].request["provider"]["allow_fallbacks"] is False
    assert results[0].score and results[0].cost_usd == 0.001
    m = json.loads(path.with_suffix(".manifest.json").read_text())
    assert m["model"] == "m" and m["provider"] == "P" and len(m["case_file_sha256"]) == 64
    assert m["git_sha"] and m["harness_version"] and m["timestamp"] and m["requests"]
    assert Ledger(tmp_path / "spend.jsonl", 60).spent() == pytest.approx(0.008)


def test_retries_then_gives_up_after_three(tmp_path):
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        return httpx.Response(503, json={"error": "down"})

    path, _ = run(handler, tmp_path, repeats=1)
    assert calls["n"] == 4 * 4  # 4 cases x (1 try + 3 retries)
    assert all(r.attempts == 4 and r.status_code == 503 for r in load_results([path]))


def test_no_retry_on_400(tmp_path):
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        return httpx.Response(400, json={"error": "bad"})

    run(handler, tmp_path, repeats=1)
    assert calls["n"] == 4


def test_retry_recovers(tmp_path):
    seq = iter([429, 200] * 100)

    def handler(request):
        return httpx.Response(next(seq), json=ok_body())

    path, _ = run(handler, tmp_path, repeats=1)
    assert all(r.status_code == 200 and r.attempts == 2 for r in load_results([path]))


def test_second_run_never_overwrites(tmp_path):
    h = lambda r: httpx.Response(200, json=ok_body())  # noqa: E731
    p1, _ = run(h, tmp_path, repeats=1)
    p2, _ = run(h, tmp_path, repeats=1)
    assert p1 != p2 and p1.exists() and p2.exists()


def test_budget_cap_halts_run(tmp_path):
    with pytest.raises(BudgetExceeded):
        run(lambda r: httpx.Response(200, json=ok_body()), tmp_path, repeats=5, cap=0.0005)
