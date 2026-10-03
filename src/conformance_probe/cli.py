"""`cprobe` command line interface. Real API calls require --yes; default is --dry-run."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Annotated

import typer

from .budget import BudgetExceeded, Ledger, estimate_cost
from .clients.base import ChatClient
from .clients.openai_compat import OpenAICompatClient
from .clients.openrouter import OpenRouterClient, list_endpoints
from .config import (
    DEFAULT_MODEL,
    DEFAULT_PLACEHOLDER_PRICE,
    PLACEHOLDER_PRICES,
    load_settings,
)
from .probes import PROBES, get_probe
from .runner import load_results, run_probe
from .summary import flag_deviations, summarize

app = typer.Typer(add_completion=False, help="Provider conformance probes.")


@app.command()
def providers(model: str = typer.Argument(DEFAULT_MODEL)) -> None:
    """List providers serving MODEL on OpenRouter (free, read-only call)."""
    settings = load_settings()
    for e in list_endpoints(model, settings.openrouter_api_key):
        pin = f"in ${e.prompt_price_per_m:.3f}/M" if e.prompt_price_per_m is not None else "in ?"
        pout = f"out ${e.completion_price_per_m:.3f}/M" if e.completion_price_per_m else "out ?"
        typer.echo(f"{e.provider_name:<20} tag={e.tag} quant={e.quantization} {pin} {pout}")


def _prices(provider: str, price_in: float | None, price_out: float | None) -> tuple[float, float]:
    if price_in is not None and price_out is not None:
        return price_in, price_out
    return PLACEHOLDER_PRICES.get(provider, DEFAULT_PLACEHOLDER_PRICE)


@app.command()
def run(
    probe: Annotated[str, typer.Option(help="tool_calls | reasoning | params | all")],
    provider: Annotated[list[str], typer.Option(help="Provider name; repeatable")],
    repeats: int = 5,
    model: str = DEFAULT_MODEL,
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Estimate only (default)")] = False,
    yes: Annotated[bool, typer.Option("--yes", help="Make real, paid API calls")] = False,
    base_url: Annotated[
        str | None, typer.Option(help="Direct OpenAI-compatible base URL (else OpenRouter)")
    ] = None,
    price_in: Annotated[float | None, typer.Option(help="USD per 1M input tokens")] = None,
    price_out: Annotated[float | None, typer.Option(help="USD per 1M output tokens")] = None,
) -> None:
    """Run probes. Prints a cost estimate; only calls the API with --yes."""
    if dry_run and yes:
        raise typer.BadParameter("--dry-run and --yes are mutually exclusive")
    real = yes
    settings = load_settings()
    ledger = Ledger(settings.spend_path, settings.budget_usd)
    names = list(PROBES) if probe == "all" else [probe]
    if any(n not in PROBES for n in names):
        raise typer.BadParameter(f"unknown probe {probe!r}")

    total = 0.0
    typer.echo(f"model={model} repeats={repeats} mode={'REAL' if real else 'DRY-RUN'}")
    for prov in provider:
        pin, pout = _prices(prov, price_in, price_out)
        known = prov in PLACEHOLDER_PRICES or (price_in is not None and price_out is not None)
        note = "" if known else " (placeholder price)"
        for n in names:
            cases = get_probe(n).load_cases()
            est = estimate_cost(cases, repeats, pin, pout)
            total += est
            typer.echo(
                f"  {prov:<16} {n:<11} {len(cases)} cases x {repeats} = {len(cases) * repeats:>3} "
                f"requests  worst-case ${est:.4f}{note}"
            )
    typer.echo(
        f"TOTAL worst-case ${total:.4f}; spent ${ledger.spent():.2f}; "
        f"remaining ${ledger.remaining():.2f} of ${settings.budget_usd:.2f}"
    )
    try:
        ledger.check(total)
    except BudgetExceeded as exc:
        typer.echo(f"REFUSED: {exc}", err=True)
        raise typer.Exit(2) from exc
    if not real:
        typer.echo("Dry run: no network calls made. Re-run with --yes to spend.")
        return

    if price_in is None or price_out is None:
        typer.echo("REFUSED: real runs need explicit --price-in and --price-out.", err=True)
        raise typer.Exit(2)
    asyncio.run(_execute(names, provider, repeats, model, base_url, price_in, price_out, ledger))


async def _execute(
    names: list[str],
    providers_: list[str],
    repeats: int,
    model: str,
    base_url: str | None,
    price_in: float,
    price_out: float,
    ledger: Ledger,
) -> None:
    settings = load_settings()
    for prov in providers_:
        client: ChatClient
        if base_url:
            client = OpenAICompatClient(base_url, settings.openrouter_api_key, name=prov)
        else:
            client = OpenRouterClient(prov, settings.openrouter_api_key)
        try:
            for n in names:
                path, _ = await run_probe(
                    get_probe(n), client, model, repeats, ledger, settings.runs_dir,
                    price_in, price_out, settings.max_concurrency,
                )  # fmt: skip
                typer.echo(f"wrote {path}")
        finally:
            await client.aclose()


@app.command()
def stats(
    files: Annotated[list[Path], typer.Argument(help="Result JSONL files")],
    reference: Annotated[str | None, typer.Option(help="Reference provider name")] = None,
) -> None:
    """Summarise runs: Wilson intervals for proportions, bootstrap CIs for numbers."""
    summary = summarize(load_results(files))
    for (prov, case, metric), m in sorted(summary.items()):
        lo, hi = m.interval
        typer.echo(
            f"{prov:<16} {case:<28} {metric:<24} n={m.n:<3} {m.estimate:8.3f} [{lo:.3f}, {hi:.3f}]"
        )
    if reference:
        flags = flag_deviations(summary, reference)
        typer.echo(f"\n{len(flags)} deviation(s) vs reference {reference} (non-overlapping CIs):")
        for prov, case, metric in flags:
            typer.echo(f"  {prov}: {case} / {metric}")


if __name__ == "__main__":
    app()
