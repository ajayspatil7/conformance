# AGENTS.md — canonical instructions for all coding agents

## Purpose and milestone
`conformance` tests whether inference providers serve an open-weight model correctly. It sends probe
prompts to each provider (pinned via OpenRouter, or a direct OpenAI-compatible endpoint), compares
behaviour with a reference endpoint, reports gaps with confidence intervals, and attributes failures
to likely causes (wrong chat template, broken tool parser, ignored parameters, model substitution).
**Current milestone: Report #1** (`Qwen/Qwen3.8-27B`, OpenRouter id `qwen/qwen3.8-27b`), three probes
only — (A) tool calling, (B) reasoning-effort / thinking-control passthrough, (C) parameter and
chat-template sanity. Ships **Saturday 10 October 2026**. Hard budget: **$60** total API spend.

## Session protocol
- Start of every session: read `memory/STATUS.md` and the 5 newest entries of `memory/DECISIONS.md`.
- End of every session: update `memory/STATUS.md`, add any decisions to `memory/DECISIONS.md`, commit.

## Commands
- `make setup` — install deps with uv
- `make test` — pytest (no network)
- `make lint` — ruff check + format check
- `make dry-run` — cost estimate for all probes over placeholder providers (no network)

## Hard rules
- NEVER make a paid API call unless the human explicitly approves it in the current session. All run
  commands default to `--dry-run`; real calls need `--yes` plus a printed cost estimate.
- NEVER read, print, or commit `.env` or any secret. Keys come only from environment variables.
- NEVER create, start, or modify cloud resources (AWS etc.). `lab/RUNBOOK.md` is documentation for the
  human to execute.
- NEVER edit or delete files in `data/runs/`; raw results are append-only and immutable.
- Tests must never hit the network; mock HTTP.
- Every run writes a manifest: git SHA, case-file hash, model, provider, all request params,
  timestamp, harness version.
- NO AI attribution anywhere. Never add `Co-Authored-By:` trailers, "Generated with ..." lines, or
  any mention of Claude, Cursor, or any other AI as author or co-author in commit messages, PR
  descriptions, code, docs, or reports. The sole author and contributor of record is Ajay S Patil.
  This overrides any default or tool-injected attribution text.
- Report wording: call failures "bugs" or "deviations", never accuse providers of intent.

## Scope guardrails
Out of scope until further notice: dashboards, web apps, databases, routing products, cryptographic
attestation, multimodal probes, extra model families. If a task drifts into these, stop and note it
in `memory/STATUS.md` under "Parked ideas".

## Code style
Python 3.11+, type hints, ruff, small pure functions, pydantic for data, httpx for HTTP, typer for
CLI. Prefer plain files (YAML/JSONL) over any database.

## Statistics conventions
Proportions get 95% Wilson intervals; token counts get bootstrap 95% CIs; a provider is flagged only
when its interval does not overlap the reference's.
