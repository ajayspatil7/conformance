"""Settings loaded from environment variables only."""

from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path

from pydantic import BaseModel, Field

DEFAULT_MODEL = "qwen/qwen3.8-27b"
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
GATEWAY_BASE_URL = "https://ai-gateway.vercel.sh/v1"
GATEWAY_DEFAULT_MODEL = "alibaba/qwen3.8-27b"
ROUTES = ("openrouter", "gateway", "direct")
CASES_DIR = Path(__file__).parent / "cases"

# Placeholder prices, USD per 1M tokens (input, output). Real prices come from
# `conformance providers` / the provider's pricing page and are passed via --price-in/--price-out.
PLACEHOLDER_PRICES: dict[str, tuple[float, float]] = {
    "placeholder-a": (0.30, 1.20),
    "placeholder-b": (0.40, 1.60),
    "placeholder-c": (0.25, 1.00),
}
DEFAULT_PLACEHOLDER_PRICE = (0.30, 1.20)

# `:free` variants cost $0 but are rate limited by OpenRouter: 20 req/min, and 50 req/day
# (1000/day once >= $10 of credits were ever purchased). Verified 2026-10-03 at
# https://openrouter.ai/docs/api-reference/limits. Smoke-test only; never report data.
FREE_SUFFIX = ":free"
FREE_MAX_RPM = 20.0


def is_free_model(model: str) -> bool:
    return model.endswith(FREE_SUFFIX)


class Settings(BaseModel):
    openrouter_api_key: str | None = Field(default=None, repr=False)
    ai_gateway_api_key: str | None = Field(default=None, repr=False)
    budget_usd: float = 60.0
    gateway_budget_usd: float = 5.0
    max_concurrency: int = 4
    max_rpm: float = 0.0  # 0 = no client-side rate limit
    aws_credits_usd: float = 80.0
    data_dir: Path = Path("data")

    @property
    def runs_dir(self) -> Path:
        return self.data_dir / "runs"

    @property
    def spend_path(self) -> Path:
        return self.data_dir / "spend.jsonl"

    @property
    def gateway_spend_path(self) -> Path:
        return self.data_dir / "gateway_spend.jsonl"

    @property
    def aws_spend_path(self) -> Path:
        return self.data_dir / "aws_spend.jsonl"


def load_settings(env: Mapping[str, str] | None = None) -> Settings:
    e = os.environ if env is None else env
    return Settings(
        openrouter_api_key=e.get("OPENROUTER_API_KEY") or None,
        ai_gateway_api_key=e.get("AI_GATEWAY_API_KEY") or None,
        gateway_budget_usd=float(e.get("CONFORMANCE_GATEWAY_BUDGET_USD", "5")),
        budget_usd=float(e.get("CONFORMANCE_BUDGET_USD", "60")),
        max_concurrency=int(e.get("CONFORMANCE_MAX_CONCURRENCY", "4")),
        max_rpm=float(e.get("CONFORMANCE_MAX_RPM", "0")),
        aws_credits_usd=float(e.get("CONFORMANCE_AWS_CREDITS_USD", "80")),
        data_dir=Path(e.get("CONFORMANCE_DATA_DIR", "data")),
    )
