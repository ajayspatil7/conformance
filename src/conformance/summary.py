"""Aggregate scored results into intervals and flag deviations from a reference."""

from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from dataclasses import dataclass

from .schema import Result
from .stats import Interval, bootstrap_ci, bootstrap_ratio_ci, is_flagged, wilson_interval

Key = tuple[str, str, str]  # (provider, case_id, metric)


@dataclass
class Metric:
    kind: str  # "proportion" | "mean" | "ratio"
    n: int
    estimate: float
    interval: Interval
    flagged: bool | None = None  # precomputed for "ratio" metrics


def _proportion(successes: int, n: int) -> Metric:
    return Metric("proportion", n, successes / n, wilson_interval(successes, n))


def _ok(r: Result) -> bool:
    return r.status_code == 200 and r.response is not None


def summarize(results: list[Result]) -> dict[Key, Metric]:
    """bool scores -> Wilson; numeric scores -> bootstrap CI of the mean.

    Also adds per (provider, case):
    - `http_ok`: share of requests that returned HTTP 200 (errors carry no scores, so without this
      a provider that fails every request would silently vanish from the summary);
    - `temp0_mode_agreement` (temperature 0) / `sampled_mode_agreement` (temperature > 0): share
      of repeats whose output (content + reasoning) equals the most common output. Low at
      temperature 0 = nondeterminism; high at temperature > 0 on long outputs = temperature
      ignored, fixed seed, or response caching. Both are compared with the reference.
    """
    groups: dict[Key, list] = defaultdict(list)
    for r in results:
        groups[(r.provider, r.case_id, "http_ok")].append(_ok(r))
        for k, v in r.score.items():
            if isinstance(v, (bool, int, float)):
                groups[(r.provider, r.case_id, k)].append(v)
    out: dict[Key, Metric] = {}
    for key, vals in groups.items():
        if all(isinstance(v, bool) for v in vals):
            out[key] = _proportion(sum(vals), len(vals))
        else:
            floats = [float(v) for v in vals]
            out[key] = Metric("mean", len(floats), sum(floats) / len(floats), bootstrap_ci(floats))
    out.update(output_agreement(results))
    return out


def output_fingerprint(r: Result) -> str | None:
    choices = (r.response or {}).get("choices") or []
    if not _ok(r) or not choices:
        return None
    msg = choices[0].get("message") or {}
    text = "\x00".join(
        [msg.get("content") or "", msg.get("reasoning") or "", json.dumps(msg.get("tool_calls"))]
    )
    return hashlib.sha256(text.encode()).hexdigest()


def request_sha(r: Result) -> str:
    return hashlib.sha256(json.dumps(r.request, sort_keys=True).encode()).hexdigest()


def request_conflicts(results: list[Result]) -> list[tuple[str, str, int]]:
    """(provider, case_id, n_variants) where one case was sent with different request bodies,
    e.g. results from before and after a case edit. Pooling those mixes different experiments."""
    variants: dict[tuple[str, str], set[str]] = defaultdict(set)
    for r in results:
        variants[(r.provider, r.case_id)].add(request_sha(r))
    return sorted((p, c, len(v)) for (p, c), v in variants.items() if len(v) > 1)


def output_agreement(results: list[Result]) -> dict[Key, Metric]:
    """Only identical requests are compared; with several request variants the largest is used."""
    groups: dict[Key, dict[str, list[str]]] = defaultdict(lambda: defaultdict(list))
    for r in results:
        temperature = r.request.get("temperature")
        fp = output_fingerprint(r)
        if fp is None or temperature is None:
            continue
        metric = "temp0_mode_agreement" if temperature == 0 else "sampled_mode_agreement"
        groups[(r.provider, r.case_id, metric)][request_sha(r)].append(fp)
    out: dict[Key, Metric] = {}
    for key, by_request in groups.items():
        fps = max(by_request.values(), key=len)
        if len(fps) >= 2:  # agreement of a single output is meaningless
            out[key] = _proportion(Counter(fps).most_common(1)[0][1], len(fps))
    return out


def completion_tokens(results: list[Result]) -> dict[tuple[str, str], list[float]]:
    out: dict[tuple[str, str], list[float]] = defaultdict(list)
    for r in results:
        tokens = (r.usage or {}).get("completion_tokens")
        if _ok(r) and isinstance(tokens, int):
            out[(r.provider, r.case_id)].append(float(tokens))
    return out


def length_ratios(results: list[Result], reference: str) -> dict[Key, Metric]:
    """Mean completion tokens of each provider / reference, per case, with a bootstrap CI.

    Flagging follows the project convention rather than "ratio CI excludes 1.0" (which is far
    stricter and flags trivial differences): flagged only when the provider's bootstrap CI of mean
    completion tokens does not overlap the reference's.
    """
    tokens = completion_tokens(results)
    out: dict[Key, Metric] = {}
    for (prov, case), vals in tokens.items():
        ref = tokens.get((reference, case))
        if prov == reference or not ref or sum(ref) == 0:
            continue
        est = (sum(vals) / len(vals)) / (sum(ref) / len(ref))
        out[(prov, case, "length_ratio")] = Metric(
            "ratio",
            len(vals),
            est,
            bootstrap_ratio_ci(vals, ref),
            flagged=is_flagged(bootstrap_ci(vals), bootstrap_ci(ref)),
        )
    return out


def flag_deviations(summary: dict[Key, Metric], reference: str) -> list[Key]:
    flagged = []
    for (prov, case, metric), m in summary.items():
        if prov == reference:
            continue
        if m.kind == "ratio":
            if m.flagged:
                flagged.append((prov, case, metric))
            continue
        ref = summary.get((reference, case, metric))
        if ref and is_flagged(m.interval, ref.interval):
            flagged.append((prov, case, metric))
    return sorted(flagged)
