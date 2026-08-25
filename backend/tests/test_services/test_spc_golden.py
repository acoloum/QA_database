"""SPC 2026 黃金資料回歸：鎖定圖表選型、時間模型與指標門檻。"""

from copy import deepcopy
from datetime import date, timedelta
import math

import pytest

from backend.services.spc_analysis_service import calculate_process_capability
from backend.services.spc_chart_engine import calculate_chart_set
from backend.services.spc_contracts import SpcSubgroup
from backend.services.spc_time_model import classify_time_model
from backend.scripts.spc_advanced_regression import (
    _build_actual,
    _compare,
    _load_baseline,
)


def _numeric_paths(value, path=""):
    if isinstance(value, bool) or value is None:
        return []
    if isinstance(value, (int, float)):
        return [path]
    if isinstance(value, dict):
        return [
            child
            for key, item in value.items()
            for child in _numeric_paths(item, f"{path}.{key}" if path else key)
        ]
    if isinstance(value, list):
        return [
            child
            for index, item in enumerate(value)
            for child in _numeric_paths(item, f"{path}[{index}]")
        ]
    return []


def _groups(sizes):
    values = (
        (9.82, 10.04, 10.16, 10.08, 9.96),
        (9.88, 10.12, 10.02, 9.94, 10.20),
        (9.91, 10.08, 10.18, 9.86, 10.03),
        (9.84, 10.06, 10.14, 9.98, 10.10),
        (9.89, 10.11, 9.97, 10.19, 10.01),
        (9.87, 10.09, 10.17, 9.93, 10.05),
    )
    start = date(2026, 7, 1)
    return tuple(
        SpcSubgroup(
            key=f"G{index + 1}",
            timestamp=start + timedelta(days=index),
            values=tuple(values[index][:size]),
            record_ids=(index + 1,),
            measurement_ids=tuple(range(index * 10, index * 10 + size)),
        )
        for index, size in enumerate(sizes)
    )


def _stability(location, variation, *, rule=None):
    location_violations = ([{
        "index": 5, "window_start": 0, "window_end": 5,
        "rule": rule, "label": rule, "chart_kind": "location",
    }] if rule else [])
    return {
        "evaluated": True,
        "stable": location and variation,
        "location": {"stable": location, "violations": location_violations},
        "variation": {"stable": variation, "violations": []},
        "violations": location_violations,
    }


NORMAL = {
    "model": "normal", "label": "常態分布", "params": (10.0, 0.2),
    "accepted": True, "normal_ok": True, "unimodal": True,
    "reason_code": None, "candidates": [], "fit_method": "golden", "alpha": 0.05,
}
LOGNORMAL = {
    **NORMAL,
    "model": "lognormal", "label": "對數常態分布", "params": (0.02, 0.0, 10.0),
    "normal_ok": False,
}
UNCONFIRMED = {
    "model": None, "label": "分布模型未確認", "params": (),
    "accepted": False, "normal_ok": False, "unimodal": False,
    "reason_code": "GOODNESS_OF_FIT_REJECTED", "candidates": [],
    "fit_method": None, "alpha": 0.05,
}


def test_golden_chart_selection_and_point_specific_limits():
    xbar_s = calculate_chart_set(_groups((3, 4, 5, 3, 4, 5)))
    xbar_r = calculate_chart_set(_groups((2, 2, 2, 2, 2, 2)))
    i_mr = calculate_chart_set(_groups((1, 1, 1, 1, 1, 1)))

    assert xbar_s.chart_type == "xbar_s"
    assert xbar_s.subgroup_sizes == (3, 4, 5, 3, 4, 5)
    assert xbar_s.location.cl[0] == pytest.approx(10.0145833333, abs=1e-8)
    assert xbar_s.location.ucl[:3] == pytest.approx(
        (10.2456996163, 10.2147359056, 10.1936052363), abs=1e-8
    )
    assert len(set(round(value, 8) for value in xbar_s.location.ucl)) == 3
    assert xbar_s.variation.lcl[0] > 0

    assert xbar_r.chart_type == "xbar_r"
    assert xbar_r.location.ucl[0] == pytest.approx(10.3800333333, abs=1e-8)
    assert xbar_r.variation.lcl[0] == 0

    assert i_mr.chart_type == "i_mr"
    assert i_mr.variation.values[0] is None
    assert i_mr.location.ucl[0] == pytest.approx(9.9906737589, abs=1e-8)


@pytest.mark.parametrize(
    ("stability", "distribution", "candidate"),
    [
        (_stability(True, True), NORMAL, "A1"),
        (_stability(True, True), LOGNORMAL, "A2"),
        (_stability(True, False), NORMAL, "B"),
        (_stability(False, True, rule="trend_6"), NORMAL, "C3"),
        (_stability(False, False), NORMAL, "D"),
    ],
)
def test_golden_time_model_candidates(stability, distribution, candidate):
    chart = calculate_chart_set(_groups((3, 3, 3, 3, 3, 3)))
    result = classify_time_model(chart, stability, distribution)
    assert result["candidate"] == candidate
    assert result["confirmed"] is False


def test_golden_unconfirmed_distribution_never_falls_back_to_normal():
    chart = calculate_chart_set(_groups((3, 3, 3, 3, 3, 3)))
    time_model = classify_time_model(chart, _stability(True, True), UNCONFIRMED)
    all_values = [value for group in _groups((3, 3, 3, 3, 3, 3)) for value in group.values]
    capability = calculate_process_capability(
        avgs=list(chart.location.values), all_values=all_values,
        r_cl=chart.variation.cl[0], d2=chart.variation.cl[0] / chart.sigma_within,
        tolerance_limits={"USL": 11, "LSL": 9},
        stability=_stability(True, True), dist=UNCONFIRMED, time_model=time_model,
    )

    assert time_model["candidate"] is None
    assert time_model["reason_code"] == "TIME_MODEL_UNCONFIRMED"
    assert capability["available"] is False
    assert capability["capability_reason"] == "GOODNESS_OF_FIT_REJECTED"
    assert capability["cpk"] is None
    assert capability["ppm"]["total"] is None


def test_golden_variation_instability_blocks_cpk_but_keeps_performance():
    chart = calculate_chart_set(_groups((3, 3, 3, 3, 3, 3)))
    groups = _groups((3, 3, 3, 3, 3, 3))
    all_values = [value for group in groups for value in group.values]
    unstable = _stability(True, False)
    capability = calculate_process_capability(
        avgs=list(chart.location.values), all_values=all_values,
        r_cl=chart.variation.cl[0], d2=chart.variation.cl[0] / chart.sigma_within,
        tolerance_limits={"USL": 11, "LSL": 9},
        stability=unstable, dist=NORMAL,
        time_model={"candidate": "B", "confirmed": False},
    )

    assert capability["available"] is True
    assert "reason" not in capability
    assert capability["applicable"] == "performance"
    assert capability["ppk"] == pytest.approx(2.660, abs=1e-3)
    assert capability["cp"] is None
    assert capability["cpk"] is None


def test_golden_confirmed_a1_supports_one_sided_capability():
    chart = calculate_chart_set(_groups((3, 3, 3, 3, 3, 3)))
    groups = _groups((3, 3, 3, 3, 3, 3))
    all_values = [value for group in groups for value in group.values]
    capability = calculate_process_capability(
        avgs=list(chart.location.values), all_values=all_values,
        r_cl=chart.variation.cl[0], d2=chart.variation.cl[0] / chart.sigma_within,
        tolerance_limits={"USL": 11, "one_sided": "upper"},
        stability=_stability(True, True), dist=NORMAL,
        time_model={"model": "A1", "candidate": "A1", "confirmed": True},
    )

    assert capability["applicable"] == "capability"
    assert capability["pp"] is None
    assert capability["ppl"] is None
    assert capability["ppu"] == pytest.approx(2.660, abs=1e-3)
    assert capability["cpk"] == capability["ppk"]


def test_advanced_fixed_baseline_reports_value_drift_and_missing_tolerance():
    """固定 expected 不得由 actual 自動更新，差異必須帶 path 與容許誤差。"""

    expected, tolerances = _load_baseline()
    actual = _build_actual()
    actual["attribute"]["p"]["center"] += 0.01

    differences = _compare(expected, actual, tolerances)

    assert differences == [{
        "path": "attribute.p.center",
        "expected": expected["attribute"]["p"]["center"],
        "actual": actual["attribute"]["p"]["center"],
        "abs_tol": 1e-12,
        "rel_tol": 1e-12,
    }]

    missing = dict(tolerances)
    missing.pop("machine.pmk")
    assert any(
        row == {"path": "machine.pmk", "error": "數值基準缺少明確容許誤差"}
        for row in _compare(expected, _build_actual(), missing)
    )


def test_advanced_golden_covers_full_internal_evidence_and_tolerances():
    expected, tolerances = _load_baseline()
    actual = _build_actual()

    for chart_type in ("p", "np"):
        chart = actual["attribute"][chart_type]
        assert {
            "values", "cl", "lcl", "ucl", "n", "x", "lower_counts",
            "upper_counts", "pearson_residuals",
        } <= set(chart)
        assert len(chart["lcl"]) == len(chart["ucl"]) == len(chart["x"])

    machine = actual["machine"]
    assert {
        "pm", "pmk", "pmu", "pml", "targets", "eligibility",
        "source_semantics", "quantiles",
    } <= set(machine)
    for model in ("A1", "A2", "B", "C1", "C2", "C3", "C4", "D"):
        evidence = actual["time_models"][model]
        assert {
            "candidate", "trend", "welch_holm", "levene_holm",
            "change_indexes", "peak_count", "formal",
        } <= set(evidence)
        assert {"tau", "slope", "raw_p_value", "adjusted_p_value", "threshold"} <= set(evidence["trend"])
        assert {"location_stable", "variation_stable", "reason_code"} <= set(evidence["formal"])

    for model in ("boxcox", "johnson_su", "johnson_sb", "johnson_sl"):
        candidate = actual["transformations"][model]
        assert {
            "params", "tail_quantiles", "monotonic", "rank", "reason_code",
            "ad_statistic", "ad_p_value", "roundtrip_relative_error",
        } <= set(candidate)
        assert list(candidate["params"]) == sorted(candidate["params"])

    assert set(_numeric_paths(expected)) == set(tolerances)
    assert _compare(expected, actual, tolerances) == []


def test_same_time_candidate_with_internal_diagnostic_drift_fails():
    expected, tolerances = _load_baseline()
    actual = _build_actual()
    assert actual["time_models"]["C3"]["candidate"] == "C3"
    actual["time_models"]["C3"]["trend"]["tau"] += 0.1

    differences = _compare(expected, actual, tolerances)

    assert any(row["path"] == "time_models.C3.trend.tau" for row in differences)


def test_optimizer_tolerances_are_portable_without_weakening_acceptance_threshold():
    """優化器「直接輸出」的容差維持在 1e-8～1e-7。

    tail_quantiles 不在此列：它們不是優化器的直接輸出，而是由這些參數推導出來、
    且回到原始單位（量級可達 55）的值。對它們套用固定的絕對上限會與物理矛盾——
    參數在自己被允許的 5e-08 內變動，就足以讓分位數位移 2e-05。那條界線改由
    test_spc_advanced_tolerance_coherence.py 以誤差傳遞同時鎖住下限與上限，
    比單一固定數字更嚴格，也不會把守門變成只能靠運氣通過。
    """
    _, tolerances = _load_baseline()
    optimizer_paths = [
        path for path in tolerances
        if path.startswith("transformations.")
        and any(name in path for name in ("params", "ad_statistic"))
    ]
    assert optimizer_paths
    assert all(1e-8 <= tolerances[path]["abs"] <= 1e-7 for path in optimizer_paths)
    for model in ("boxcox", "johnson_su", "johnson_sb", "johnson_sl"):
        error = _build_actual()["transformations"][model]["roundtrip_relative_error"]
        assert math.isfinite(error) and error <= 1e-9
