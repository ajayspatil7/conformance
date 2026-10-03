"""Probe interface and response helpers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

import yaml

from ..config import CASES_DIR
from ..schema import Case, Request


def first_choice(body: dict[str, Any] | None) -> dict[str, Any]:
    choices = (body or {}).get("choices") or []
    return choices[0] if choices else {}


def message_of(body: dict[str, Any] | None) -> dict[str, Any]:
    return first_choice(body).get("message") or {}


def content_of(body: dict[str, Any] | None) -> str:
    return message_of(body).get("content") or ""


def finish_reason_of(body: dict[str, Any] | None) -> str | None:
    return first_choice(body).get("finish_reason")


def _gateway_meta(body: dict[str, Any]) -> dict[str, Any]:
    """Vercel AI Gateway provider metadata; location in raw chat-completions bodies unconfirmed,
    so the documented key and its plausible spellings are all checked."""
    msg = message_of(body)
    for holder in (body, msg):
        for key in ("providerMetadata", "provider_metadata"):
            meta = holder.get(key)
            if isinstance(meta, dict) and isinstance(meta.get("gateway"), dict):
                return meta["gateway"]
    return {}


def served_provider_of(body: dict[str, Any] | None) -> str | None:
    """Which upstream provider actually served the request, as reported by the router."""
    if not body:
        return None
    if isinstance(body.get("provider"), str):  # OpenRouter
        return body["provider"]
    # Only `finalProvider` means "served". `resolvedProvider` is the routing plan and is present
    # even when no provider was attempted (seen on 403s with providerAttemptCount=0).
    final = (_gateway_meta(body).get("routing") or {}).get("finalProvider")
    return final if isinstance(final, str) else None


def reported_cost_of(body: dict[str, Any] | None) -> float | None:
    """Router-reported USD cost: OpenRouter `usage.cost`, else AI Gateway `gateway.cost`."""
    if not body:
        return None
    cost = (body.get("usage") or {}).get("cost")
    if cost is None:
        cost = _gateway_meta(body).get("cost")
    try:
        return float(cost) if cost is not None else None
    except (TypeError, ValueError):
        return None


def _norm_provider(name: str) -> str:
    return "".join(ch for ch in name.casefold() if ch.isalnum())


def provider_matches(expected: str, served: str | None) -> bool | None:
    """None when the router did not say; else a case/punctuation-insensitive name or slug match
    (OpenRouter returns display names like "DeepInfra" for the slug "deepinfra")."""
    if served is None:
        return None
    e, s = _norm_provider(expected), _norm_provider(served)
    return bool(e and s) and (e == s or e.startswith(s) or s.startswith(e))


class Probe(ABC):
    name: str
    case_file: str

    @property
    def case_path(self) -> Path:
        return CASES_DIR / self.case_file

    def load_cases(self) -> list[Case]:
        raw = yaml.safe_load(self.case_path.read_text())
        return [Case(probe=self.name, **c) for c in raw["cases"]]

    def build_request(self, case: Case, model: str) -> Request:
        return Request(
            model=model, messages=case.messages, tools=case.tools, params=dict(case.params)
        )

    @abstractmethod
    def score(self, case: Case, body: dict[str, Any] | None) -> dict[str, Any]:
        """Score one response. Booleans become proportions, numbers get bootstrap CIs."""
