import pytest

from conformance.budget import BudgetExceeded, Ledger, actual_cost, estimate_cost
from conformance.schema import Case


def _case(max_tokens: int) -> Case:
    return Case(id="c", probe="p", kind="k", messages=[], params={"max_tokens": max_tokens})


def test_estimate_scales_with_repeats_and_tokens():
    # (600*1 + 1000*2)/1e6 per request, 3 requests
    est = estimate_cost([_case(1000)], repeats=3, price_in_per_m=1.0, price_out_per_m=2.0)
    assert est == pytest.approx(2600 * 3 / 1e6)


def test_actual_cost_prefers_reported():
    assert actual_cost({"cost": 0.5, "prompt_tokens": 1}, 1, 1) == 0.5
    assert actual_cost({"prompt_tokens": 1_000_000, "completion_tokens": 0}, 2.0, 9.0) == 2.0
    assert actual_cost(None, 1, 1) == 0.0


def test_ledger_refuses_over_budget(tmp_path):
    ledger = Ledger(tmp_path / "spend.jsonl", cap_usd=1.0)
    ledger.record("r", "p", {"prompt_tokens": 1}, 0.75)
    assert ledger.spent() == pytest.approx(0.75)
    ledger.check(0.25)
    with pytest.raises(BudgetExceeded):
        ledger.check(0.26)


def test_aws_ledger(tmp_path):
    aws = Ledger(tmp_path / "aws.jsonl", cap_usd=80.0)
    aws.record_aws("2026-10-04", 3.5, 2.0, "g6e.xlarge", "us-east-1", "reference")
    aws.record_aws("2026-10-05", 1.5, None, None, None)
    assert aws.spent() == pytest.approx(5.0) and aws.remaining() == pytest.approx(75.0)
    assert aws.rows()[0]["instance"] == "g6e.xlarge"
    with pytest.raises(ValueError):
        aws.record_aws("2026-10-05", -1, None, None, None)
