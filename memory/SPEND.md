# Spend

Two separate budgets. `make spend` (or `conformance spend`) prints both from the ledgers.

## OpenRouter API — cap $60.00 (hard, enforced by the harness)
Source of truth: `data/spend.jsonl` (appended by the runner from actual `usage`).
`:free` variant calls cost $0 and are logged at $0.

| Date | Run | Provider | USD | Cumulative |
|------|-----|----------|-----|------------|
| —    | —   | —        | 0.00 | 0.00 |

Planning estimate (2026-10-03, live endpoint prices, worst case = every request hits max_tokens):
full sweep of all 60 cases over 17 paid endpoints = $33.94 at 5 repeats, $20.36 at 3 repeats.

## AWS credits — $80.00 (reference endpoint + fault-injection lab, human-operated)
Source of truth: `data/aws_spend.jsonl`, appended by the human with
`conformance aws-log --usd <cost> --hours <h> --instance <type> --region <r> --note "<what>"`
using numbers from the AWS Billing console. Agents never query AWS.

| Date | Instance | Hours | USD | Remaining |
|------|----------|-------|-----|-----------|
| —    | —        | —     | 0.00 | 80.00 |
