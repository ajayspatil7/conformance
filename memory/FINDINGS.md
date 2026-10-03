# Findings (dated, facts only)

## 2026-10-03 — `make smoke-free`: qwen/qwen3.8-27b:free via ModelRun (fp4), n=1 per case, $0
Smoke data only (free variant, `require_parameters=false`, one repeat); not report data.
Files: `data/runs/2026-10-03_{tool_calls,reasoning,params}_ModelRun.jsonl` (+ manifests).
- Response shape matches the harness's assumptions: `usage.completion_tokens_details.reasoning_tokens`
  present; `usage.cost` present (0); reasoning text in `message.reasoning` and `reasoning_details`
  (`reasoning.text`); tool calls in OpenAI format with `finish_reason: "tool_calls"`. The body also
  carries `provider` ("ModelRun") and `choices[].native_finish_reason`.
- All 7 requests: HTTP 200, 1 attempt, latency 0.8–11.6 s.
- `chat_template_kwargs.enable_thinking=false` did not stop reasoning on this route: reasoning
  tokens were 89 (train-off-kwargs), 27 (stop-digit), 27 and 31 (the two tool_calls cases).
  Whether OpenRouter or the provider drops it cannot be told from one endpoint.
- `reasoning: {effort: "none"}` did stop it: 0 reasoning tokens (train-off-openrouter).
- stop-digit: `stop: ["5"]` was not applied; content was "1, 2, 3, 4, 5, 6, 7, 8, 9, 10",
  finish_reason "stop" (ModelRun lists `stop` as supported).
- train-low: 93 reasoning tokens, answer 205 correct. Both tool_calls cases passed (correct call
  with `{"city":"Paris"}`; text answer after the tool result). No template-token leakage seen.

## 2026-10-03 — Vercel AI Gateway listing for alibaba/qwen3.8-27b (free listing API, no inference)
- 7 providers: alibaba, cerebras, deepinfra, novita, parasail (fp8), runinfra (bf16), wafer.
  Six also serve the model on OpenRouter; runinfra does not appear on OpenRouter.
- Every endpoint's `supported_parameters` is max_tokens, temperature, stop, tools, tool_choice,
  reasoning, include_reasoning (+ response_format/structured_outputs for some). `top_p`, `top_k`,
  `presence_penalty`, `reasoning_effort`, `chat_template_kwargs` are not listed.
- Reasoning efforts listed for the model: none, low, medium, xhigh.

## 2026-10-03 — OpenRouter endpoint metadata for qwen/qwen3.8-27b (free listing API, no inference)
- 17 paid endpoints listed: Reka, Wafer, DekaLLM, Darkbloom, Ionstream, Phala, DeepInfra, Mancer 2,
  AkashML, Parasail, Chutes, CoreWeave, Novita, Alibaba, Cloudflare, Venice, Cerebras.
- Declared quantisation: bf16 (DeepInfra), fp16 (Cerebras), fp8 (Ionstream, Mancer 2, AkashML,
  Parasail, Chutes, CoreWeave, Venice), fp4 (Darkbloom); "unknown" for Reka, Wafer, DekaLLM, Phala,
  Novita, Alibaba, Cloudflare.
- `top_k` (part of the official sampling settings) is not in `supported_parameters` for DekaLLM,
  Ionstream, or the free endpoint; with `require_parameters=true` those endpoints are not routable
  for cases that send `top_k`.
- `chat_template_kwargs` is not listed in any endpoint's `supported_parameters`; whether it is
  forwarded is what the `*-off-kwargs` reasoning cases measure.
- Every endpoint lists `reasoning` and `reasoning_effort`.
- Context length 262144 for most; Phala, Novita, Alibaba list 1000000; Cerebras lists 65536.
  Max completion tokens range from 32768 (Darkbloom, Cerebras) to 262144 (Phala).
- `qwen/qwen3.8-27b:free` has a single endpoint: ModelRun, fp4, $0.
