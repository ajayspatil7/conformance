"""Cost estimation and the hard-cap spend ledger (data/spend.jsonl)."""

from __future__ import annotations

import json
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

from .schema import Case

DEFAULT_MAX_TOKENS = 4096
EST_PROMPT_TOKENS = 600  # conservative per-request prompt size


class BudgetExceeded(RuntimeError):
    pass


def estimate_cost(
    cases: Sequence[Case],
    repeats: int,
    price_in_per_m: float,
    price_out_per_m: float,
    est_prompt_tokens: int = EST_PROMPT_TOKENS,
) -> float:
    """Worst-case USD: every request uses est_prompt_tokens in and its full max_tokens out."""
    total = 0.0
    for c in cases:
        max_tokens = int(c.params.get("max_tokens", DEFAULT_MAX_TOKENS))
        per_request = est_prompt_tokens * price_in_per_m + max_tokens * price_out_per_m
        total += per_request / 1_000_000 * repeats
    return total


def actual_cost(usage: dict | None, price_in_per_m: float, price_out_per_m: float) -> float:
    """Prefer provider-reported `usage.cost`; otherwise tokens x price."""
    if not usage:
        return 0.0
    if isinstance(usage.get("cost"), (int, float)):
        return float(usage["cost"])
    p = int(usage.get("prompt_tokens") or 0)
    c = int(usage.get("completion_tokens") or 0)
    return (p * price_in_per_m + c * price_out_per_m) / 1_000_000


class Ledger:
    def __init__(self, path: Path, cap_usd: float) -> None:
        self.path = path
        self.cap_usd = cap_usd

    def spent(self) -> float:
        if not self.path.exists():
            return 0.0
        total = 0.0
        for line in self.path.read_text().splitlines():
            if line.strip():
                total += float(json.loads(line).get("cost_usd", 0.0))
        return total

    def remaining(self) -> float:
        return self.cap_usd - self.spent()

    def check(self, estimate_usd: float) -> None:
        if estimate_usd > self.remaining():
            raise BudgetExceeded(
                f"estimate ${estimate_usd:.2f} exceeds remaining budget ${self.remaining():.2f} "
                f"(cap ${self.cap_usd:.2f}, spent ${self.spent():.2f})"
            )

    def record(self, run_id: str, provider: str, usage: dict | None, cost_usd: float) -> None:
        row = {
            "ts": datetime.now(UTC).isoformat(),
            "run_id": run_id,
            "provider": provider,
            "prompt_tokens": (usage or {}).get("prompt_tokens"),
            "completion_tokens": (usage or {}).get("completion_tokens"),
            "cost_usd": cost_usd,
        }
        self._append(row)

    def record_aws(
        self, date: str, usd: float, hours: float | None, instance: str | None, region: str | None,
        note: str = "",
    ) -> None:  # fmt: skip
        """Append a human-reported AWS usage row (from the Billing console). No AWS calls."""
        if usd < 0:
            raise ValueError("usd must be >= 0")
        self._append(
            {
                "ts": datetime.now(UTC).isoformat(),
                "date": date,
                "cost_usd": usd,
                "hours": hours,
                "instance": instance,
                "region": region,
                "note": note,
            }
        )

    def rows(self) -> list[dict]:
        if not self.path.exists():
            return []
        return [json.loads(x) for x in self.path.read_text().splitlines() if x.strip()]

    def _append(self, row: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a") as f:
            f.write(json.dumps(row) + "\n")
