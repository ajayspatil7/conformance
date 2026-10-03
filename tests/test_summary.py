from conformance.schema import Result
from conformance.summary import flag_deviations, length_ratios, summarize


def res(provider, case, repeat, score=None, tokens=10, status=200, temperature=0.0):
    return Result(
        case_id=case,
        probe="params",
        provider=provider,
        repeat=repeat,
        request={"temperature": temperature},
        status_code=status,
        response={"choices": []} if status == 200 else None,
        usage={"completion_tokens": tokens} if status == 200 else None,
        score=score or {},
    )


def test_http_ok_counts_failed_requests():
    rs = [res("A", "c", 0, {"passed": True}), res("A", "c", 1, status=404)]
    s = summarize(rs)
    assert s[("A", "c", "http_ok")].estimate == 0.5
    assert s[("A", "c", "passed")].n == 1


def test_temp0_mode_agreement():
    stable = [res("ref", "t", i, {"output_sha": "aa"}) for i in range(10)]
    noisy = [res("B", "t", i, {"output_sha": f"x{i % 5}"}) for i in range(10)]
    hot = [res("B", "h", i, {"output_sha": f"y{i}"}, temperature=0.7) for i in range(3)]
    s = summarize(stable + noisy + hot)
    assert s[("ref", "t", "temp0_mode_agreement")].estimate == 1.0
    assert s[("B", "t", "temp0_mode_agreement")].estimate == 0.2
    assert ("B", "h", "temp0_mode_agreement") not in s  # only temperature-0 requests count
    assert ("B", "t", "temp0_mode_agreement") in flag_deviations(s, "ref")


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
