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
