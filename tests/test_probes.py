import json

import pytest

from conformance.probes import PROBES, get_probe
from conformance.probes.params import length_ratio, template_leaks
from conformance.probes.reasoning import reasoning_tokens


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
def test_each_probe_loads_cases_and_builds_requests(name):
    p = get_probe(name)
    cases = p.load_cases()
    assert len(cases) >= 3
    payload = p.build_request(cases[0], "m").to_payload()
    assert payload["model"] == "m" and payload["messages"]


def cases_by_id(name):
    return {c.id: c for c in get_probe(name).load_cases()}


def test_tool_calls_scoring():
    p, cs = get_probe("tool_calls"), cases_by_id("tool_calls")
    good = p.score(cs["should-call-weather"], body(tool_calls=[call("get_weather", {"city": "P"})]))
    assert good["passed"] and good["args_valid"]
    bad_args = p.score(cs["should-call-weather"], body(tool_calls=[call("get_weather", {"x": 1})]))
    assert bad_args["args_valid"] is False and not bad_args["passed"]
    wrong_tool = p.score(
        cs["choose-time-tool"], body(tool_calls=[call("get_weather", {"city": "T"})])
    )
    assert not wrong_tool["trigger_correct"]
    over_call = p.score(
        cs["should-not-call-arithmetic"], body(tool_calls=[call("get_time", {"timezone": "UTC"})])
    )
    assert not over_call["trigger_correct"]
    silent = p.score(cs["continuation-after-tool-result"], body(content="", finish="stop"))
    assert silent["silent_termination"] and not silent["passed"]
    ok = p.score(cs["continuation-after-tool-result"], body(content="18C and cloudy."))
    assert ok["passed"]


def test_tool_call_with_malformed_json_args():
    p, cs = get_probe("tool_calls"), cases_by_id("tool_calls")
    bad = {"id": "1", "type": "function", "function": {"name": "get_weather", "arguments": "{oops"}}
    assert p.score(cs["should-call-weather"], body(tool_calls=[bad]))["args_valid"] is False


def test_reasoning_scoring():
    p, cs = get_probe("reasoning"), cases_by_id("reasoning")
    usage = {"completion_tokens": 900, "completion_tokens_details": {"reasoning_tokens": 800}}
    s = p.score(cs["effort-xhigh"], body("205", usage=usage))
    assert s["reasoning_tokens"] == 800 and s["thinking_as_expected"]
    off = p.score(cs["thinking-disabled"], body("205", usage=usage))
    assert not off["thinking_as_expected"]  # thinking leaked through despite enable_thinking=false
    zero = p.score(cs["thinking-disabled"], body("205", usage={"completion_tokens": 5}))
    assert zero["thinking_as_expected"]


def test_reasoning_tokens_fallback_estimate():
    b = body("x")
    b["choices"][0]["message"]["reasoning"] = "a" * 400
    assert reasoning_tokens(b) == (100, True)


def test_params_scoring():
    p, cs = get_probe("params"), cases_by_id("params")
    assert p.score(cs["stop-sequence"], body("1, 2, 3, 4, "))["stop_respected"]
    assert not p.score(cs["stop-sequence"], body("1, 2, 3, 4, 5"))["stop_respected"]
    over = p.score(
        cs["max-tokens-respected"], body("x", usage={"completion_tokens": 40}, finish="length")
    )
    assert not over["max_tokens_respected"] and over["truncated_finish"]
    leak = p.score(cs["template-leakage"], body("hi <|im_end|>"))
    assert leak["template_leak"]
    assert (
        p.score(cs["temp0-stability"], body("a"))["output_sha"]
        == p.score(cs["temp0-stability"], body("a"))["output_sha"]
    )


def test_leak_regex_and_length_ratio():
    assert template_leaks("a <think> b </think>") == ["</think>", "<think>"]
    assert template_leaks("clean text") == []
    assert length_ratio([50, 50], [100, 100]) == 0.5
