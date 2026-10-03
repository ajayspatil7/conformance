"""Settings loaded from environment variables only."""

from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path

from pydantic import BaseModel, Field

DEFAULT_MODEL = "qwen/qwen3.8-27b"
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
CASES_DIR = Path(__file__).parent / "cases"

# Placeholder prices, USD per 1M tokens (input, output). Real prices come from
# `cprobe providers` / the provider's pricing page and are passed via --price-in/--price-out.
PLACEHOLDER_PRICES: dict[str, tuple[float, float]] = {
    "placeholder-a": (0.30, 1.20),
    "placeholder-b": (0.40, 1.60),
    "placeholder-c": (0.25, 1.00),
}
DEFAULT_PLACEHOLDER_PRICE = (0.30, 1.20)


class Settings(BaseModel):
    openrouter_api_key: str | None = Field(default=None, repr=False)
    budget_usd: float = 60.0
    max_concurrency: int = 4
    data_dir: Path = Path("data")

    @property
    def runs_dir(self) -> Path:
        return self.data_dir / "runs"

    @property
    def spend_path(self) -> Path:
        return self.data_dir / "spend.jsonl"


def load_settings(env: Mapping[str, str] | None = None) -> Settings:
    e = os.environ if env is None else env
    return Settings(
        openrouter_api_key=e.get("OPENROUTER_API_KEY") or None,
        budget_usd=float(e.get("CPROBE_BUDGET_USD", "60")),
        max_concurrency=int(e.get("CPROBE_MAX_CONCURRENCY", "4")),
        data_dir=Path(e.get("CPROBE_DATA_DIR", "data")),
    )
