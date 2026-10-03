# conformance

Tests whether inference providers serve an open-weight model correctly. `conformance` sends probe prompts
to each provider (pinned via OpenRouter, or a direct OpenAI-compatible endpoint), compares behaviour
with a reference endpoint, reports gaps with confidence intervals, and attributes failures to likely
causes (wrong chat template, broken tool parser, ignored parameters, model substitution).

**Report #1:** `Qwen/Qwen3.8-27B` — tool calling, reasoning-effort/thinking-control passthrough, and
parameter/chat-template sanity. Ships 10 October 2026. Raw results live in `data/runs/`.

## Quick start
```bash
make setup
make test
make dry-run          # cost estimate, no network
uv run conformance providers qwen/qwen3.8-27b
uv run conformance run --probe tool_calls --provider <name> --repeats 5 --dry-run   # default
uv run conformance run --probe tool_calls --provider <name> --price-in X --price-out Y --yes  # spends money
uv run conformance stats data/runs/*.jsonl --reference <ref-provider>
make smoke-free       # $0 run of 7 cases on qwen/qwen3.8-27b:free (needs OPENROUTER_API_KEY exported)
make smoke-gateway    # ~$0.03: same cases via Vercel AI Gateway pinned to deepinfra
make spend            # OpenRouter, AI Gateway, and AWS credit ledgers
uv run conformance providers --route gateway   # providers on Vercel AI Gateway
uv run conformance aws-log --usd 3.70 --hours 2 --instance g6e.xlarge --note "vLLM reference"
```
Keys come only from environment variables (see `.env.example`).

Routes (`--route`): `openrouter` (default; pins one provider, fallbacks off), `gateway` (Vercel
AI Gateway, pins with `only`, cross-check), `direct` (`--base-url`, e.g. the self-hosted reference).
Every response's serving provider is recorded and checked against the pinned one (`provider_match`).

Budgets: **$60 OpenRouter API** (`CONFORMANCE_BUDGET_USD`, hard cap enforced against
`data/spend.jsonl`), **$5 AI Gateway** (`CONFORMANCE_GATEWAY_BUDGET_USD`, hard cap,
`data/gateway_spend.jsonl`) and **$80 AWS credits** (`CONFORMANCE_AWS_CREDITS_USD`, tracked in
`data/aws_spend.jsonl` from Billing-console numbers logged with `conformance aws-log`).

`conformance stats` reports, per provider and case: every score as a Wilson interval (proportions)
or bootstrap CI (numbers), `http_ok`, `temp0_mode_agreement` (temperature-0 repeats matching the
most common output), and with `--reference`, `length_ratio` (mean completion tokens vs reference).

Failures are reported as bugs or deviations from a reference; no claim is made about intent.
See `AGENTS.md` for contributor/agent rules.

Author: Ajay S Patil.

MIT licensed.
