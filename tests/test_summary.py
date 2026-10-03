from conformance.schema import Result
from conformance.summary import flag_deviations, length_ratios, request_conflicts, summarize


def res(
    provider, case, repeat, score=None, tokens=10, status=200, temperature=0.0, content="x",
    extra=None,
):  # fmt: skip
    return Result(
        case_id=case,
        probe="params",
        provider=provider,
        repeat=repeat,
        request={"temperature": temperature, **(extra or {})},
        status_code=status,
        response={"choices": [{"message": {"content": content}}]} if status == 200 else None,
        usage={"completion_tokens": tokens} if status == 200 else None,
        score=score or {},
    )


def test_http_ok_counts_failed_requests():
    rs = [res("A", "c", 0, {"passed": True}), res("A", "c", 1, status=404)]
    s = summarize(rs)
    assert s[("A", "c", "http_ok")].estimate == 0.5
    assert s[("A", "c", "passed")].n == 1


def test_temp0_mode_agreement():
    stable = [res("ref", "t", i, content="aa") for i in range(10)]
    noisy = [res("B", "t", i, content=f"x{i % 5}") for i in range(10)]
    s = summarize(stable + noisy)
    assert s[("ref", "t", "temp0_mode_agreement")].estimate == 1.0
    assert s[("B", "t", "temp0_mode_agreement")].estimate == 0.2
    assert ("B", "t", "temp0_mode_agreement") in flag_deviations(s, "ref")


def test_sampled_mode_agreement_catches_ignored_temperature():
    ref = [res("ref", "h", i, temperature=1.0, content=f"story {i}") for i in range(10)]
    frozen = [res("B", "h", i, temperature=1.0, content="same story") for i in range(10)]
    s = summarize(ref + frozen)
    assert s[("ref", "h", "sampled_mode_agreement")].estimate == 0.1
    assert s[("B", "h", "sampled_mode_agreement")].estimate == 1.0
    assert ("ref", "h", "temp0_mode_agreement") not in s
    assert ("B", "h", "sampled_mode_agreement") in flag_deviations(s, "ref")


def test_agreement_needs_two_successful_outputs():
    s = summarize([res("A", "c", 0, content="a"), res("A", "c", 1, status=500)])
    assert ("A", "c", "temp0_mode_agreement") not in s


def test_length_ratio_and_flagging():
    spread = [(i * 7) % 40 for i in range(10)]  # realistic run-to-run variation
    ref = [res("ref", "c", i, tokens=100 + s) for i, s in enumerate(spread)]
    same = [res("A", "c", i, tokens=97 + s) for i, s in enumerate(spread)]
    short = [res("B", "c", i, tokens=40 + s) for i, s in enumerate(spread)]
    errors = [res("C", "c", i, status=500) for i in range(3)]
    ratios = length_ratios(ref + same + short + errors, "ref")
    assert abs(ratios[("A", "c", "length_ratio")].estimate - 1.0) < 0.05
    assert ratios[("B", "c", "length_ratio")].estimate < 0.6
    assert ("C", "c", "length_ratio") not in ratios
    assert ("ref", "c", "length_ratio") not in ratios
    flags = flag_deviations(ratios, "ref")
    assert ("B", "c", "length_ratio") in flags and ("A", "c", "length_ratio") not in flags


def test_agreement_only_compares_identical_requests():
    old = [res("A", "c", i, temperature=0.7, content="thinking on") for i in range(2)]
    new = [
        res("A", "c", i, temperature=0.7, content="off", extra={"reasoning": {"effort": "none"}})
        for i in range(3)
    ]
    s = summarize(old + new)
    m = s[("A", "c", "sampled_mode_agreement")]
    assert m.n == 3 and m.estimate == 1.0  # largest variant only, not a 2-vs-3 mix
    assert request_conflicts(old + new) == [("A", "c", 2)]
    assert request_conflicts(new) == []
