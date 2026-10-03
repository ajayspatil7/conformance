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
    r = runner.invoke(app, ["run", "--probe", "all", "--provider", "placeholder-a", "--dry-run"])
    assert r.exit_code == 0, r.output
    assert "TOTAL worst-case" in r.output and "no network calls" in r.output
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
