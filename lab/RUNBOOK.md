# Lab runbook — fault-injection and reference endpoint

**For the human to execute. Agents must not run these or touch cloud resources.**
Commands are illustrative; check versions and prices before use. Stop instances when finished.

## 1. Reference endpoint (vLLM, known-good template and parsers)
On a single-GPU box with enough VRAM for a 27B model (e.g. one 80 GB GPU, or two 48 GB with TP=2):
```bash
pip install -U vllm
vllm serve Qwen/Qwen3.8-27B \
  --served-model-name qwen/qwen3.8-27b \
  --reasoning-parser qwen3 \
  --enable-auto-tool-choice --tool-call-parser hermes \
  --max-model-len 32768 --port 8000
```
Parser names must match the model card for Qwen3.8; confirm there first. Probe it with
`cprobe run --probe all --provider reference --base-url http://<host>:8000/v1 --price-in 0 --price-out 0 --yes`.

## 2. Fault injections (each is a separate server launch; label runs by fault)
| Fault | How | Expected probe signal |
|-------|-----|-----------------------|
| Broken tool parser | omit `--enable-auto-tool-choice`/`--tool-call-parser` | tool_calls: trigger failures, calls appear as text |
| Wrong chat template | `--chat-template <other-family.jinja>` | params: template leakage; reasoning: odd thinking |
| Ignored params | proxy that strips `temperature`, `stop`, `max_tokens` | params: stop/max_tokens/temp0 failures |
| Reasoning parser off | omit `--reasoning-parser` | reasoning: tokens 0 or `<think>` in content |
| Model substitution | serve a smaller/quantised variant under the same name | length ratio, effort gaps |

Record the exact launch command next to each run in `memory/FINDINGS.md`.

## 3. Cost control
Use spot/on-demand by the hour, set a billing alarm, and tear everything down after each session.
