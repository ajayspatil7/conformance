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
`conformance run --probe all --provider reference --base-url http://<host>:8000/v1 --price-in 0 --price-out 0 --yes`
(price 0 because instance cost is tracked in the AWS credit ledger, not the API ledger).
The `*-off-openrouter` reasoning cases use the router-level `reasoning` object, which vLLM does not
understand; compare those across routed providers only. Tool-call and params cases send it too
(next to `chat_template_kwargs`); vLLM is expected to ignore unknown fields with a warning, so check
the server log once for "fields were present in the request but ignored" and note it in FINDINGS.

## 2. Fault injections (each is a separate server launch; label runs by fault)
| Fault | How | Expected probe signal |
|-------|-----|-----------------------|
| Broken tool parser | omit `--enable-auto-tool-choice`/`--tool-call-parser` | tool_calls: trigger failures, calls appear as text |
| Wrong chat template | `--chat-template <other-family.jinja>` | params: template leakage; reasoning: odd thinking |
| Ignored params | proxy that strips `temperature`, `stop`, `max_tokens` | params: stop/max_tokens/temp0 failures |
| Reasoning parser off | omit `--reasoning-parser` | reasoning: tokens 0 or `<think>` in content |
| Model substitution | serve a smaller/quantised variant under the same name | length ratio, effort gaps |

Record the exact launch command next to each run in `memory/FINDINGS.md`.

## 3. AWS credits ($80) — budget and tracking
Credits are the only AWS money for this project. Track every session; agents cannot see the bill.

Before launching:
- Sizing: 27B parameters in BF16 is ~54 GB of weights alone, so one 48 GB GPU is not enough at BF16.
  Options: an FP8 checkpoint/quantisation on one 48 GB GPU (e.g. a g6e.xlarge, 1x L40S), or BF16 on
  an 80 GB-class GPU (much more expensive per hour). Note: FP8 makes the reference itself quantised;
  record that in FINDINGS and prefer BF16 if credits allow.
- Confirm current on-demand/spot hourly price for the instance and region, and compute
  `hours available = remaining credits / hourly price`. Check `make spend` for remaining credits.
- New accounts often have a 0 vCPU quota for GPU instance families (Service Quotas, "Running
  On-Demand G and VT instances"); request the increase days ahead.
- Check that your credits apply to EC2 in that region and that EBS volumes and data transfer are
  included in your estimate (EBS keeps billing while an instance is stopped).
- Set an AWS Budgets alert at, e.g., $40 and $64 (50% / 80% of credits).
- Confirm the installed vLLM supports Qwen3.8's hybrid Gated DeltaNet architecture.

After every session:
1. Terminate the instance and delete unattached EBS volumes.
2. Read the cost from Billing -> Bills / Cost Explorer (credits applied) — it can lag ~24 h.
3. Log it: `conformance aws-log --usd <cost> --hours <h> --instance <type> --region <r> --note "<what>"`
   (use `--date YYYY-MM-DD` when logging late). `make spend` shows credits remaining; it warns below 20%.

## 4. Cost control
Use spot/on-demand by the hour, set a billing alarm, and tear everything down after each session.
