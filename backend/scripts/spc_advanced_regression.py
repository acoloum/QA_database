"""SPC 2026.2 進階分析固定基準確效與稽核保存工具。"""

from __future__ import annotations

import argparse
from datetime import date, timedelta
import json
import math
from pathlib import Path
import sys
from typing import Any, Mapping

import numpy as np
from scipy import stats as scipy_stats


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.extensions import db
from backend.models import SpcValidationRun
from backend.services.spc_attribute_engine import (
    AttributeSubgroup,
    calculate_attribute_chart,
)
from backend.services.spc_chart_engine import calculate_chart_set
from backend.services.spc_contracts import SpcChartSeries, SpcChartSet, SpcSubgroup
from backend.services.spc_distribution import assess_distribution
from backend.services.spc_machine_performance import calculate_machine_performance
from backend.services.spc_stability import evaluate_study_stability
from backend.services.spc_study_service import (
    SPC_CODE_VERSION,
    SPC_METHOD_VERSION,
    _require_permission,
)
from backend.services.spc_time_diagnostics import diagnose_time_model
from backend.services.spc_transformations import evaluate_transformations


DATASET_VERSION = "spc-advanced-golden-2026.2"
# 基準內多數數值的容差是 abs 5e-08；分布轉換的 tail_quantiles 例外，因為它們是由
# 擬合參數推導出來的，容差必須大於「參數在自己容差內變動」所造成的位移，否則守門
# 自相矛盾、只能靠運氣通過。那些數字是由誤差傳遞算出來的，且由
# tests/test_services/test_spc_advanced_tolerance_coherence.py 釘住上下界。
EXPECTED_PATH = Path(__file__).with_name("spc_advanced_expected_2026_2.json")
PASS_LINE = (
    "[PASS] SPC 2026.2 進階分析確效通過；"
    "屬性圖、機器績效、時間模型與分布轉換皆符合固定基準。"
)
TIME_MODELS = ("A1", "A2", "B", "C1", "C2", "C3", "C4", "D")
TRANSFORMATION_MODELS = ("boxcox", "johnson_su", "johnson_sb", "johnson_sl")


def _assert_no_nonfinite(value: Any, path: str = "root") -> None:
    if isinstance(value, (float, np.floating)) and not math.isfinite(float(value)):
        raise AssertionError(f"{path} 出現 NaN 或 Infinity")
    if isinstance(value, Mapping):
        for key, item in value.items():
            _assert_no_nonfinite(item, f"{path}.{key}")
    elif isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            _assert_no_nonfinite(item, f"{path}[{index}]")


def _json_safe(value: Any) -> Any:
    """將錯誤路徑上的 NumPy 與非有限值轉為可保存的明確 JSON 證據。"""

    if isinstance(value, np.generic):
        value = value.item()
    if isinstance(value, float) and not math.isfinite(value):
        if math.isnan(value):
            return "NaN"
        return "Infinity" if value > 0 else "-Infinity"
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return value


def _error_detail(stage: str, exc: Exception) -> dict[str, str]:
    return {
        "stage": stage,
        "error_type": type(exc).__name__,
        "message": str(exc),
    }


def _attribute_actual() -> dict[str, Any]:
    p_chart = calculate_attribute_chart(
        (
            AttributeSubgroup("p-1", "2026-07-01", 80, 4),
            AttributeSubgroup("p-2", "2026-07-02", 100, 7),
            AttributeSubgroup("p-3", "2026-07-03", 120, 8),
            AttributeSubgroup("p-4", "2026-07-04", 90, 3),
        ),
        "p",
    )
    np_chart = calculate_attribute_chart(
        tuple(
            AttributeSubgroup(f"np-{index}", f"2026-07-{index:02d}", 100, count)
            for index, count in enumerate((4, 7, 8, 3), start=1)
        ),
        "np",
    )

    def compact(chart: Mapping[str, Any]) -> dict[str, Any]:
        return {
            "chart_type": chart["chart_type"],
            "center": chart["center"],
            "values": list(chart["values"]),
            "cl": list(chart["cl"]),
            "lcl": list(chart["lcl"]),
            "ucl": list(chart["ucl"]),
            "n": list(chart["n"]),
            "x": list(chart["x"]),
            "lower_counts": list(chart["lower_counts"]),
            "upper_counts": list(chart["upper_counts"]),
            "pearson_residuals": list(chart["pearson_residuals"]),
            "total_inspected": chart["total_inspected"],
            "total_nonconforming": chart["total_nonconforming"],
        }

    return {"p": compact(p_chart), "np": compact(np_chart)}


def _machine_actual() -> dict[str, Any]:
    result = calculate_machine_performance(
        values=np.linspace(9.8, 10.2, 60).tolist(),
        specification={"found": True, "consistent": True, "LSL": 9.2, "USL": 10.8},
        distribution={
            "model": "normal", "label": "常態分布", "accepted": True,
            "reason_code": None, "params": [10.0, 0.1],
        },
        characteristic_class="主要",
    )
    return {
        "method": result["method"],
        "n": result["n"],
        "pm": result["pm"],
        "pmk": result["pmk"],
        "pmu": result["pmu"],
        "pml": result["pml"],
        "quantiles": dict(result["quantiles"]),
        "targets": dict(result["targets"]),
        "eligibility": {
            "available": result["available"],
            "preliminary": result["preliminary"],
            "approvable": result["approvable"],
            "reason_code": result["reason_code"],
        },
        "source_semantics": "patrol_min_max_observations",
    }


def _sampled_groups(matrix: np.ndarray) -> tuple[SpcSubgroup, ...]:
    return tuple(
        SpcSubgroup(
            key=f"advanced-time:{index}",
            timestamp=date(2026, 2, 1) + timedelta(days=index),
            values=tuple(float(value) for value in row),
            record_ids=(index + 1,),
        )
        for index, row in enumerate(matrix)
    )


def _controlled_chart(groups: tuple[SpcSubgroup, ...]) -> SpcChartSet:
    calculated = calculate_chart_set(groups)
    count = len(groups)
    locations = tuple(float(value) for value in calculated.location.values)
    variations = tuple(
        float(value) if value is not None else None
        for value in calculated.variation.values
    )
    numeric_variations = [value for value in variations if value is not None]
    location_center = float(np.mean(locations))
    variation_center = float(np.mean(numeric_variations))
    location_span = max(5.0, float(np.std(locations, ddof=1)) * 10)
    variation_upper = max(numeric_variations) + max(1.0, variation_center * 3)
    return SpcChartSet(
        chart_type=calculated.chart_type,
        location=SpcChartSeries(
            calculated.location.statistic,
            locations,
            (location_center,) * count,
            (location_center + location_span,) * count,
            (location_center - location_span,) * count,
        ),
        variation=SpcChartSeries(
            calculated.variation.statistic,
            variations,
            tuple(value if value is not None else variation_center for value in variations),
            (variation_upper,) * count,
            (0.0,) * count,
        ),
        subgroup_sizes=calculated.subgroup_sizes,
        sigma_within=calculated.sigma_within,
        variation_source_pairs=calculated.variation_source_pairs,
    )


def _normalized_rows(
    rng: np.random.Generator,
    means: list[float],
    scales: list[float],
    *,
    size: int = 12,
    skew: bool = False,
) -> np.ndarray:
    rows = []
    for mean, scale in zip(means, scales):
        sample = rng.exponential(1.0, size=size) if skew else rng.normal(0.0, 1.0, size=size)
        sample = (sample - sample.mean()) / sample.std(ddof=1)
        rows.append(mean + scale * sample)
    return np.asarray(rows)


def _time_dataset(model: str) -> tuple[SpcChartSet, tuple[SpcSubgroup, ...], dict[str, Any]]:
    rng = np.random.default_rng(100 + sum(ord(char) for char in model))
    if model == "A1":
        matrix = np.random.default_rng(0).normal(10.0, 1.0, size=(30, 5))
    elif model == "A2":
        matrix = _normalized_rows(rng, [10.0] * 30, [1.0] * 30, skew=True)
    elif model == "B":
        matrix = _normalized_rows(rng, [10.0] * 30, [0.35] * 15 + [2.2] * 15)
    elif model == "C1":
        raw = np.random.default_rng(0)
        means = raw.normal(10.0, 0.9, size=30)
        matrix = np.asarray([mean + raw.normal(0.0, 0.25, size=5) for mean in means])
    elif model == "C2":
        raw = np.random.default_rng(0)
        means = 9.0 + raw.lognormal(-0.2, 0.45, size=30)
        matrix = np.asarray([mean + raw.normal(0.0, 0.08, size=5) for mean in means])
    elif model == "C3":
        matrix = _normalized_rows(
            rng, [9.0 + index * 0.08 for index in range(30)], [0.5] * 30
        )
    elif model == "C4":
        matrix = _normalized_rows(
            rng, [9.5] * 10 + [10.5] * 10 + [9.7] * 10, [0.5] * 30
        )
    else:
        matrix = _normalized_rows(
            rng, [9.0] * 15 + [11.0] * 15, [0.3] * 15 + [2.0] * 15
        )
    groups = _sampled_groups(matrix)
    chart = _controlled_chart(groups)
    values = [value for group in groups for value in group.values]
    return chart, groups, assess_distribution(values)


def _holm_summary(rows: list[Mapping[str, Any]]) -> dict[str, Any]:
    adjusted = [float(row["adjusted_p_value"]) for row in rows]
    rejected = [float(row["adjusted_p_value"]) for row in rows if row["reject"]]
    return {
        "method": "Holm",
        "comparison_count": len(rows),
        "minimum_adjusted_p_value": min(adjusted) if adjusted else None,
        "maximum_rejected_adjusted_p_value": max(rejected) if rejected else None,
        "rejected_count": len(rejected),
    }


def _time_actual() -> dict[str, dict[str, Any]]:
    results: dict[str, dict[str, Any]] = {}
    for model in TIME_MODELS:
        chart, groups, distribution = _time_dataset(model)
        diagnostic = diagnose_time_model(
            chart,
            groups,
            distribution,
            stability=evaluate_study_stability(chart),
        )
        evidence = diagnostic["evidence"]
        families = evidence["multiple_testing"]["families"]
        trend_row = families["trend"][0]
        formal = evidence["formal_stability"]
        location_stable = formal["location"]["stable"]
        variation_stable = formal["variation"]["stable"]
        if location_stable is True and variation_stable is True:
            formal_reason = None
        elif location_stable is False and variation_stable is False:
            formal_reason = "LOCATION_AND_VARIATION_UNSTABLE"
        elif location_stable is False:
            formal_reason = "LOCATION_UNSTABLE"
        else:
            formal_reason = "VARIATION_UNSTABLE"
        results[model] = {
            "candidate": diagnostic["candidate"],
            "reason_code": diagnostic.get("reason_code"),
            "trend": {
                "tau": trend_row["tau"],
                "slope": trend_row["slope"],
                "raw_p_value": trend_row["raw_p_value"],
                "adjusted_p_value": trend_row["adjusted_p_value"],
                "threshold": trend_row["threshold"],
                "detected": evidence["trend"]["detected"],
            },
            "welch_holm": _holm_summary(families["mean_change"]),
            "levene_holm": _holm_summary(families["variance_change"]),
            "change_indexes": {
                "welch": list(evidence["change_points"]["change_points"]),
                "levene": list(evidence["variance_change"]["change_indexes"]),
            },
            "peak_count": evidence["aggregate_modality"].get("peak_count"),
            "formal": {
                "stable": formal["stable"],
                "location_stable": location_stable,
                "variation_stable": variation_stable,
                "reason_code": formal_reason,
            },
        }
    return results


def _transformation_actual() -> dict[str, Any]:
    probabilities = np.linspace(0.01, 0.99, 99)
    scores = scipy_stats.norm.ppf(probabilities)
    datasets = {
        "boxcox": np.power(0.25 * scores + 2.0, 4.0),
        "johnson_su": scipy_stats.johnsonsu.ppf(
            probabilities, 1.2, 1.8, loc=4.0, scale=1.5
        ),
        "johnson_sb": scipy_stats.johnsonsb.ppf(
            probabilities, 1.0, 1.5, loc=2.0, scale=8.0
        ),
        "johnson_sl": scipy_stats.lognorm.ppf(
            probabilities, 0.6, loc=0.0, scale=np.exp(1.0)
        ),
    }
    actual: dict[str, Any] = {}
    for model, values in datasets.items():
        result = evaluate_transformations(values)
        candidate = next(item for item in result["candidates"] if item["model"] == model)
        actual[model] = {
            "model": candidate["model"],
            "accepted": candidate["accepted"],
            "params": {
                key: candidate["params"][key]
                for key in sorted(candidate["params"])
            },
            "epsilon": candidate["epsilon"],
            "fit_method": candidate["fit_method"],
            "ad_statistic": candidate["ad_statistic"],
            "ad_p_value": candidate["ad_p_value"],
            "tail_quantiles": list(candidate["tail_quantiles"]),
            "monotonic": candidate["monotonic"],
            "roundtrip_relative_error": candidate["roundtrip_relative_error"],
            "rank": candidate["rank"],
            "reason_code": candidate["reason_code"],
        }
    return actual


def _build_actual() -> dict[str, Any]:
    actual = {
        "attribute": _attribute_actual(),
        "machine": _machine_actual(),
        "time_models": _time_actual(),
        "transformations": _transformation_actual(),
    }
    _assert_no_nonfinite(actual)
    return json.loads(json.dumps(actual, ensure_ascii=False, allow_nan=False))


def _load_baseline() -> tuple[dict[str, Any], dict[str, Any]]:
    with EXPECTED_PATH.open(encoding="utf-8") as stream:
        payload = json.load(stream)
    if payload.get("dataset_version") != DATASET_VERSION:
        raise AssertionError("進階確效基準資料版本不符")
    expected = payload.get("expected")
    tolerances = payload.get("tolerances")
    if not isinstance(expected, dict) or not isinstance(tolerances, dict):
        raise AssertionError("進階確效基準缺少 expected 或 tolerances")
    _assert_no_nonfinite(expected, "expected")
    _assert_no_nonfinite(tolerances, "tolerances")
    return expected, tolerances


def _compare(
    expected: Any,
    actual: Any,
    tolerances: Mapping[str, Any],
    *,
    path: str = "",
) -> list[dict[str, Any]]:
    differences: list[dict[str, Any]] = []
    if isinstance(expected, bool) or expected is None or isinstance(expected, str):
        if actual != expected:
            differences.append({"path": path, "expected": expected, "actual": actual})
        return differences
    if isinstance(expected, (int, float)):
        tolerance = tolerances.get(path)
        if not isinstance(tolerance, Mapping):
            return [{"path": path, "error": "數值基準缺少明確容許誤差"}]
        absolute = float(tolerance.get("abs", 0.0))
        relative = float(tolerance.get("rel", 0.0))
        if not isinstance(actual, (int, float)) or isinstance(actual, bool) or not math.isclose(
            float(expected), float(actual), abs_tol=absolute, rel_tol=relative
        ):
            differences.append({
                "path": path, "expected": expected, "actual": actual,
                "abs_tol": absolute, "rel_tol": relative,
            })
        return differences
    if isinstance(expected, dict):
        if not isinstance(actual, dict):
            return [{"path": path, "expected_type": "object", "actual": actual}]
        if set(expected) != set(actual):
            differences.append({
                "path": path,
                "missing_keys": sorted(set(expected) - set(actual)),
                "unexpected_keys": sorted(set(actual) - set(expected)),
            })
        for key in sorted(set(expected) & set(actual)):
            child = f"{path}.{key}" if path else key
            differences.extend(_compare(expected[key], actual[key], tolerances, path=child))
        return differences
    if isinstance(expected, list):
        if not isinstance(actual, list) or len(expected) != len(actual):
            return [{"path": path, "expected": expected, "actual": actual}]
        for index, (expected_item, actual_item) in enumerate(zip(expected, actual)):
            differences.extend(
                _compare(expected_item, actual_item, tolerances, path=f"{path}[{index}]")
            )
        return differences
    return [{"path": path, "error": "不支援的固定基準型別"}]


def run_advanced_regression(
    *,
    executed_by: int | None = None,
    persist: bool = False,
) -> dict[str, Any]:
    """執行固定資料確效；persist=True 時將 PASS／FAIL 證據保存到目前資料庫。

    計算或基準載入本身失敗（例如例外、NaN/Infinity）不得讓呼叫端整個崩潰，
    而必須轉為可持久化的 FAIL 明細，讓稽核紀錄留下確切證據。
    """

    if persist:
        _require_permission(executed_by, "spc.approve")

    expected: dict[str, Any] = {}
    tolerances: dict[str, Any] = {}
    actual: dict[str, Any] = {}
    try:
        expected, tolerances = _load_baseline()
        actual = _build_actual()
        differences = _compare(expected, actual, tolerances)
    except Exception as exc:  # noqa: BLE001 - 需將任何計算失敗轉為可持久化證據
        differences = [_error_detail("run_advanced_regression", exc)]

    result = "PASS" if not differences else "FAIL"
    safe_expected = _json_safe(expected)
    safe_actual = _json_safe(actual)
    safe_tolerances = _json_safe(tolerances)
    safe_details = _json_safe(differences)
    payload = {
        "dataset_version": DATASET_VERSION,
        "method_version": SPC_METHOD_VERSION,
        "code_version": SPC_CODE_VERSION,
        "expected": safe_expected,
        "actual": safe_actual,
        "tolerances": safe_tolerances,
        "result": result,
        "details": safe_details,
    }
    if persist:
        row = SpcValidationRun(
            dataset_version=DATASET_VERSION,
            method_version=SPC_METHOD_VERSION,
            code_version=SPC_CODE_VERSION,
            expected=safe_expected,
            actual=safe_actual,
            tolerances=safe_tolerances,
            result=result,
            details=safe_details,
            executed_by=executed_by,
        )
        db.session.add(row)
        db.session.commit()
        payload["validation_run_id"] = row.id
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="SPC 2026.2 進階分析固定基準確效")
    parser.add_argument("--persist", action="store_true", help="將本次 PASS／FAIL 保存到目前資料庫")
    parser.add_argument("--executed-by", type=int, default=None, help="確效執行者使用者 ID")
    args = parser.parse_args()

    if args.persist:
        from backend.app import app

        with app.app_context():
            payload = run_advanced_regression(
                executed_by=args.executed_by,
                persist=True,
            )
    else:
        payload = run_advanced_regression()
    print(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False))
    if payload["result"] == "PASS":
        print(f"\n{PASS_LINE}")
        return 0
    print("\n[FAIL] SPC 2026.2 進階分析確效失敗；請依 details 修正差異。")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
