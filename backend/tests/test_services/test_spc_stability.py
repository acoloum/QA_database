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


def test_alternating_14_marks_unstable_when_rule_enabled():
    # 14點交替上升下降（未落在管制界限外，且需明確啟用該準則才會觸發）
    avgs = [10.2, 9.8, 10.2, 9.8, 10.2, 9.8, 10.2, 9.8,
            10.2, 9.8, 10.2, 9.8, 10.2, 9.8]
    result = evaluate_stability(
        avgs, x_cl=10.0, x_ucl=10.9, x_lcl=9.1,
        enabled_rules=["alternating_14"],
    )
    assert result["stable"] is False
    assert any(v["rule"] == "alternating_14" for v in result["violations"])


def test_eight_beyond_1s_both_marks_unstable_when_rule_enabled():
    # 連續8點皆落在 Zone C（±1σ）之外（需明確啟用該準則才會觸發）
    avgs = [10.5, 9.5, 10.5, 9.5, 10.5, 9.5, 10.5, 9.5]
    result = evaluate_stability(
        avgs, x_cl=10.0, x_ucl=10.9, x_lcl=9.1,
        enabled_rules=["eight_beyond_1s_both"],
    )
    assert result["stable"] is False
    assert any(v["rule"] == "eight_beyond_1s_both" for v in result["violations"])


def test_two_new_rules_not_in_default_set():
    assert "alternating_14" not in DEFAULT_STABILITY_RULES
    assert "eight_beyond_1s_both" not in DEFAULT_STABILITY_RULES
