import pytest

from backend.services.spc_analysis_service import (
    calculate_control_limits,
    calculate_cpk_trend,
    calculate_distribution_stats,
    calculate_process_capability,
)
from backend.services.spc_stability import evaluate_stability


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
    avgs = [10, 10.1, 9.9, 10.2, 9.8]
    stability = {"evaluated": True, "stable": True, "violations": [], "rules_used": []}
    result = calculate_process_capability(
        avgs=avgs,
        all_values=[9.9, 10.0, 10.1, 10.2, 9.8, 10.0, 10.1, 9.9, 10.2, 9.8],
        r_cl=0.4,
        d2=2.326,
        tolerance_limits={"USL": 11, "LSL": 9},
        include_reason=True,
        stability=stability,
    )
    assert result["available"] is True
    assert result["applicable"] == "capability"   # 穩定 → 報 Cp/Cpk
    assert result["cp"] is not None
    assert result["cpk"] is not None
    assert result["cp"] == result["pp"]           # §6.2：C 與 P 公式相同（整體變異）
    assert result["cpk"] == result["ppk"]
    assert result["cw"] is not None               # 組內指數另列 Cw/Cwk 參考
    assert result["method"] == "G"
    assert result["ppm"]["total"] >= 0


def test_unstable_process_reports_performance_only():
    stability = {"evaluated": True, "stable": False,
                 "violations": [{"index": 0, "rule": "beyond_limits", "label": "x"}],
                 "rules_used": ["beyond_limits"]}
    result = calculate_process_capability(
        avgs=[10, 10.1, 9.9, 10.2, 9.8],
        all_values=[9.9, 10.0, 10.1, 10.2, 9.8, 10.0, 10.1, 9.9, 10.2, 9.8],
        r_cl=0.4, d2=2.326,
        tolerance_limits={"USL": 11, "LSL": 9},
        stability=stability,
    )
    assert result["applicable"] == "performance"
    assert result["cp"] is None and result["cpk"] is None
    assert result["pp"] is not None and result["ppk"] is not None


def test_no_stability_info_reports_performance_only():
    result = calculate_process_capability(
        avgs=[10, 10.1, 9.9, 10.2, 9.8],
        all_values=[9.9, 10.0, 10.1, 10.2, 9.8, 10.0, 10.1, 9.9, 10.2, 9.8],
        r_cl=0.4, d2=2.326,
        tolerance_limits={"USL": 11, "LSL": 9},
        stability=None,
    )
    assert result["applicable"] == "performance"
    assert result["cp"] is None


def test_upper_one_sided_limits():
    # 同心度等單側上限特性：只計算 PPU/CPU 側（§6.8.2.2）
    result = calculate_process_capability(
        avgs=[0.02, 0.03, 0.025, 0.02, 0.03],
        all_values=[0.02, 0.03, 0.025, 0.02, 0.03, 0.024],
        r_cl=0.01, d2=2.326,
        tolerance_limits={"USL": 0.05, "LSL": 0, "one_sided": "upper"},
    )
    assert result["one_sided"] == "upper"
    assert result["ppk"] is not None
    assert result["ppk"] == result["ppu"]
    assert result["pp"] is None


def test_targets_and_preliminary_flags():
    result = calculate_process_capability(
        avgs=[10, 10.1, 9.9, 10.2, 9.8],
        all_values=[9.9, 10.0, 10.1, 10.2, 9.8, 10.0, 10.1, 9.9, 10.2, 9.8],
        r_cl=0.4, d2=2.326,
        tolerance_limits={"USL": 11, "LSL": 9},
        characteristic_class="主要",
    )
    assert result["targets"]["class"] == "主要"
    assert result["targets"]["insufficient_sample"] is True  # 只有 10 筆
    assert result["preliminary"] is True                     # n<125 或子組<25
    assert isinstance(result["achieved"], bool)


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
    assert result["ppl"] == result["ppk"]
    assert result["ppk"] is not None
    assert result["cpk"] is None


def test_zero_variance_returns_none_capability_indices():
    # 量測值完全相同（如四捨五入後之常數資料）：sigma_overall=0，
    # 指數應安全回傳 None/0.0，不得產生 NaN/inf 或除以零例外
    result = calculate_process_capability(
        avgs=[10, 10, 10, 10, 10],
        all_values=[10, 10, 10, 10, 10, 10],
        r_cl=0, d2=2.326,
        tolerance_limits={"USL": 11, "LSL": 9},
    )
    assert result["available"] is True
    assert result["pp"] is None
    assert result["ppk"] is None
    assert result["cp"] is None
    assert result["cpk"] is None
    assert result["cw"] is None
    assert result["cwk"] is None
    assert result["ppm"]["total"] == 0.0


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


def test_control_limits_lcl_can_be_negative():
    # 中心線接近 0 時 LCL 不得被箝制為 0（真圓度等特性統計上允許負 LCL）
    result = calculate_control_limits(
        avgs=[0.01, 0.02, 0.015, 0.01, 0.02],
        ranges=[0.03, 0.04, 0.03, 0.04, 0.03],
        subgroup_sizes=[5, 5, 5, 5, 5],
    )
    assert result["x_lcl"] < 0
