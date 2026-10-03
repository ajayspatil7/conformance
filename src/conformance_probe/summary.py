"""Aggregate scored results into intervals and flag deviations from a reference."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from .schema import Result
from .stats import Interval, bootstrap_ci, is_flagged, wilson_interval


@dataclass
class Metric:
    kind: str  # "proportion" | "mean"
    n: int
    estimate: float
    interval: Interval


def summarize(results: list[Result]) -> dict[tuple[str, str, str], Metric]:
    """Keyed by (provider, case_id, metric). bool -> Wilson; numbers -> bootstrap CI of mean."""
    groups: dict[tuple[str, str, str], list] = defaultdict(list)
    for r in results:
        for k, v in r.score.items():
            if isinstance(v, (bool, int, float)):
                groups[(r.provider, r.case_id, k)].append(v)
    out: dict[tuple[str, str, str], Metric] = {}
    for key, vals in groups.items():
        if all(isinstance(v, bool) for v in vals):
            s = sum(vals)
            out[key] = Metric("proportion", len(vals), s / len(vals), wilson_interval(s, len(vals)))
        else:
            floats = [float(v) for v in vals]
            out[key] = Metric("mean", len(floats), sum(floats) / len(floats), bootstrap_ci(floats))
    return out


def flag_deviations(
    summary: dict[tuple[str, str, str], Metric], reference: str
) -> list[tuple[str, str, str]]:
    flagged = []
    for (prov, case, metric), m in summary.items():
        ref = summary.get((reference, case, metric))
        if prov != reference and ref and is_flagged(m.interval, ref.interval):
            flagged.append((prov, case, metric))
    return sorted(flagged)
