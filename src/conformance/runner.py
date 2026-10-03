"""Async case execution: retries, JSONL logging, manifest, budget enforcement."""

from __future__ import annotations

import asyncio
import hashlib
import json
import subprocess
import time
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from pathlib import Path

from . import __version__
from .budget import BudgetExceeded, Ledger, actual_cost
from .clients.base import ChatClient, ChatResponse
from .probes.base import (
    Probe,
    finish_reason_of,
    provider_matches,
    reported_cost_of,
    served_provider_of,
)
from .schema import Case, Result, RunManifest

MAX_RETRIES = 3
BASE_BACKOFF_S = 1.0


class RateLimiter:
    """Spaces request starts at least 60/max_rpm seconds apart (no-op when max_rpm <= 0)."""

    def __init__(
        self,
        max_rpm: float,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.interval = 60.0 / max_rpm if max_rpm > 0 else 0.0
        self._sleep = sleep
        self._clock = clock
        self._next = 0.0
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        if not self.interval:
            return
        async with self._lock:
            now = self._clock()
            wait = self._next - now
            self._next = max(now, self._next) + self.interval
        if wait > 0:
            await self._sleep(wait)


def should_retry(resp: ChatResponse) -> bool:
    """Retry only on HTTP 429 and 5xx (never on transport errors or other 4xx)."""
    sc = resp.status_code
    return sc is not None and (sc == 429 or 500 <= sc < 600)


def git_sha() -> str:
    try:
        return subprocess.run(
            ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True
        ).stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "unknown"


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def unique_result_path(runs_dir: Path, date: str, probe: str, provider: str) -> Path:
    """Never overwrite: raw results are immutable, so later runs get a numeric suffix."""
    safe = provider.replace("/", "_")
    path = runs_dir / f"{date}_{probe}_{safe}.jsonl"
    n = 2
    while path.exists():
        path = runs_dir / f"{date}_{probe}_{safe}-{n}.jsonl"
        n += 1
    return path


async def send_with_retry(
    client: ChatClient,
    body: dict,
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    limiter: RateLimiter | None = None,
) -> tuple[ChatResponse, int]:
    attempts = 0
    while True:
        attempts += 1
        if limiter:
            await limiter.acquire()
        resp = await client.chat(body)
        if not should_retry(resp) or attempts > MAX_RETRIES:
            return resp, attempts
        await sleep(BASE_BACKOFF_S * 2 ** (attempts - 1))


async def run_probe(
    probe: Probe,
    client: ChatClient,
    model: str,
    repeats: int,
    ledger: Ledger,
    runs_dir: Path,
    price_in_per_m: float,
    price_out_per_m: float,
    concurrency: int = 4,
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    cases: list[Case] | None = None,
    max_rpm: float = 0.0,
) -> tuple[Path, RunManifest]:
    cases = cases if cases is not None else probe.load_cases()
    now = datetime.now(UTC)
    runs_dir.mkdir(parents=True, exist_ok=True)
    out_path = unique_result_path(runs_dir, now.strftime("%Y-%m-%d"), probe.name, client.name)
    run_id = out_path.stem

    jobs = [(c, r) for c in cases for r in range(repeats)]
    sem = asyncio.Semaphore(concurrency)
    write_lock = asyncio.Lock()
    halted = False
    limiter = RateLimiter(max_rpm, sleep)

    async def one(case: Case, repeat: int, fh) -> None:
        nonlocal halted
        async with sem:
            if halted or ledger.remaining() <= 0:
                halted = True
                return
            body = client.prepare(probe.build_request(case, model).to_payload())
            resp, attempts = await send_with_retry(client, body, sleep, limiter)
            usage = (resp.body or {}).get("usage")
            cost = actual_cost(usage, price_in_per_m, price_out_per_m, reported_cost_of(resp.body))
            result = Result(
                case_id=case.id,
                probe=probe.name,
                provider=client.name,
                repeat=repeat,
                request=body,
                status_code=resp.status_code,
                response=resp.body,
                error=resp.error,
                finish_reason=finish_reason_of(resp.body),
                usage=usage,
                latency_s=resp.latency_s,
                attempts=attempts,
                cost_usd=cost,
                served_provider=served_provider_of(resp.body),
            )
            if resp.status_code == 200 and resp.body:
                try:
                    result.score = probe.score(case, resp.body)
                except Exception as exc:  # scoring bug must not lose the raw response
                    result.score = {"score_error": f"{type(exc).__name__}: {exc}"}
                expected = getattr(client, "expected_provider", None)
                if expected:
                    # Silent re-routing would invalidate every other metric for this provider.
                    result.score["provider_match"] = provider_matches(
                        expected, result.served_provider
                    )
            async with write_lock:
                fh.write(result.model_dump_json() + "\n")
                fh.flush()
                ledger.record(run_id, client.name, usage, cost)

    with out_path.open("x") as fh:
        await asyncio.gather(*(one(c, r, fh) for c, r in jobs))

    manifest = RunManifest(
        run_id=run_id,
        git_sha=git_sha(),
        case_file=str(probe.case_path.name),
        case_file_sha256=file_sha256(probe.case_path),
        model=model,
        provider=client.name,
        route=getattr(client, "route", "direct"),
        base_url=getattr(client, "base_url", None),
        probe=probe.name,
        repeats=repeats,
        requests=[client.prepare(probe.build_request(c, model).to_payload()) for c in cases],
        timestamp=now.isoformat(),
        harness_version=__version__,
        result_file=out_path.name,
    )
    manifest_path = out_path.with_suffix(".manifest.json")
    with manifest_path.open("x") as fh:
        fh.write(manifest.model_dump_json(indent=2))
    if halted:
        raise BudgetExceeded(f"budget cap reached mid-run; partial results in {out_path}")
    return out_path, manifest


def load_results(paths: list[Path]) -> list[Result]:
    out = []
    for p in paths:
        for line in p.read_text().splitlines():
            if line.strip():
                out.append(Result(**json.loads(line)))
    return out
