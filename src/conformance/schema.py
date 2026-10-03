"""Pydantic models shared across the harness."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class Case(BaseModel):
    id: str
    probe: str
    kind: str
    description: str = ""
    messages: list[dict[str, Any]]
    tools: list[dict[str, Any]] | None = None
    params: dict[str, Any] = Field(default_factory=dict)  # merged verbatim into the request body
    expect: dict[str, Any] = Field(default_factory=dict)


class Request(BaseModel):
    model: str
    messages: list[dict[str, Any]]
    tools: list[dict[str, Any]] | None = None
    params: dict[str, Any] = Field(default_factory=dict)

    def to_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {"model": self.model, "messages": self.messages}
        if self.tools:
            payload["tools"] = self.tools
        payload.update(self.params)
        return payload


class Result(BaseModel):
    case_id: str
    probe: str
    provider: str
    repeat: int
    request: dict[str, Any]  # exact payload sent (provider-routing fields included)
    status_code: int | None = None
    response: dict[str, Any] | None = None
    error: str | None = None
    finish_reason: str | None = None
    usage: dict[str, Any] | None = None
    latency_s: float | None = None
    attempts: int = 1
    cost_usd: float = 0.0
    score: dict[str, Any] = Field(default_factory=dict)


class RunManifest(BaseModel):
    run_id: str
    git_sha: str
    case_file: str
    case_file_sha256: str
    model: str
    provider: str
    probe: str
    repeats: int
    requests: list[dict[str, Any]]  # every distinct request payload (all params)
    timestamp: str
    harness_version: str
    result_file: str
