"""Probe C: parameter and chat-template sanity."""

from __future__ import annotations

import hashlib
import re
from collections.abc import Sequence
from typing import Any

from ..schema import Case
from .base import Probe, content_of, finish_reason_of

# Special tokens that must never appear in user-visible content.
LEAK_RE = re.compile(
    r"<\|im_start\|>|<\|im_end\|>|<\|endoftext\|>|</?think>|</?tool_call>|<\|vision_\w+\|>"
)


def template_leaks(text: str) -> list[str]:
    return sorted(set(LEAK_RE.findall(text)))


def length_ratio(provider_lengths: Sequence[float], reference_lengths: Sequence[float]) -> float:
    """Mean output length of provider divided by reference (1.0 = same)."""
    if not provider_lengths or not reference_lengths:
        raise ValueError("need lengths from both provider and reference")
    ref = sum(reference_lengths) / len(reference_lengths)
    return (sum(provider_lengths) / len(provider_lengths)) / ref


class ParamsProbe(Probe):
    name = "params"
    case_file = "params.yaml"

    def score(self, case: Case, body: dict[str, Any] | None) -> dict[str, Any]:
        text = content_of(body)
        usage = (body or {}).get("usage") or {}
        completion = int(usage.get("completion_tokens") or 0)
        out: dict[str, Any] = {
            "output_chars": len(text),
            "completion_tokens": completion,
            "template_leak": bool(template_leaks(text)),
            "output_sha": hashlib.sha256(text.encode()).hexdigest()[:16],
        }
        kind = case.kind
        if kind == "stop":
            stops = case.params.get("stop") or []
            stops = [stops] if isinstance(stops, str) else stops
            out["stop_respected"] = not any(s in text for s in stops)
        elif kind == "max_tokens":
            limit = int(case.params["max_tokens"])
            out["max_tokens_respected"] = completion <= limit
            out["truncated_finish"] = finish_reason_of(body) == "length"
        # temp0 stability needs several repeats: compare output_sha across them (see stats).
        return out
