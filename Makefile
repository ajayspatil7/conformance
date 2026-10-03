.PHONY: setup test lint dry-run smoke-free smoke-gateway spend

setup:
	uv sync

test:
	uv run pytest -q

lint:
	uv run ruff check .
	uv run ruff format --check .

# No network, no spend: prints a cost estimate for all probes over placeholder providers.
dry-run:
	uv run conformance run --probe all --provider placeholder-a --provider placeholder-b \
		--provider placeholder-c --repeats 5 --dry-run

# $0 smoke run against the free variant (one endpoint, ModelRun, which lacks top_k, hence
# --no-require-parameters). 7 requests; free tier allows 20/min and 50/day.
# The human runs this with the key exported, e.g. `set -a; . ./.env; set +a; make smoke-free`.
SMOKE_CASES = --case should-call-weather-paris --case continuation-weather-answer \
	--case train-low --case train-off-kwargs --case train-off-openrouter \
	--case stop-digit --case leak-thinking-on-short
smoke-free:
	@test -n "$$OPENROUTER_API_KEY" || { echo "OPENROUTER_API_KEY is not exported"; exit 1; }
	uv run conformance run --probe all --model qwen/qwen3.8-27b:free --provider ModelRun \
		--no-require-parameters --repeats 1 $(SMOKE_CASES) --yes

# Paid but tiny: the same 7 cases via Vercel AI Gateway pinned to deepinfra (also on OpenRouter),
# worst case ~$0.03 of the $5 gateway budget. Prices: gateway endpoint listing, 2026-10-03.
# Human runs it with the key exported: `set -a; . ./.env; set +a; make smoke-gateway`.
smoke-gateway:
	@test -n "$$AI_GATEWAY_API_KEY" || { echo "AI_GATEWAY_API_KEY is not exported"; exit 1; }
	uv run conformance run --probe all --route gateway --provider deepinfra \
		--price-in 0.15 --price-out 1.875 --repeats 1 $(SMOKE_CASES) --yes

spend:
	uv run conformance spend
