from backend.services.spc_stability import (
    DEFAULT_STABILITY_RULES,
    evaluate_stability,
)


def test_stable_process_returns_stable_true():
    # 交替繞中心線的資料，不觸發任何準則
    avgs = [10.0, 10.2, 9.8, 10.1, 9.9, 10.2, 9.8, 10.1, 9.9, 10.0]
    result = evaluate_stability(avgs, x_cl=10.0, x_ucl=10.9, x_lcl=9.1)
    assert result["evaluated"] is True
    assert result["stable"] is True
    assert result["violations"] == []
    assert result["rules_used"] == DEFAULT_STABILITY_RULES


def test_point_beyond_limits_marks_unstable():
    avgs = [10.0, 10.2, 9.8, 10.1, 12.0, 10.2, 9.8, 10.1, 9.9, 10.0]
    result = evaluate_stability(avgs, x_cl=10.0, x_ucl=10.9, x_lcl=9.1)
    assert result["stable"] is False
    assert result["violations"][0]["index"] == 4
    assert result["violations"][0]["rule"] == "beyond_limits"


def test_run_9_same_side_marks_unstable():
    avgs = [10.1] * 9 + [9.9]
    result = evaluate_stability(avgs, x_cl=10.0, x_ucl=10.9, x_lcl=9.1)
    assert result["stable"] is False
    assert any(v["rule"] == "run_9_same_side" for v in result["violations"])


def test_disabled_rule_is_not_applied():
    avgs = [10.1] * 9 + [9.9]
    result = evaluate_stability(
        avgs, x_cl=10.0, x_ucl=10.9, x_lcl=9.1,
        enabled_rules=["beyond_limits"],
    )
    assert result["stable"] is True
    assert result["rules_used"] == ["beyond_limits"]


def test_insufficient_data_returns_not_evaluated():
    result = evaluate_stability([10.0, 10.1], x_cl=10.0, x_ucl=10.9, x_lcl=9.1)
    assert result["evaluated"] is False
    assert result["stable"] is None
