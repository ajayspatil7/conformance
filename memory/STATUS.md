# STATUS — 2026-10-03

## Built
- Repo scaffold: AGENTS.md (canonical), CLAUDE.md, Cursor rule, Claude settings and commands.
- Harness: config, schema, stats (Wilson, bootstrap, bootstrap ratio), budget ledgers, OpenRouter +
  OpenAI-compat clients, async runner (retries, rate limit, JSONL, manifest, budget halt),
  summary/flagging, `conformance` CLI (`providers`, `run`, `stats`, `spend`, `aws-log`).
- Probes A/B/C with **20 cases each** and working scorers (tool args match, truncation, answer check).
- `stats` aggregates `temp0_mode_agreement`, `length_ratio` vs reference, and `http_ok`.
- `:free` smoke support (`make smoke-free`, $0, 20 rpm cap) and AWS credit ledger ($80).
- Routes: `openrouter` (default), `gateway` (Vercel AI Gateway, $5 hard cap, `make smoke-gateway`),
  `direct` (self-hosted; sends no key). Every result records `served_provider`; `provider_match`
  flags re-routing. Probes A/C turn thinking off with both switches.
- 71 offline tests; `make lint`, `make test`, `make dry-run` pass.
- Spend: OpenRouter $0.00 of $60; AWS credits $0.00 of $80 used.
- Pushed to https://github.com/ajayspatil7/conformance `main` up to the rename; later commits local.

## Stubbed / not yet validated
- Response shapes verified by `make smoke-free` (7 requests, $0): all assumptions held.
- Thinking-off via `chat_template_kwargs` was not honoured on the free route; A/C now also send
  `reasoning: {effort: none}` (not yet re-run).
- AI Gateway response shape (where provider metadata and cost land in a raw chat-completions body)
  is unconfirmed; the extractor checks the documented and plausible keys. `make smoke-gateway`
  will confirm.
- Cause attribution (template vs parser vs ignored params vs substitution) not implemented.
- Effort-ordering check (low < medium < xhigh reasoning tokens) is done by eye in the report, not code.
- `lab/RUNBOOK.md` and `reports/report-1/README.md` are drafts.

## Next 3 tasks
1. Human: `set -a; . ./.env; set +a; make smoke-free smoke-gateway` (~$0.03); then check
   gateway metadata/cost extraction and that thinking is off in A/C cases.
2. Human: approve a small paid OpenRouter run (2–3 endpoints incl. deepinfra, repeats=3) — pairs
   with the gateway smoke to test whether the kwargs drop is router- or provider-side.
3. Human: stand up the reference endpoint per `lab/RUNBOOK.md` (log AWS usage with `aws-log`),
   then run the full sweep (worst case $34 at 5 repeats, 17 endpoints).

## Blockers
- `OPENROUTER_API_KEY` is in `.env`, which agents may not read: the human must export it and run.
- Reference endpoint (AWS) must be started by the human; GPU quota may need a request.

## Parked ideas
(none)
