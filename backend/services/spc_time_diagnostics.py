"""SPC 2026.2 時間相依分布模型的可重現診斷。"""

from __future__ import annotations

from math import isfinite
from typing import Any, Iterable, Mapping, Sequence
import warnings

import numpy as np
from scipy import stats as scipy_stats

from .spc_contracts import SpcChartSet, SpcSubgroup


DIAGNOSTIC_VERSION = "2026.2"
MIN_SUBGROUPS = 25
MIN_SEGMENT = 5
TIME_MODELS = ("A1", "A2", "B", "C1", "C2", "C3", "C4", "D")


def _validate_alpha(alpha: float) -> float:
    alpha = float(alpha)
    if not isfinite(alpha) or not 0 < alpha < 1:
        raise ValueError("alpha 必須是介於 0 與 1 間的有限數值")
    return alpha


def _holm(records: Sequence[Mapping[str, Any]], alpha: float) -> list[dict[str, Any]]:
    """以 Holm 校正保存所有原始值、校正值及逐項拒絕門檻。"""
    output = [dict(record) for record in records]
    ordered = sorted(range(len(output)), key=lambda index: (float(output[index].get("raw_p_value", 1.0)), index))
    adjusted = 0.0
    may_reject = True
    for rank, index in enumerate(ordered):
        row = output[index]
        raw = float(row.get("raw_p_value", 1.0))
        raw = min(1.0, max(0.0, raw if isfinite(raw) else 1.0))
        divisor = len(output) - rank
        adjusted = max(adjusted, min(1.0, raw * divisor))
        threshold = alpha / divisor
        reject = bool(may_reject and raw <= threshold)
        may_reject = may_reject and reject
        row.update(raw_p_value=raw, adjusted_p_value=adjusted, threshold=threshold, reject=reject)
    return output


def _trend(means: np.ndarray, alpha: float):
    indexes = np.arange(means.size, dtype=float)
    tau, p_value = scipy_stats.kendalltau(indexes, means)
    slope = scipy_stats.theilslopes(means, indexes).slope
    rows = _holm([{"index_start": 0, "index_end": int(means.size - 1), "tau": float(tau) if isfinite(float(tau)) else None, "slope": float(slope) if isfinite(float(slope)) else None, "raw_p_value": float(p_value) if isfinite(float(p_value)) else 1.0}], alpha)
    row = rows[0]
    return {"method": "Kendall_tau_Theil_Sen", "indexes": list(range(means.size)), "tau": row["tau"], "slope": row["slope"], "detected": bool(row["reject"] and row["slope"] is not None and abs(row["slope"]) > 1e-12)}, rows


def _recursive_welch(means: np.ndarray, alpha: float):
    selected_keys, all_rows, segments = [], [], [(0, int(means.size))]
    while segments:
        start, end = segments.pop(0)
        rows = []
        for split in range(start + MIN_SEGMENT, end - MIN_SEGMENT + 1):
            left, right = means[start:split], means[split:end]
            if np.std(left, ddof=1) <= 1e-12 and np.std(right, ddof=1) <= 1e-12:
                statistic = 0.0 if float(np.mean(left)) == float(np.mean(right)) else float("inf")
                p_value = 1.0 if statistic == 0 else 0.0
            else:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore", RuntimeWarning)
                    statistic, p_value = scipy_stats.ttest_ind(left, right, equal_var=False)
            rows.append({"window_start": start, "window_end": end - 1, "index": split, "statistic": float(statistic) if isfinite(float(statistic)) else None, "raw_p_value": float(p_value) if isfinite(float(p_value)) else 1.0})
        all_rows.extend(rows)
        # 遞迴時先以目前視窗的 Holm 結果選擇唯一切點；所有視窗完成後，
        # 再把完整比較集合視為同一檢定家族重新校正，供正式判定與稽核。
        hits = [row for row in _holm(rows, alpha) if row["reject"]]
        if hits:
            chosen = min(hits, key=lambda row: (row["adjusted_p_value"], row["index"]))
            selected_keys.append((chosen["window_start"], chosen["window_end"], chosen["index"]))
            split = int(chosen["index"])
            if split - start >= 2 * MIN_SEGMENT:
                segments.append((start, split))
            if end - split >= 2 * MIN_SEGMENT:
                segments.append((split, end))
    corrected_rows = _holm(all_rows, alpha)
    selected = set(selected_keys)
    accepted = [
        row for row in corrected_rows
        if row["reject"] and (
            row["window_start"], row["window_end"], row["index"]
        ) in selected
    ]
    return {"method": "recursive_welch", "min_segment": MIN_SEGMENT, "detected": bool(accepted), "change_points": sorted(int(row["index"]) for row in accepted), "windows": accepted}, corrected_rows


def _variance(subgroups: Sequence[SpcSubgroup], alpha: float):
    residuals = [np.asarray(group.values, dtype=float) - float(np.mean(group.values)) for group in subgroups]
    rows = []
    for split in range(MIN_SEGMENT, len(residuals) - MIN_SEGMENT + 1):
        left, right = np.concatenate(residuals[:split]), np.concatenate(residuals[split:])
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            statistic, p_value = scipy_stats.levene(left, right, center="median")
        rows.append({"window_start": 0, "window_end": len(residuals) - 1, "index": split, "statistic": float(statistic) if isfinite(float(statistic)) else None, "raw_p_value": float(p_value) if isfinite(float(p_value)) else 1.0})
    rows = _holm(rows, alpha)
    hits = [row for row in rows if row["reject"]]
    return {"method": "Levene_median_windows", "min_segment": MIN_SEGMENT, "detected": bool(hits), "change_indexes": [int(row["index"]) for row in hits], "windows": hits}, rows


def _instantaneous(subgroups: Sequence[SpcSubgroup], alpha: float):
    residual_groups = [
        (np.asarray(group.values, dtype=float) - np.mean(group.values))
        / np.std(group.values, ddof=1)
        for group in subgroups
        if len(group.values) > 1 and np.std(group.values, ddof=1) > 1e-12
    ]
    if not residual_groups:
        return {
            "available": False,
            "reason_code": "INSTANTANEOUS_DISTRIBUTION_UNAVAILABLE",
        }, []
    residuals = np.concatenate(residual_groups)
    if residuals.size < 8 or np.std(residuals, ddof=1) <= 1e-12:
        return {"available": False, "reason_code": "INSTANTANEOUS_DISTRIBUTION_UNAVAILABLE"}, []
    statistic, p_value = scipy_stats.normaltest(residuals)
    rows = _holm([{"index_start": 0, "index_end": int(residuals.size - 1), "statistic": float(statistic), "raw_p_value": float(p_value)}], alpha)
    row = rows[0]
    return {"available": True, "method": "D_Agostino_Pearson", "statistic": row["statistic"], "p_value": row["raw_p_value"], "adjusted_p_value": row["adjusted_p_value"], "threshold": row["threshold"], "normal": not row["reject"]}, rows


def _modality(values: np.ndarray):
    if values.size < 8 or not np.all(np.isfinite(values)) or np.std(values, ddof=1) <= 1e-12:
        return {"available": False, "reason_code": "AGGREGATE_MODALITY_UNAVAILABLE"}
    std = float(np.std(values, ddof=1))
    grid = np.linspace(float(np.min(values) - .5 * std), float(np.max(values) + .5 * std), 512)
    try:
        kde = scipy_stats.gaussian_kde(values)
    except (ValueError, np.linalg.LinAlgError):
        return {"available": False, "reason_code": "AGGREGATE_MODALITY_UNAVAILABLE"}
    density = kde(grid)
    peaks = [index for index in range(1, 511) if density[index] >= density[index - 1] and density[index] > density[index + 1] and density[index] >= .1 * max(density)]
    return {"available": True, "method": "fixed_grid_kde", "grid_points": 512, "bandwidth": float(kde.factor), "peak_indexes": peaks, "peak_values": [float(grid[index]) for index in peaks], "peak_threshold": .1, "peak_count": len(peaks), "unimodal": len(peaks) <= 1}


def _chart_limit_evidence(chart_set: SpcChartSet) -> dict[str, Any]:
    """保存位置圖與變異圖超限點，讓圖表穩定性參與模型分類。"""

    result = {}
    for name, series in (
        ("location", chart_set.location),
        ("variation", chart_set.variation),
    ):
        points = []
        for index, (value, lower, upper) in enumerate(
            zip(series.values, series.lcl, series.ucl)
        ):
            numeric = tuple(
                float(item) if item is not None else float("nan")
                for item in (value, lower, upper)
            )
            if not all(isfinite(item) for item in numeric):
                continue
            observed, lcl, ucl = numeric
            if observed < lcl or observed > ucl:
                points.append({
                    "index": index,
                    "value": observed,
                    "lcl": lcl,
                    "ucl": ucl,
                })
        result[name] = {
            "method": "point_specific_control_limits",
            "detected": bool(points),
            "indexes": [point["index"] for point in points],
            "points": points,
        }
    return result


def diagnose_time_model(chart_set: SpcChartSet, subgroups: Iterable[SpcSubgroup], distribution: Mapping[str, Any], *, alpha: float = .05) -> dict[str, Any]:
    """產生含完整可稽核證據的 A1/A2/B/C1-C4/D 候選，不自動確認。"""
    alpha = _validate_alpha(alpha)
    groups = tuple(subgroups)
    means = np.asarray(chart_set.location.values, dtype=float)
    base = {"diagnostic_version": DIAGNOSTIC_VERSION, "alpha": alpha, "candidate": None, "candidate_options": [], "confirmed": False, "statistically_controlled": False}
    if len(groups) < MIN_SUBGROUPS:
        return {**base, "reason_code": "TIME_DIAGNOSTIC_SAMPLE_INSUFFICIENT", "evidence": {"subgroup_count": len(groups), "minimum_subgroups": MIN_SUBGROUPS}}
    if means.size != len(groups):
        raise ValueError("管制圖位置點數必須與子組數一致")
    if not np.all(np.isfinite(means)):
        raise ValueError("管制圖位置資料必須全部為有限數值")
    for group in groups:
        values = np.asarray(group.values, dtype=float)
        distribution_values = np.asarray(
            group.distribution_values or group.values, dtype=float
        )
        if values.size == 0 or not np.all(np.isfinite(values)):
            raise ValueError("時間模型子組資料必須為非空的有限數值")
        if distribution_values.size == 0 or not np.all(np.isfinite(distribution_values)):
            raise ValueError("時間模型分布資料必須為非空的有限數值")
    trend, trend_rows = _trend(means, alpha)
    changes, change_rows = _recursive_welch(means, alpha)
    variance, variance_rows = _variance(groups, alpha)
    values = np.concatenate([np.asarray(group.distribution_values or group.values, dtype=float) for group in groups])
    between_scale = float(np.std(means, ddof=1))
    within_scales = [
        float(np.std(group.values, ddof=1)) if len(group.values) > 1 else 0.0
        for group in groups
    ]
    location_threshold = max(1e-12, float(np.median(within_scales)) * .25)
    random_location = bool(between_scale > location_threshold)
    location_change = {
        "method": "between_within_scale_ratio",
        "observed": between_scale,
        "threshold": location_threshold,
        "within_scale_median": float(np.median(within_scales)),
        "detected": random_location,
    }
    instantaneous, instantaneous_rows = _instantaneous(groups, alpha)
    chart_stability = _chart_limit_evidence(chart_set)
    evidence = {"trend": trend, "change_points": changes, "variance_change": variance, "location_change": location_change, "chart_stability": chart_stability, "instantaneous_distribution": instantaneous, "aggregate_modality": _modality(values), "multiple_testing": {"method": "Holm", "families": {"trend": trend_rows, "mean_change": change_rows, "variance_change": variance_rows, "instantaneous_distribution": instantaneous_rows}}, "thresholds": {"alpha": alpha, "minimum_subgroups": MIN_SUBGROUPS, "min_segment": MIN_SEGMENT, "random_location_within_scale_ratio": .25}, "subgroup_count": len(groups)}
    location_changed = bool(
        trend["detected"]
        or changes["detected"]
        or random_location
        or chart_stability["location"]["detected"]
    )
    variance_changed = bool(
        variance["detected"] or chart_stability["variation"]["detected"]
    )
    if variance_changed and location_changed:
        candidate = "D"
    elif variance_changed:
        candidate = "B"
    elif trend["detected"]:
        candidate = "C3"
    elif changes["detected"]:
        candidate = "C4"
    elif location_changed:
        candidate = "C1" if distribution.get("normal_ok") else "C2"
    else:
        candidate = "A1" if distribution.get("normal_ok") else "A2"
    return {**base, "candidate": candidate, "candidate_options": list(TIME_MODELS), "statistically_controlled": candidate in {"A1", "A2"}, "reason_code": None, "evidence": evidence}
