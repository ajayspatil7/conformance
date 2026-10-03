# Report #1 — Qwen/Qwen3.8-27B provider conformance (draft)

Ships Saturday 10 October 2026. Status: harness built; no provider data collected yet.

## Scope
Three probes: tool calling, reasoning-effort/thinking-control passthrough, parameter and
chat-template sanity. Text only.

## Method
Pinned single-provider requests via OpenRouter (fallbacks off, `require_parameters`), compared with a
reference endpoint. Proportions: 95% Wilson intervals. Token counts: bootstrap 95% CIs. A provider is
flagged only when its interval does not overlap the reference's. Raw JSONL and manifests: `data/runs/`.

## Results
_TBD._

## Wording
Failures are described as bugs or deviations from the reference. We make no claim about intent.
