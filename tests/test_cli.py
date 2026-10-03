import httpx
from typer.testing import CliRunner

from conformance.cli import app

runner = CliRunner()


def test_dry_run_prints_estimate_without_network(monkeypatch, tmp_path):
    monkeypatch.setenv("CONFORMANCE_DATA_DIR", str(tmp_path))

    def boom(*a, **k):
        raise AssertionError("network used in dry run")

    monkeypatch.setattr(httpx.AsyncClient, "post", boom)
    monkeypatch.setattr(httpx.Client, "get", boom)
    r = runner.invoke(
        app, ["run", "--probe", "all", "--provider", "placeholder-a", "--repeats", "1", "--dry-run"]
    )
    assert r.exit_code == 0, r.output
    assert "worst-case $" in r.output and "no network calls" in r.output
    assert "TOTAL 60 requests" in r.output.replace(" x 1", "")
    for p in ("tool_calls", "reasoning", "params"):
        assert p in r.output


def test_default_is_dry_and_flags_exclusive(monkeypatch, tmp_path):
    monkeypatch.setenv("CONFORMANCE_DATA_DIR", str(tmp_path))
    r = runner.invoke(app, ["run", "--probe", "params", "--provider", "x"])
    assert r.exit_code == 0 and "DRY-RUN" in r.output
    r = runner.invoke(app, ["run", "--probe", "params", "--provider", "x", "--dry-run", "--yes"])
    assert r.exit_code != 0


def test_real_run_refused_without_prices(monkeypatch, tmp_path):
    monkeypatch.setenv("CONFORMANCE_DATA_DIR", str(tmp_path))
    r = runner.invoke(app, ["run", "--probe", "params", "--provider", "x", "--yes"])
    assert r.exit_code == 2


def test_run_refused_when_over_budget(monkeypatch, tmp_path):
    monkeypatch.setenv("CONFORMANCE_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("CONFORMANCE_BUDGET_USD", "0.001")
    r = runner.invoke(app, ["run", "--probe", "all", "--provider", "placeholder-a"])
    assert r.exit_code == 2


def test_case_filter_and_unknown_case(monkeypatch, tmp_path):
    monkeypatch.setenv("CONFORMANCE_DATA_DIR", str(tmp_path))
    r = runner.invoke(
        app,
        ["run", "--probe", "all", "--provider", "p", "--repeats", "1",
         "--case", "stop-digit", "--case", "train-low"],
    )  # fmt: skip
    assert r.exit_code == 0, r.output
    assert "TOTAL 2 requests" in r.output and "tool_calls" not in r.output
    r = runner.invoke(app, ["run", "--probe", "params", "--provider", "p", "--case", "nope"])
    assert r.exit_code != 0


def test_free_model_is_zero_cost_and_noted(monkeypatch, tmp_path):
    monkeypatch.setenv("CONFORMANCE_DATA_DIR", str(tmp_path))
    r = runner.invoke(
        app,
        ["run", "--probe", "all", "--provider", "ModelRun", "--model", "qwen/qwen3.8-27b:free",
         "--no-require-parameters"],
    )  # fmt: skip
    assert r.exit_code == 0, r.output
    assert "worst-case $0.0000; spent" in r.output and "free variant" in r.output
    assert "require_parameters=false" in r.output


def test_real_run_refused_without_key(monkeypatch, tmp_path):
    monkeypatch.setenv("CONFORMANCE_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    r = runner.invoke(
        app, ["run", "--probe", "params", "--provider", "x", "--model", "m:free", "--yes"]
    )
    assert r.exit_code == 2 and "OPENROUTER_API_KEY" in r.output


def test_aws_log_and_spend(monkeypatch, tmp_path):
    monkeypatch.setenv("CONFORMANCE_DATA_DIR", str(tmp_path))
    r = runner.invoke(app, ["aws-log", "--usd", "70", "--hours", "4", "--instance", "g6e.xlarge"])
    assert r.exit_code == 0 and "remaining $10.00" in r.output and "WARNING" in r.output
    r = runner.invoke(app, ["spend"])
    assert r.exit_code == 0
    assert "AWS credits:    used $70.00 of $80.00" in r.output
    assert "OpenRouter API: spent $0.0000 of $60.00" in r.output
    assert runner.invoke(app, ["aws-log", "--usd", "-1"]).exit_code != 0
