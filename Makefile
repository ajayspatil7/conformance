.PHONY: setup test lint dry-run

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
