"""`conformance` command line interface. Real API calls require --yes; default is --dry-run."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
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
    FREE_MAX_RPM,
    PLACEHOLDER_PRICES,
    is_free_model,
    load_settings,
)
from .probes import PROBES, get_probe
from .runner import load_results, run_probe
from .schema import Case
from .summary import flag_deviations, length_ratios, summarize

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


def select_cases(names: list[str], case_ids: list[str] | None) -> dict[str, list[Case]]:
    """Load each probe's cases, keeping only `case_ids` when given; drop probes left empty."""
    selected: dict[str, list[Case]] = {}
    for n in names:
        cases = get_probe(n).load_cases()
        if case_ids:
            cases = [c for c in cases if c.id in case_ids]
        if cases:
            selected[n] = cases
    found = {c.id for cs in selected.values() for c in cs}
    missing = sorted(set(case_ids or []) - found)
    if missing:
        raise typer.BadParameter(f"unknown case id(s): {', '.join(missing)}")
    return selected


@app.command()
def run(
    probe: Annotated[str, typer.Option(help="tool_calls | reasoning | params | all")],
    provider: Annotated[list[str], typer.Option(help="Provider name; repeatable")],
    repeats: int = 5,
    model: str = DEFAULT_MODEL,
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Estimate only (default)")] = False,
    yes: Annotated[bool, typer.Option("--yes", help="Make real API calls")] = False,
    base_url: Annotated[
        str | None, typer.Option(help="Direct OpenAI-compatible base URL (else OpenRouter)")
    ] = None,
    price_in: Annotated[float | None, typer.Option(help="USD per 1M input tokens")] = None,
    price_out: Annotated[float | None, typer.Option(help="USD per 1M output tokens")] = None,
    case: Annotated[
        list[str] | None, typer.Option("--case", help="Only these case ids; repeatable")
    ] = None,
    max_rpm: Annotated[
        float | None, typer.Option(help="Client-side request cap per minute (0 = none)")
    ] = None,
    require_parameters: Annotated[
        bool,
        typer.Option(
            "--require-parameters/--no-require-parameters",
            help="OpenRouter: only route to endpoints supporting every sent parameter",
        ),
    ] = True,
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
    selected = select_cases(names, case)

    free = is_free_model(model)
    if free and price_in is None and price_out is None:
        price_in, price_out = 0.0, 0.0
    rpm = max_rpm if max_rpm is not None else settings.max_rpm
    if free and (rpm <= 0 or rpm > FREE_MAX_RPM):
        rpm = FREE_MAX_RPM

    total = 0.0
    n_requests = 0
    typer.echo(f"model={model} repeats={repeats} mode={'REAL' if real else 'DRY-RUN'}")
    for prov in provider:
        pin, pout = _prices(prov, price_in, price_out)
        known = prov in PLACEHOLDER_PRICES or (price_in is not None and price_out is not None)
        note = "" if known else " (placeholder price)"
        for n, cases in selected.items():
            est = estimate_cost(cases, repeats, pin, pout)
            total += est
            n_requests += len(cases) * repeats
            typer.echo(
                f"  {prov:<16} {n:<11} {len(cases):>2} cases x {repeats} = "
                f"{len(cases) * repeats:>3} requests  worst-case ${est:.4f}{note}"
            )
    typer.echo(
        f"TOTAL {n_requests} requests, worst-case ${total:.4f}; spent ${ledger.spent():.2f}; "
        f"remaining ${ledger.remaining():.2f} of ${settings.budget_usd:.2f}"
    )
    if free:
        typer.echo(
            f"NOTE: {model} is a free variant: $0, capped at {FREE_MAX_RPM:.0f} req/min and "
            "50 req/day (1000/day with >= $10 credits purchased). Smoke tests only; "
            "free-variant results are not report data."
        )
    if not require_parameters:
        typer.echo("NOTE: require_parameters=false; unsupported params may be silently dropped.")
    try:
        ledger.check(total)
    except BudgetExceeded as exc:
        typer.echo(f"REFUSED: {exc}", err=True)
        raise typer.Exit(2) from exc
    if not real:
        typer.echo("Dry run: no network calls made. Re-run with --yes to call the API.")
        return

    if price_in is None or price_out is None:
        typer.echo("REFUSED: real runs need explicit --price-in and --price-out.", err=True)
        raise typer.Exit(2)
    if not settings.openrouter_api_key and not base_url:
        typer.echo("REFUSED: OPENROUTER_API_KEY is not set in the environment.", err=True)
        raise typer.Exit(2)
    asyncio.run(
        _execute(
            selected, provider, repeats, model, base_url, price_in, price_out, ledger, rpm,
            require_parameters,
        )
    )  # fmt: skip


async def _execute(
    selected: dict[str, list[Case]],
    providers_: list[str],
    repeats: int,
    model: str,
    base_url: str | None,
    price_in: float,
    price_out: float,
    ledger: Ledger,
    max_rpm: float,
    require_parameters: bool,
) -> None:
    settings = load_settings()
    for prov in providers_:
        client: ChatClient
        if base_url:
            client = OpenAICompatClient(base_url, settings.openrouter_api_key, name=prov)
        else:
            client = OpenRouterClient(
                prov, settings.openrouter_api_key, require_parameters=require_parameters
            )
        try:
            for n, cases in selected.items():
                path, _ = await run_probe(
                    get_probe(n), client, model, repeats, ledger, settings.runs_dir,
                    price_in, price_out, settings.max_concurrency, cases=cases, max_rpm=max_rpm,
                )  # fmt: skip
                typer.echo(f"wrote {path}")
        finally:
            await client.aclose()


@app.command()
def spend() -> None:
    """Show spend to date: OpenRouter API ledger and AWS credit ledger (local files only)."""
    settings = load_settings()
    api = Ledger(settings.spend_path, settings.budget_usd)
    aws = Ledger(settings.aws_spend_path, settings.aws_credits_usd)
    typer.echo(
        f"OpenRouter API: spent ${api.spent():.4f} of ${api.cap_usd:.2f} "
        f"(remaining ${api.remaining():.4f})  [{settings.spend_path}]"
    )
    by_provider: dict[str, float] = {}
    for row in api.rows():
        by_provider[row.get("provider", "?")] = (
            by_provider.get(row.get("provider", "?"), 0.0) + row["cost_usd"]
        )
    for prov, usd in sorted(by_provider.items()):
        typer.echo(f"  {prov:<20} ${usd:.4f}")
    typer.echo(
        f"AWS credits:    used ${aws.spent():.2f} of ${aws.cap_usd:.2f} "
        f"(remaining ${aws.remaining():.2f})  [{settings.aws_spend_path}]"
    )
    for row in aws.rows():
        hours = f"{row['hours']}h" if row.get("hours") is not None else "?h"
        typer.echo(
            f"  {row['date']}  ${row['cost_usd']:.2f}  {hours}  {row.get('instance') or ''} "
            f"{row.get('region') or ''}  {row.get('note') or ''}".rstrip()
        )


@app.command("aws-log")
def aws_log(
    usd: Annotated[float, typer.Option(help="USD of AWS credits used (from the Billing console)")],
    hours: Annotated[float | None, typer.Option(help="Instance hours")] = None,
    instance: Annotated[str | None, typer.Option(help="Instance type, e.g. g6e.xlarge")] = None,
    region: Annotated[str | None, typer.Option(help="AWS region")] = None,
    note: Annotated[str, typer.Option(help="What it was for")] = "",
    date: Annotated[str | None, typer.Option(help="YYYY-MM-DD (default today, UTC)")] = None,
) -> None:
    """Record AWS credit usage the human read from the Billing console. Makes no AWS calls."""
    settings = load_settings()
    aws = Ledger(settings.aws_spend_path, settings.aws_credits_usd)
    day = date or datetime.now(UTC).strftime("%Y-%m-%d")
    try:
        aws.record_aws(day, usd, hours, instance, region, note)
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc
    typer.echo(f"logged ${usd:.2f}; AWS credits remaining ${aws.remaining():.2f}")
    if aws.remaining() < 0.2 * aws.cap_usd:
        typer.echo("WARNING: less than 20% of AWS credits left.", err=True)


@app.command()
def stats(
    files: Annotated[list[Path], typer.Argument(help="Result JSONL files")],
    reference: Annotated[str | None, typer.Option(help="Reference provider name")] = None,
) -> None:
    """Summarise runs: Wilson intervals for proportions, bootstrap CIs for numbers."""
    results = load_results(files)
    summary = summarize(results)
    if reference:
        summary.update(length_ratios(results, reference))
    for (prov, case, metric), m in sorted(summary.items()):
        lo, hi = m.interval
        typer.echo(
            f"{prov:<16} {case:<28} {metric:<24} n={m.n:<3} {m.estimate:8.3f} [{lo:.3f}, {hi:.3f}]"
        )
    if reference:
        flags = flag_deviations(summary, reference)
        typer.echo(
            f"\n{len(flags)} deviation(s) vs reference {reference} (non-overlapping 95% CIs):"
        )
        for prov, case, metric in flags:
            typer.echo(f"  {prov}: {case} / {metric}")


if __name__ == "__main__":
    app()
