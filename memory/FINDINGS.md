# Findings (dated, facts only)

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
