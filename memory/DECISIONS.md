# Decisions (newest first)

## 2026-10-03 — Layout: data/, reports/, lab/, tests/ at repo root
The spec's tree was ambiguous about nesting; only `cases/`, `probes/`, `clients/` live inside
`src/conformance_probe/`. Cases ship inside the package so `cprobe` works from any directory.

## 2026-10-03 — Four example cases per probe, not three
tool_calls needs four kinds (should-call, should-not-call, choose-among, continuation); reasoning
needs low/medium/xhigh + thinking-off; params has stop/temp0/max_tokens/leakage. Output-length ratio
vs reference is an aggregate (`probes/params.length_ratio`), not a case.

## 2026-10-03 — Reasoning params are sent raw
Cases send `reasoning_effort` and `chat_template_kwargs.enable_thinking` verbatim. OpenRouter may
normalise to its own `reasoning: {effort}` object; with `require_parameters=true` an unsupported
field makes routing fail loudly, which is itself a finding. Revisit once real responses are seen.

## 2026-10-03 — Cost model and budget enforcement
Estimate is worst-case: 600 prompt tokens + full `max_tokens` output per request. Actual spend uses
provider `usage.cost` when present, else tokens x price. The runner re-checks the ledger before every
request and halts (raising BudgetExceeded, keeping partial results) if the cap is reached.
Real runs require explicit `--price-in/--price-out` (USD per 1M tokens); placeholder prices are
dry-run only. Dry-run is the default; `--dry-run --yes` together is an error.

## 2026-10-03 — Result files are never overwritten
`data/runs/<date>_<probe>_<provider>.jsonl` opened with exclusive create; a second run the same day
gets a `-2`, `-3` suffix. Manifest sits beside it as `.manifest.json`.

## 2026-10-03 — Retry policy lives in the runner, not the clients
Clients make one attempt and return status/body/error. Runner retries only HTTP 429/5xx, max 3
retries, exponential backoff (1s, 2s, 4s). Transport errors and other 4xx are not retried.

## 2026-10-03 — OpenRouter provider pinning and endpoint listing (sources)
Provider routing fields `provider.order`, `provider.allow_fallbacks=false`,
`provider.require_parameters=true` verified at https://openrouter.ai/docs/features/provider-routing
(fetched 2026-10-03). Endpoint listing: `GET /api/v1/models/{author}/{slug}/endpoints`. The docs
pages for it returned 404 via fetch, so the path and response shape (`data.endpoints[]` with
`provider_name`, `tag`, `quantization`, `pricing`, `supported_parameters`) were checked against a
live free GET for another model (`qwen/qwen3-32b`); no key, no spend. `order` takes the provider
name or slug as users pass it; `cprobe providers` prints both name and tag.
