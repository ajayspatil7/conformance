"""Probe B: reasoning-effort and thinking-control passthrough."""

from __future__ import annotations

import re
from typing import Any

from ..schema import Case
from .base import Probe, content_of, finish_reason_of, message_of


def reasoning_tokens(body: dict[str, Any] | None) -> tuple[int, bool]:
    """(reasoning tokens, estimated?). Uses usage; falls back to ~chars/4 of returned reasoning."""
    usage = (body or {}).get("usage") or {}
    reported = (usage.get("completion_tokens_details") or {}).get("reasoning_tokens")
    if isinstance(reported, int):
        return reported, False
    msg = message_of(body)
    text = msg.get("reasoning") or msg.get("reasoning_content") or ""
    return len(text) // 4, True


NUMBER_RE = re.compile(r"-?\d+(?:\.\d+)?(?:/\d+)?")


def answer_correct(content: str, expected: str | None) -> bool | None:
    """The last number (or a/b fraction) in the final content equals the expected answer."""
    if expected is None:
        return None
    found = NUMBER_RE.findall(content.replace(",", ""))
    return bool(found) and found[-1] == str(expected)


class ReasoningProbe(Probe):
    name = "reasoning"
    case_file = "reasoning.yaml"

    def score(self, case: Case, body: dict[str, Any] | None) -> dict[str, Any]:
        tokens, estimated = reasoning_tokens(body)
        completion = int(((body or {}).get("usage") or {}).get("completion_tokens") or 0)
        observed = tokens > 0
        return {
            "reasoning_tokens": tokens,
            "reasoning_tokens_estimated": estimated,
            "completion_tokens": completion,
            "thinking_observed": observed,
            "thinking_as_expected": observed == bool(case.expect.get("thinking")),
            "answered": bool(content_of(body).strip()),
            "answer_correct": answer_correct(content_of(body), case.expect.get("answer")),
            "truncated": finish_reason_of(body) == "length",
        }
