import pytest

from conformance_probe.stats import bootstrap_ci, intervals_overlap, is_flagged, wilson_interval


def test_wilson_known_value():
    lo, hi = wilson_interval(8, 10)
    assert lo == pytest.approx(0.4902, abs=1e-3)
    assert hi == pytest.approx(0.9433, abs=1e-3)


def test_wilson_edges():
    assert wilson_interval(0, 0) == (0.0, 1.0)
    lo, hi = wilson_interval(10, 10)
    assert hi == 1.0 and lo > 0.6
    assert wilson_interval(0, 10)[0] == 0.0
    with pytest.raises(ValueError):
        wilson_interval(11, 10)


def test_bootstrap_contains_mean_and_is_deterministic():
    xs = [100, 110, 90, 105, 95, 102, 98]
    lo, hi = bootstrap_ci(xs, seed=1)
    assert lo <= sum(xs) / len(xs) <= hi
    assert bootstrap_ci(xs, seed=1) == (lo, hi)
    assert bootstrap_ci([5, 5, 5]) == (5, 5)


def test_flagging_requires_non_overlap():
    assert intervals_overlap((0.1, 0.5), (0.4, 0.9))
    assert not is_flagged((0.1, 0.5), (0.4, 0.9))
    assert is_flagged((0.0, 0.2), (0.5, 0.9))
