import json

import pytest

from conformance.probes import PROBES, get_probe
from conformance.probes.params import length_ratio, template_leaks
from conformance.probes.reasoning import answer_correct, reasoning_tokens


def body(content="", tool_calls=None, usage=None, finish="stop"):
    msg = {"role": "assistant", "content": content}
    if tool_calls:
        msg["tool_calls"] = tool_calls
    return {"choices": [{"message": msg, "finish_reason": finish}], "usage": usage or {}}


def call(name, args):
    return {
        "id": "1",
        "type": "function",
        "function": {"name": name, "arguments": json.dumps(args)},
    }


@pytest.mark.parametrize("name", list(PROBES))
def test_each_probe_loads_20_cases_and_builds_requests(name):
    p = get_probe(name)
    cases = p.load_cases()
    assert len(cases) == 20
    for c in cases:
        payload = p.build_request(c, "m").to_payload()
        assert payload["model"] == "m" and payload["messages"]
        assert "max_tokens" in payload


def test_case_ids_unique_across_probes():
    ids = [c.id for n in PROBES for c in get_probe(n).load_cases()]
    assert len(ids) == len(set(ids))


def test_tool_case_expectations_are_well_formed():
    for c in get_probe("tool_calls").load_cases():
        names = {t["function"]["name"] for t in c.tools}
        if c.expect.get("tool"):
            assert c.expect["tool"] in names, c.id
            props = next(
                t["function"]["parameters"]["properties"]
                for t in c.tools
                if t["function"]["name"] == c.expect["tool"]
            )
            assert set(c.expect.get("args", {})) <= set(props), c.id


def cases_by_id(name):
    return {c.id: c for c in get_probe(name).load_cases()}


def test_tool_calls_scoring():
    p, cs = get_probe("tool_calls"), cases_by_id("tool_calls")
    paris = cs["should-call-weather-paris"]
    good = p.score(paris, body(tool_calls=[call("get_weather", {"city": "paris"})]))
    assert good["passed"] and good["args_valid"] and good["args_match"]
    wrong_city = p.score(paris, body(tool_calls=[call("get_weather", {"city": "Lyon"})]))
    assert wrong_city["args_valid"] and wrong_city["args_match"] is False
    assert not wrong_city["passed"]
    bad_args = p.score(paris, body(tool_calls=[call("get_weather", {"x": 1})]))
    assert bad_args["args_valid"] is False and not bad_args["passed"]
    wrong_tool = p.score(
        cs["choose-time-tokyo"], body(tool_calls=[call("get_weather", {"city": "T"})])
    )
    assert not wrong_tool["trigger_correct"]
    over_call = p.score(
        cs["should-not-call-arithmetic"], body(tool_calls=[call("get_time", {"timezone": "UTC"})])
    )
    assert not over_call["trigger_correct"] and over_call["args_match"] is None
    silent = p.score(cs["continuation-weather-answer"], body(content="", finish="stop"))
    assert silent["silent_termination"] and not silent["passed"]
    ok = p.score(cs["continuation-weather-answer"], body(content="18C and cloudy."))
    assert ok["passed"]
    truncated = p.score(cs["should-not-call-capital"], body(content="Let me th", finish="length"))
    assert truncated["truncated"] and not truncated["passed"]


def test_tool_calls_numeric_and_parallel_args():
    p, cs = get_probe("tool_calls"), cases_by_id("tool_calls")
    fx = p.score(
        cs["should-call-currency"],
        body(tool_calls=[call("convert_currency", {"amount": 250.0, "from": "EUR", "to": "USD"})]),
    )
    assert fx["args_match"] and fx["passed"]
    second = p.score(
        cs["continuation-second-call"],
        body(tool_calls=[call("get_weather", {"city": "Rome"})]),
    )
    assert second["passed"]
    bad_pattern = p.score(
        cs["should-call-order-lookup"],
        body(tool_calls=[call("lookup_order", {"order_id": "482913"})]),
    )
    assert bad_pattern["args_valid"] is False


def test_tool_call_with_malformed_json_args():
    p, cs = get_probe("tool_calls"), cases_by_id("tool_calls")
    bad = {"id": "1", "type": "function", "function": {"name": "get_weather", "arguments": "{oops"}}
    s = p.score(cs["should-call-weather-paris"], body(tool_calls=[bad]))
    assert s["args_valid"] is False and s["args_match"] is False


def test_reasoning_scoring():
    p, cs = get_probe("reasoning"), cases_by_id("reasoning")
    usage = {"completion_tokens": 900, "completion_tokens_details": {"reasoning_tokens": 800}}
    s = p.score(cs["train-xhigh"], body("The trip takes 205 minutes.\n\n205", usage=usage))
    assert s["reasoning_tokens"] == 800 and s["thinking_as_expected"] and s["answer_correct"]
    off = p.score(cs["train-off-kwargs"], body("205", usage=usage))
    assert not off["thinking_as_expected"]  # thinking leaked through despite enable_thinking=false
    zero = p.score(cs["train-off-openrouter"], body("205", usage={"completion_tokens": 5}))
    assert zero["thinking_as_expected"]
    wrong = p.score(cs["painters-low"], body("6 workers need 16", usage=usage))
    assert wrong["answer_correct"] is False
    frac = p.score(cs["balls-medium"], body("P = 12/90 = **2/15**", usage=usage))
    assert frac["answer_correct"]


def test_answer_correct_edge_cases():
    assert answer_correct("1,205", "1205")
    assert answer_correct("no numbers", "6") is False
    assert answer_correct("anything", None) is None


def test_reasoning_tokens_fallback_estimate():
    b = body("x")
    b["choices"][0]["message"]["reasoning"] = "a" * 400
    assert reasoning_tokens(b) == (100, True)


def test_params_scoring():
    p, cs = get_probe("params"), cases_by_id("params")
    assert p.score(cs["stop-digit"], body("1, 2, 3, 4, "))["stop_respected"]
    assert not p.score(cs["stop-digit"], body("1, 2, 3, 4, 5"))["stop_respected"]
    assert not p.score(cs["stop-newline"], body("apple\nbanana"))["stop_respected"]
    assert not p.score(cs["stop-multiple"], body("one two three four five six seven"))[
        "stop_respected"
    ]
    over = p.score(cs["max-tokens-32"], body("x", usage={"completion_tokens": 40}, finish="length"))
    assert not over["max_tokens_respected"] and over["truncated_finish"]
    leak = p.score(cs["leak-hello"], body("hi <|im_end|>"))
    assert leak["template_leak"]
    think_leak = p.score(cs["leak-thinking-on-short"], body("hmm</think>144"))
    assert think_leak["template_leak"]
    assert (
        p.score(cs["temp0-primes"], body("a"))["output_sha"]
        == p.score(cs["temp0-primes"], body("a"))["output_sha"]
    )


def test_params_temp0_cases_are_greedy():
    for c in get_probe("params").load_cases():
        if c.kind == "temp0":
            assert c.params["temperature"] == 0


def test_leak_regex_and_length_ratio():
    assert template_leaks("a <think> b </think>") == ["</think>", "<think>"]
    assert template_leaks("clean text") == []
    assert length_ratio([50, 50], [100, 100]) == 0.5
