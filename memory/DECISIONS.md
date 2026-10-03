# Decisions (newest first)

## 2026-10-03 — Why providers are tested at all, and what self-hosting is for
The project's question is "do *providers* serve Qwen3.8-27B correctly?" — what a user of DeepInfra,
Novita, etc. actually receives. Providers are the system under test, so no amount of self-hosting
replaces calling them. Self-hosting on AWS is the *reference* (a known configuration to compare
against) and the *lab* (inject one fault at a time — wrong template, missing parser, stripped
params — to learn each fault's signature, which is how provider failures get attributed). It is not
automatically ground truth: the reference is checked against the model card's settings and its own
config is recorded. Budget split follows: providers $60 (OpenRouter) + $5 (AI Gateway cross-check),
reference/lab $80 (AWS credits, a few GPU-hours).

## 2026-10-03 — Vercel AI Gateway as a cross-check route, not the main route
Gateway lists 7 providers for alibaba/qwen3.8-27b (6 also on OpenRouter) and does not list `top_p`,
`top_k`, `presence_penalty`, `reasoning_effort`, or `chat_template_kwargs`, so it cannot carry the
official sampling settings as a primary route. Its value is attribution: the same upstream provider
reached via two routers separates router bugs from provider bugs. Pinning via
`providerOptions.gateway.only=[slug]`, which restricts fallbacks too (docs:
https://vercel.com/docs/ai-gateway/models-and-providers/provider-filtering-and-ordering). Results are
named `gateway-<slug>` so routes never mix in stats. Separate $5 hard-capped ledger.

## 2026-10-03 — Verify who served every request (`provider_match`)
OpenRouter returns `provider`; AI Gateway reports `gateway.routing.finalProvider` in provider
metadata. Each result stores `served_provider`, and `provider_match` (case/punctuation-insensitive,
prefix-tolerant: "mancer" ~ "Mancer 2") is scored as a proportion, so silent re-routing shows up as
a deviation instead of contaminating other metrics. Router-reported cost is preferred for the ledger.

## 2026-10-03 — Probes A and C turn thinking off with both switches
The smoke run showed `chat_template_kwargs.enable_thinking=false` alone did not stop reasoning via
OpenRouter, while `reasoning: {effort: none}` did. A and C now send both, so tool-parser and
parameter results are not confounded by thinking. Probe B keeps the switches in separate cases,
because which switch works is its measurement.

## 2026-10-03 — Length-ratio flagging uses CI overlap, not "ratio CI excludes 1"
`length_ratio` (provider mean completion tokens / reference) is reported with a bootstrap ratio CI,
but flagged only when the provider's and reference's mean-token CIs do not overlap, matching the
project convention. "Ratio CI excludes 1.0" flagged 1% differences on low-variance data.

## 2026-10-03 — temp0 stability = share of repeats matching the modal output
For temperature-0 requests, `temp0_mode_agreement` = (count of most common output_sha) / repeats,
with a Wilson interval, compared with the reference like any proportion. `http_ok` added so a
provider that errors on every request is visible instead of silently missing from the summary.

## 2026-10-03 — Case set expanded to 20 per probe
tool_calls: 6 tools, 6 should-call / 5 should-not / 5 choose-among-6 / 4 continuations, with
expected-argument checks; max_tokens 512 -> 2048 so a dropped `enable_thinking=false` shows up as
`truncated` rather than a parser failure. reasoning: 4 questions x 5 controls (`reasoning_effort`
low/medium/xhigh; off via `chat_template_kwargs`; off via OpenRouter `reasoning: {effort: none}`,
documented at https://openrouter.ai/docs/use-cases/reasoning-tokens), answer = last number in the
content. params: 5 each of stop / temp0 / max_tokens / leakage (2 leakage cases with thinking on).

## 2026-10-03 — :free variant for $0 smoke tests only; key never read by agents
`qwen/qwen3.8-27b:free` is one fp4 endpoint (ModelRun) without `top_k` support, so smoke runs use
`--no-require-parameters` (recorded in every request's `provider` block). The harness prices
`:free` models at $0 and caps them at 20 req/min (limits: 20/min, 50/day or 1000/day after $10 of
purchases; https://openrouter.ai/docs/api-reference/limits). Free results are never report data.
The key lives in `.env`, which agents must not read, so the human runs `make smoke-free` with the
key exported.

## 2026-10-03 — AWS credits ($80) tracked in a separate local ledger
`data/aws_spend.jsonl` with `conformance aws-log` (human-entered from the Billing console) and
`conformance spend` for both budgets. Agents still never touch AWS, including billing APIs.
Reference-endpoint runs use `--price-in 0 --price-out 0` so instance cost is not double-counted.

## 2026-10-03 — One name: `conformance`
Package renamed `conformance_probe` -> `conformance`, CLI `cprobe` -> `conformance`, env vars
`CPROBE_*` -> `CONFORMANCE_*`. Remote is https://github.com/ajayspatil7/conformance (`main`); its
LICENSE-only initial commit was merged (unrelated histories, identical LICENSE), no force push.
No-AI-attribution rule widened to all AI tools and all artifacts; `includeCoAuthoredBy: false` set
in `.claude/settings.json`.

## 2026-10-03 — No AI co-authors or attribution, ever
Owner instruction: the only author/contributor of record is Ajay S Patil. No `Co-Authored-By`
trailers, "Generated with ..." lines, or AI mentions as author in commits, PRs, code, or docs.
Recorded in AGENTS.md, CLAUDE.md, the Cursor rule, and `/wrap-up`. Overrides tool defaults.

## 2026-10-03 — Layout: data/, reports/, lab/, tests/ at repo root
The spec's tree was ambiguous about nesting; only `cases/`, `probes/`, `clients/` live inside
`src/conformance/`. Cases ship inside the package so `conformance` works from any directory.

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
name or slug as users pass it; `conformance providers` prints both name and tag.
