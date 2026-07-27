"""MSA 穩定性分析測試。"""

from datetime import date, timedelta

import pytest

from backend.services.msa_contracts import MsaMethodContext
from backend.services.msa_errors import MsaMethodNotApplicable
from backend.services.msa_stability import analyze_stability


def _context(**overrides):
    values = {
        "method_code": "MSA4_STABILITY_1_0",
        "method_version": "1.0",
        "alpha": 0.05,
        "study_variation_multiplier": 6.0,
        "tolerance": 1.0,
        "process_sigma": None,
        "criteria": {
            "stability_rules": {"rule_set": "WECO", "enabled_rules": [1, 2, 3, 4]}
        },
    }
    values.update(overrides)
    return MsaMethodContext(**values)


def _series(subgroup_size, count=24, *, start=date(2026, 1, 1), step=7):
    """建立穩定、可重現且無判異的基準序列。

    組間偏移刻意遠小於組內離散，界限才不會窄到讓正常波動就判異；
    偏移正負交錯，也不會形成連續同側或趨勢。
    """
    between_offsets = [0.001, -0.001, 0.0005, -0.0005]
    within_spread = 0.005
    series = []
    for index in range(count):
        base = 10.0 + between_offsets[index % len(between_offsets)]
        readings = [
            base + (within_spread if position % 2 else -within_spread)
            for position in range(subgroup_size)
        ]
        series.append({
            "measured_on": (start + timedelta(days=step * index)).isoformat(),
            "readings": readings,
        })
    return series


@pytest.mark.parametrize(
    ("subgroup_size", "expected_chart"),
    [(1, "i_mr"), (4, "xbar_r"), (12, "xbar_s")],
)
def test_stability_selects_controlled_chart(subgroup_size, expected_chart):
    output = analyze_stability(_series(subgroup_size), _context())

    assert output.statistics["chart_type"] == expected_chart
    assert output.statistics["subgroup_size"] == subgroup_size


def test_stability_has_no_fake_single_index():
    """穩定與否由違規清單表達，不輸出任何綜合指數。"""
    output = analyze_stability(_series(4), _context())

    assert "stability_index" not in output.statistics
    assert output.statistics["stable"] is True
    assert output.statistics["rule_violations"] == []


def test_stability_reports_baseline_period_and_rule_set():
    series = _series(4)
    output = analyze_stability(series, _context())
    baseline = output.statistics["baseline_period"]

    assert baseline["from"] == series[0]["measured_on"]
    assert baseline["to"] == series[-1]["measured_on"]
    assert baseline["count"] == len(series)
    assert output.statistics["rule_set"] == "WECO"
    assert output.statistics["enabled_rules"] == [1, 2, 3, 4]


def test_point_beyond_control_limits_is_reported_as_rule_one():
    series = _series(4)
    series[10]["readings"] = [11.0, 11.0, 11.0, 11.0]

    output = analyze_stability(series, _context())

    assert output.statistics["stable"] is False
    assert any(
        violation["rule"] == 1 and violation.get("index") == 10
        for violation in output.statistics["rule_violations"]
    )


def test_eight_consecutive_points_on_one_side_trigger_rule_four():
    series = _series(1)
    for index in range(5, 15):
        series[index]["readings"] = [10.0015]

    output = analyze_stability(series, _context())

    assert any(
        violation["rule"] == 4
        for violation in output.statistics["rule_violations"]
    )


def test_disabled_rules_are_not_applied():
    series = _series(1)
    for index in range(5, 15):
        series[index]["readings"] = [10.0015]
    criteria = {
        "stability_rules": {"rule_set": "WECO", "enabled_rules": [1]}
    }

    output = analyze_stability(series, _context(criteria=criteria))

    assert all(
        violation["rule"] == 1
        for violation in output.statistics["rule_violations"]
    )
    assert output.statistics["enabled_rules"] == [1]


def test_unsupported_rule_is_rejected_rather_than_silently_ignored():
    criteria = {
        "stability_rules": {"rule_set": "WECO", "enabled_rules": [1, 9]}
    }

    with pytest.raises(MsaMethodNotApplicable) as error:
        analyze_stability(_series(4), _context(criteria=criteria))

    assert error.value.details["reason"] == "unsupported_stability_rule"


def test_unsorted_time_series_is_rejected():
    series = _series(4)
    series[3], series[9] = series[9], series[3]

    with pytest.raises(MsaMethodNotApplicable) as error:
        analyze_stability(series, _context())

    assert error.value.details["reason"] == "unsorted_time_series"


def test_missing_measurement_intervals_are_reported():
    series = _series(4)
    for index in range(12, len(series)):
        moment = date.fromisoformat(series[index]["measured_on"])
        series[index]["measured_on"] = (
            moment + timedelta(days=60)
        ).isoformat()

    output = analyze_stability(series, _context())

    assert output.statistics["missing_intervals"]
    assert any(
        warning["code"] == "MSA_STABILITY_MISSING_INTERVALS"
        for warning in output.warnings
    )


def test_inconsistent_subgroup_size_is_rejected():
    series = _series(4)
    series[7]["readings"] = series[7]["readings"][:2]

    with pytest.raises(MsaMethodNotApplicable) as error:
        analyze_stability(series, _context())

    assert error.value.details["reason"] == "inconsistent_subgroup_size"


def test_insufficient_baseline_is_rejected():
    with pytest.raises(MsaMethodNotApplicable) as error:
        analyze_stability(_series(4, count=10), _context())

    assert error.value.details["reason"] == "insufficient_baseline"


def test_missing_timestamp_is_rejected():
    series = _series(4)
    series[2].pop("measured_on")

    with pytest.raises(MsaMethodNotApplicable) as error:
        analyze_stability(series, _context())

    assert error.value.details["reason"] == "missing_timestamp"


def test_non_finite_reading_is_rejected():
    series = _series(4)
    series[1]["readings"][0] = float("nan")

    with pytest.raises(MsaMethodNotApplicable) as error:
        analyze_stability(series, _context())

    assert error.value.details["reason"] == "non_finite_reading"


def test_chart_data_carries_raw_readings_limits_and_event_markers():
    series = _series(4)
    series[6]["event"] = {"type": "calibration", "note": "外校回廠"}

    output = analyze_stability(series, _context())
    chart = output.chart_data

    assert chart["primary_chart"]["label"] == "xbar"
    assert chart["dispersion_chart"]["label"] == "range"
    assert chart["primary_chart"]["ucl"] > chart["primary_chart"]["center"]
    assert chart["primary_chart"]["points"][0]["readings"] == (
        series[0]["readings"]
    )
    assert chart["event_markers"] == [
        {"measured_on": series[6]["measured_on"], "event": series[6]["event"]}
    ]


def test_individual_chart_uses_moving_range_dispersion():
    output = analyze_stability(_series(1), _context())

    assert output.statistics["dispersion_limits"]["label"] == "moving_range"
    assert output.chart_data["dispersion_chart"]["label"] == "moving_range"
    assert len(output.chart_data["dispersion_chart"]["points"]) == 23


def test_large_subgroup_uses_standard_deviation_chart():
    output = analyze_stability(_series(12), _context())

    assert output.statistics["chart_type"] == "xbar_s"
    assert output.statistics["dispersion_limits"]["label"] == "sd"
