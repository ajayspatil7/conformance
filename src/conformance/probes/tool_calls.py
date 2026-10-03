"""Probe A: tool calling."""

from __future__ import annotations

import json
from typing import Any

import jsonschema

from ..schema import Case
from .base import Probe, content_of, finish_reason_of, message_of


def _args_valid(call: dict[str, Any], tools: list[dict[str, Any]]) -> bool:
    fn = call.get("function") or {}
    schema = next(
        (
            t["function"].get("parameters", {})
            for t in tools
            if t.get("function", {}).get("name") == fn.get("name")
        ),
        None,
    )
    if schema is None:  # call to a tool that was never offered
        return False
    try:
        args = json.loads(fn.get("arguments") or "")
        jsonschema.validate(args, schema)
    except (json.JSONDecodeError, jsonschema.ValidationError, jsonschema.SchemaError):
        return False
    return True


def _same(actual: Any, expected: Any) -> bool:
    if isinstance(expected, str) and isinstance(actual, str):
        return actual.strip().casefold() == expected.strip().casefold()
    if isinstance(expected, (int, float)) and isinstance(actual, (int, float)):
        return float(actual) == float(expected)
    return actual == expected


def _args_match(calls: list[dict[str, Any]], tool: str | None, expected: dict[str, Any]) -> bool:
    """True if any call to `tool` carries every expected key with the expected value."""
    for c in calls:
        fn = c.get("function") or {}
        if tool and fn.get("name") != tool:
            continue
        try:
            args = json.loads(fn.get("arguments") or "")
        except json.JSONDecodeError:
            continue
        if isinstance(args, dict) and all(_same(args.get(k), v) for k, v in expected.items()):
            return True
    return False


class ToolCallsProbe(Probe):
    name = "tool_calls"
    case_file = "tool_calls.yaml"

    def score(self, case: Case, body: dict[str, Any] | None) -> dict[str, Any]:
        msg = message_of(body)
        calls = msg.get("tool_calls") or []
        called = bool(calls)
        should_call = bool(case.expect.get("should_call"))
        want_tool = case.expect.get("tool")
        trigger_ok = called == should_call
        if called and should_call and want_tool:
            trigger_ok = all((c.get("function") or {}).get("name") == want_tool for c in calls)
        args_valid = all(_args_valid(c, case.tools or []) for c in calls) if called else None
        silent = not called and not content_of(body).strip()
        expected_args = case.expect.get("args")
        args_match = (
            _args_match(calls, want_tool, expected_args) if expected_args and should_call else None
        )
        truncated = finish_reason_of(body) == "length"
        return {
            "called": called,
            "trigger_correct": trigger_ok,
            "args_valid": args_valid,
            "args_match": args_match,
            "silent_termination": silent,
            "truncated": truncated,
            "finish_reason": finish_reason_of(body),
            "passed": (
                trigger_ok
                and args_valid is not False
                and args_match is not False
                and not silent
                and not truncated
            ),
        }
