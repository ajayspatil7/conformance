"""Wilson intervals, bootstrap CIs, and overlap-based flagging."""

from __future__ import annotations

import math
import random
from collections.abc import Callable, Sequence

Interval = tuple[float, float]


def wilson_interval(successes: int, n: int, z: float = 1.96) -> Interval:
    """95% Wilson score interval for a proportion. n == 0 gives the vacuous (0, 1)."""
    if n <= 0:
        return (0.0, 1.0)
    if not 0 <= successes <= n:
        raise ValueError("successes must be within [0, n]")
    p = successes / n
    denom = 1 + z**2 / n
    centre = (p + z**2 / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z**2 / (4 * n**2)) / denom
    return (max(0.0, centre - half), min(1.0, centre + half))


def _mean(xs: Sequence[float]) -> float:
    return sum(xs) / len(xs)


def bootstrap_ci(
    values: Sequence[float],
    stat: Callable[[Sequence[float]], float] = _mean,
    n_boot: int = 2000,
    alpha: float = 0.05,
    seed: int = 0,
) -> Interval:
    """Percentile bootstrap CI (default 95%) of `stat`; deterministic for a given seed."""
    if not values:
        raise ValueError("bootstrap_ci needs at least one value")
    rng = random.Random(seed)
    n = len(values)
    stats = sorted(stat([values[rng.randrange(n)] for _ in range(n)]) for _ in range(n_boot))
    lo = stats[int((alpha / 2) * n_boot)]
    hi = stats[min(n_boot - 1, int((1 - alpha / 2) * n_boot))]
    return (lo, hi)


def intervals_overlap(a: Interval, b: Interval) -> bool:
    return a[0] <= b[1] and b[0] <= a[1]


def is_flagged(provider: Interval, reference: Interval) -> bool:
    """A provider is flagged only when its interval does not overlap the reference's."""
    return not intervals_overlap(provider, reference)
