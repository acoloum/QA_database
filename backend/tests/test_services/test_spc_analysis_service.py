import numpy as np
import pytest

from backend.services.spc_analysis_service import (
    calculate_control_limits,
    calculate_cpk_trend,
    calculate_distribution_stats,
    calculate_process_capability,
)
from backend.services.spc_stability import evaluate_stability


def _accepted_normal_distribution(values):
    return {
        "model": "normal",
        "label": "常態分布",
        "accepted": True,
        "normal_ok": True,
        "unimodal": True,
        "reason_code": None,
        "ad_stat": None,
        "params": (float(np.mean(values)), float(np.std(values, ddof=1))),
        "candidates": [],
        "fit_method": "test_fixture",
        "alpha": 0.05,
        "n": len(values),
    }


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


def test_calculate_control_limits_exposes_point_limits_for_unequal_n():
    result = calculate_control_limits(
        avgs=[10.0, 10.1, 9.9, 10.05, 9.95],
        ranges=[0.2, 0.3, 0.25, 0.2, 0.35],
        subgroup_sizes=[3, 4, 5, 3, 4],
    )

    assert result["variable_subgroup_size"] is True
    assert len(result["x_ucls"]) == 5
    assert result["x_ucls"][0] != result["x_ucls"][1]
    assert result["x_ucls"][1] != result["x_ucls"][2]
    assert result["r_cls"][0] != result["r_cls"][1]


def test_process_capability_supports_two_sided_and_ppm():
    avgs = [10, 10.1, 9.9, 10.2, 9.8]
    values = [9.9, 10.0, 10.1, 10.2, 9.8, 10.0, 10.1, 9.9, 10.2, 9.8]
    stability = {"evaluated": True, "stable": True, "violations": [], "rules_used": []}
    result = calculate_process_capability(
        avgs=avgs,
        all_values=values,
        r_cl=0.4,
        d2=2.326,
        tolerance_limits={"USL": 11, "LSL": 9},
        include_reason=True,
        stability=stability,
        time_model={"model": "A1", "confirmed": True},
        dist=_accepted_normal_distribution(values),
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
    values = [9.9, 10.0, 10.1, 10.2, 9.8, 10.0, 10.1, 9.9, 10.2, 9.8]
    stability = {"evaluated": True, "stable": False,
                 "violations": [{"index": 0, "rule": "beyond_limits", "label": "x"}],
                 "rules_used": ["beyond_limits"]}
    result = calculate_process_capability(
        avgs=[10, 10.1, 9.9, 10.2, 9.8],
        all_values=values,
        r_cl=0.4, d2=2.326,
        tolerance_limits={"USL": 11, "LSL": 9},
        stability=stability,
        dist=_accepted_normal_distribution(values),
    )
    assert result["applicable"] == "performance"
    assert result["cp"] is None and result["cpk"] is None
    assert result["pp"] is not None and result["ppk"] is not None


def test_no_stability_info_reports_performance_only():
    values = [9.9, 10.0, 10.1, 10.2, 9.8, 10.0, 10.1, 9.9, 10.2, 9.8]
    result = calculate_process_capability(
        avgs=[10, 10.1, 9.9, 10.2, 9.8],
        all_values=values,
        r_cl=0.4, d2=2.326,
        tolerance_limits={"USL": 11, "LSL": 9},
        stability=None,
        dist=_accepted_normal_distribution(values),
    )
    assert result["applicable"] == "performance"
    assert result["cp"] is None


def test_upper_one_sided_limits():
    # 同心度等單側上限特性：只計算 PPU/CPU 側（§6.8.2.2）
    values = [0.02, 0.03, 0.025, 0.02, 0.03, 0.024]
    result = calculate_process_capability(
        avgs=[0.02, 0.03, 0.025, 0.02, 0.03],
        all_values=values,
        r_cl=0.01, d2=2.326,
        tolerance_limits={"USL": 0.05, "LSL": 0, "one_sided": "upper"},
        dist=_accepted_normal_distribution(values),
    )
    assert result["one_sided"] == "upper"
    assert result["ppk"] is not None
    assert result["ppk"] == result["ppu"]
    assert result["pp"] is None


def test_targets_and_preliminary_flags():
    values = [9.9, 10.0, 10.1, 10.2, 9.8, 10.0, 10.1, 9.9, 10.2, 9.8]
    result = calculate_process_capability(
        avgs=[10, 10.1, 9.9, 10.2, 9.8],
        all_values=values,
        r_cl=0.4, d2=2.326,
        tolerance_limits={"USL": 11, "LSL": 9},
        characteristic_class="主要",
        dist=_accepted_normal_distribution(values),
    )
    assert result["targets"]["class"] == "主要"
    assert result["targets"]["insufficient_sample"] is True  # 只有 10 筆
    assert result["preliminary"] is True                     # n<125 或子組<25
    assert isinstance(result["achieved"], bool)


def test_process_capability_supports_lower_one_sided_limits():
    values = [60, 61, 62, 63, 64, 65]
    result = calculate_process_capability(
        avgs=[60, 61, 62, 63, 64],
        all_values=values,
        r_cl=2.0,
        d2=2.326,
        tolerance_limits={"LSL": 55, "one_sided": "lower"},
        dist=_accepted_normal_distribution(values),
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
    assert result["available"] is False
    assert result["reason"] == "distribution_unconfirmed"
    assert result["pp"] is None
    assert result["ppk"] is None
    assert result["cp"] is None
    assert result["cpk"] is None
    assert result["cw"] is None
    assert result["cwk"] is None
    assert result["ppm"]["total"] is None


def test_stable_process_without_confirmed_time_model_is_performance_only():
    values = [9.9, 10.0, 10.1, 10.2, 9.8, 10.0, 10.1, 9.9, 10.2, 9.8]
    result = calculate_process_capability(
        avgs=[10, 10.1, 9.9, 10.2, 9.8],
        all_values=values,
        r_cl=0.4,
        d2=2.326,
        tolerance_limits={"USL": 11, "LSL": 9},
        stability={"evaluated": True, "stable": True},
        dist=_accepted_normal_distribution(values),
    )

    assert result["applicable"] == "performance"
    assert result["ppk"] is not None
    assert result["cpk"] is None
    assert result["capability_reason"] == "TIME_MODEL_UNCONFIRMED"


def test_unconfirmed_distribution_blocks_performance_indices():
    result = calculate_process_capability(
        avgs=[10, 10.1, 9.9, 10.2, 9.8],
        all_values=[9.9, 10.0, 10.1, 10.2, 9.8, 10.0],
        r_cl=0.4,
        d2=2.326,
        tolerance_limits={"USL": 11, "LSL": 9},
    )

    assert result["available"] is False
    assert result["reason"] == "distribution_unconfirmed"
    assert result["ppk"] is None
    assert result["cpk"] is None


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


def test_capability_uses_percentile_method_for_non_normal():
    import numpy as np
    rng = np.random.default_rng(3)
    values = np.abs(rng.normal(0, 0.01, 300)).tolist()  # 摺疊常態形狀資料
    avgs = [float(np.mean(values[i:i+5])) for i in range(0, 100, 5)]
    result = calculate_process_capability(
        avgs=avgs, all_values=values, r_cl=0.01, d2=2.326,
        tolerance_limits={"USL": 0.05, "LSL": 0, "one_sided": "upper"},
        field="真圓度",
    )
    assert result["distribution"]["model"] == "folded_normal"
    assert result["ppk"] is not None
    # G 法分位數:Ppk = (U − X50%) / (X99.865% − X50%)
    from backend.services.spc_distribution import assess_distribution, dist_quantiles
    d = assess_distribution(values, field="真圓度")
    q_lo, q_mid, q_hi = dist_quantiles(d)
    expected = (0.05 - q_mid) / (q_hi - q_mid)
    assert result["ppk"] == pytest.approx(expected, abs=0.01)
