import pytest

from backend.services.spc_analysis_service import (
    calculate_control_limits,
    calculate_cpk_trend,
    calculate_distribution_stats,
    calculate_process_capability,
)


def test_calculate_control_limits_uses_baseline_subgroups():
    result = calculate_control_limits(
        avgs=[10, 11, 12, 13, 14, 15],
        ranges=[1, 1.2, 1.1, 1.3, 1.2, 4.0],
        subgroup_sizes=[5, 5, 5, 5, 5, 5],
        baseline_limit=5,
    )

    assert result["baseline_count"] == 5
    assert result["avg_n"] == 5
    assert result["x_cl"] == 12
    assert result["r_cl"] == pytest.approx(1.16)
    assert result["d2"] == 2.326


def test_process_capability_supports_two_sided_and_ppm():
    result = calculate_process_capability(
        avgs=[10, 10.1, 9.9, 10.2, 9.8],
        all_values=[9.9, 10.0, 10.1, 10.2, 9.8, 10.0, 10.1, 9.9, 10.2, 9.8],
        r_cl=0.4,
        d2=2.326,
        tolerance_limits={"USL": 11, "LSL": 9},
        include_reason=True,
    )

    assert result["available"] is True
    assert result["usl"] == 11
    assert result["lsl"] == 9
    assert result["cp"] is not None
    assert result["cpk"] is not None
    assert result["ppm"]["total"] >= 0


def test_process_capability_supports_lower_one_sided_limits():
    result = calculate_process_capability(
        avgs=[60, 61, 62, 63, 64],
        all_values=[60, 61, 62, 63, 64, 65],
        r_cl=2.0,
        d2=2.326,
        tolerance_limits={"LSL": 55, "one_sided": "lower"},
    )

    assert result["available"] is True
    assert result["one_sided"] == "lower"
    assert result["usl"] is None
    assert result["cpl"] == result["cpk"]
    assert result["ppl"] == result["ppk"]


def test_distribution_stats_labels_non_normal_data():
    result = calculate_distribution_stats([1, 1, 1, 1, 10, 20])

    assert result["normality"] == "poor"
    assert result["normality_label"] == "分佈明顯非常態，Cpk 可能不準確"


def test_calculate_cpk_trend_groups_values_by_month():
    result = calculate_cpk_trend(
        all_values=[9.8, 10.0, 10.2, 10.1, 9.9, 10.5, 10.1, 9.9, 10.0, 10.2],
        dates_valid=["2026-01-01", "2026-01-02", "2026-01-03", "2026-01-04", "2026-01-05"],
        subgroup_sizes=[2, 2, 2, 2, 2],
        usl=11,
        lsl=9,
    )

    assert result == [{"month": "2026-01", "cpk": result[0]["cpk"], "count": 10}]
