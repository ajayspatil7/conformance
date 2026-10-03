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
```
Keys come only from environment variables (see `.env.example`). Budget cap: `CONFORMANCE_BUDGET_USD`
(default 60), enforced against `data/spend.jsonl`.

Failures are reported as bugs or deviations from a reference; no claim is made about intent.
See `AGENTS.md` for contributor/agent rules.

Author: Ajay S Patil. No AI co-authors or AI attribution appear anywhere in this repository.

MIT licensed.
