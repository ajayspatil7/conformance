# STATUS — 2026-10-03

## Built
- Repo scaffold: AGENTS.md (canonical), CLAUDE.md, Cursor rule, Claude settings and commands.
- Harness: config, schema, stats (Wilson/bootstrap), budget ledger, OpenRouter + OpenAI-compat
  clients, async runner (retries, JSONL, manifest, budget halt), summary/flagging, `conformance` CLI.
- Probes A/B/C with 4 example cases each and working scorers.
- Naming unified to `conformance` (package, CLI, `CONFORMANCE_*` env vars); pushed to
  https://github.com/ajayspatil7/conformance `main`.
- 31 offline tests; `make lint`, `make test`, `make dry-run` pass. Spend to date: $0.00.

## Stubbed / not yet validated
- No real API call has ever been made; response shapes (reasoning_tokens location, tool_calls
  format, `usage.cost`) are assumed from the OpenAI schema and must be checked on first real run.
- Cases are 4 toy examples per probe; prompts need broadening for statistical power.
- temp0 stability (compare `output_sha` across repeats) and length-ratio-vs-reference are not yet
  aggregated by `conformance stats`.
- Cause attribution (template vs parser vs ignored params vs substitution) not implemented.
- `lab/RUNBOOK.md` and `reports/report-1/README.md` are drafts.

## Next 3 tasks
1. Human approves a small paid smoke run (1 provider, repeats=1, ~cents); verify real response shapes.
2. Add temp0-stability and length-ratio aggregation to `stats`; expand cases to ~20 per probe.
3. Stand up the reference endpoint per `lab/RUNBOOK.md` (human), then run the full provider sweep.

## Blockers
- Needs `OPENROUTER_API_KEY` in the environment and human approval for any paid call.
- Reference endpoint (self-hosted vLLM) must be started by the human.

## Parked ideas
(none)
