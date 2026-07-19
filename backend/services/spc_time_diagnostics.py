"""SPC 2026.2 時間相依分布模型的可重現診斷。"""

from __future__ import annotations

from math import isfinite
from typing import Any, Iterable, Mapping, Sequence
import warnings

import numpy as np
from scipy import stats as scipy_stats

from .spc_contracts import SpcChartSet, SpcSubgroup
from .spc_distribution import assess_distribution
from .spc_stability import evaluate_study_stability


DIAGNOSTIC_VERSION = "2026.2"
MIN_SUBGROUPS = 25
MIN_SEGMENT = 5
RANDOM_EFFECT_THRESHOLD = 0.05
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


def _instantaneous(subgroups: Sequence[SpcSubgroup], alpha: float):
    """評估去除各子組位置後的瞬時分布，不使用合成分布答案。"""

    centered = [
        np.asarray(group.values, dtype=float) - float(np.mean(group.values))
        for group in subgroups
    ]
    residuals = np.concatenate(centered)
    scale = float(np.std(residuals, ddof=1))
    if residuals.size < 20 or scale <= 1e-12:
        return {
            "available": False,
            "accepted": False,
            "unimodal": False,
            "normal": None,
            "reason_code": "INSTANTANEOUS_DISTRIBUTION_UNAVAILABLE",
        }, []
    standardized = residuals / scale
    fitted = assess_distribution(standardized.tolist(), alpha=alpha)
    modality = _modality(standardized)
    normal_candidate = next(
        (item for item in fitted.get("candidates", []) if item.get("model") == "normal"),
        None,
    )
    if normal_candidate is None:
        return {
            "available": False,
            "accepted": False,
            "unimodal": False,
            "normal": None,
            "reason_code": "INSTANTANEOUS_DISTRIBUTION_UNAVAILABLE",
        }, []
    rows = _holm([{
        "index_start": 0,
        "index_end": int(standardized.size - 1),
        "statistic": float(normal_candidate["statistic"]),
        "raw_p_value": float(normal_candidate["p_value"]),
    }], alpha)
    row = rows[0]
    normal = not row["reject"]
    unimodal = bool(modality.get("available") and modality.get("unimodal"))
    # A2 不要求另一個參數分布已配適；充分樣本、拒絕常態且 KDE 單峰，
    # 即是可確認的「非常態單峰瞬時分布」證據。
    accepted = unimodal
    return {
        "available": True,
        "accepted": accepted,
        "unimodal": unimodal,
        "normal": normal,
        "method": "centered_residual_anderson_darling",
        "statistic": row["statistic"],
        "p_value": row["raw_p_value"],
        "adjusted_p_value": row["adjusted_p_value"],
        "threshold": row["threshold"],
        "residual_scale": scale,
        "sample_count": int(standardized.size),
        "acceptance_method": "normal_fit_or_unimodal_shape",
        "modality": modality,
        "reason_code": None if accepted else "INSTANTANEOUS_DISTRIBUTION_UNAVAILABLE",
    }, rows


def _validate_chart_lengths(chart_set: SpcChartSet, subgroup_count: int) -> None:
    """公開診斷契約不得以 zip 靜默截斷不一致的管制圖序列。"""

    expected = subgroup_count
    for name, series in (
        ("location", chart_set.location),
        ("variation", chart_set.variation),
    ):
        for field in ("values", "cl", "ucl", "lcl"):
            if len(getattr(series, field)) != expected:
                raise ValueError(f"{name}.{field} 長度必須與子組數一致")
    if len(chart_set.subgroup_sizes) != expected:
        raise ValueError("subgroup_sizes 長度必須與子組數一致")
    if chart_set.variation_source_pairs and len(chart_set.variation_source_pairs) != expected:
        raise ValueError("variation_source_pairs 長度必須與子組數一致")


def _random_location_effect(
    subgroups: Sequence[SpcSubgroup], alpha: float
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """以實際 n_i 的 one-way F 與 omega-squared 判斷隨機位置效應。"""

    arrays = [np.asarray(group.values, dtype=float) for group in subgroups]
    sizes = [int(values.size) for values in arrays]
    count = sum(sizes)
    grand_mean = float(sum(float(np.sum(values)) for values in arrays) / count)
    means = [float(np.mean(values)) for values in arrays]
    ss_between = float(sum(
        size * (mean - grand_mean) ** 2
        for size, mean in zip(sizes, means)
    ))
    ss_within = float(sum(
        float(np.sum((values - mean) ** 2))
        for values, mean in zip(arrays, means)
    ))
    df_between = len(arrays) - 1
    df_within = count - len(arrays)
    ms_between = ss_between / df_between
    ms_within = ss_within / df_within if df_within > 0 else 0.0
    if ms_within <= 1e-12:
        statistic = 0.0 if ms_between <= 1e-12 else float("inf")
        p_value = 1.0 if statistic == 0 else 0.0
    else:
        statistic = ms_between / ms_within
        p_value = float(scipy_stats.f.sf(statistic, df_between, df_within))
    total = ss_between + ss_within
    omega_squared = max(
        0.0,
        (ss_between - df_between * ms_within) / (total + ms_within)
        if total + ms_within > 0 else 0.0,
    )
    rows = _holm([{
        "statistic": float(statistic) if isfinite(statistic) else None,
        "raw_p_value": p_value,
        "df_between": df_between,
        "df_within": df_within,
    }], alpha)
    row = rows[0]
    reject = bool(row["reject"] and omega_squared >= RANDOM_EFFECT_THRESHOLD)
    evidence = {
        "method": "one_way_random_effect_f",
        "statistic": row["statistic"],
        "raw_p_value": row["raw_p_value"],
        "adjusted_p_value": row["adjusted_p_value"],
        "threshold": row["threshold"],
        "statistical_reject": row["reject"],
        "omega_squared": float(omega_squared),
        "effect_threshold": RANDOM_EFFECT_THRESHOLD,
        "reject": reject,
        "subgroup_sizes": sizes,
        "grand_mean": grand_mean,
        "ss_between": ss_between,
        "ss_within": ss_within,
        "df_between": df_between,
        "df_within": df_within,
    }
    return evidence, rows


def _formal_stability_evidence(stability: Mapping[str, Any]) -> dict[str, Any]:
    result = {
        "evaluated": bool(stability.get("evaluated")),
        "stable": stability.get("stable"),
        "rules_used": list(stability.get("rules_used") or []),
    }
    for name in ("location", "variation"):
        chart = stability.get(name) or {}
        result[name] = {
            "evaluated": bool(chart.get("evaluated")),
            "stable": chart.get("stable"),
            "rules_used": list(chart.get("rules_used") or []),
            "violations": [dict(item) for item in chart.get("violations") or []],
        }
    return result


def _aggregate_normality(
    distribution: Mapping[str, Any], modality: Mapping[str, Any], alpha: float
) -> tuple[bool | None, dict[str, Any]]:
    """辨識合成分布常態性；替代分布不必通過才可判 C2。"""

    if not modality.get("available") or not modality.get("unimodal"):
        return None, {
            "available": False,
            "reason_code": "AGGREGATE_MODALITY_UNAVAILABLE",
        }
    normal_candidate = next(
        (
            item for item in distribution.get("candidates", [])
            if item.get("model") == "normal"
        ),
        None,
    )
    if normal_candidate is not None:
        p_value = normal_candidate.get("p_value", normal_candidate.get("raw_p_value"))
        if p_value is not None and isfinite(float(p_value)):
            threshold = float(distribution.get("alpha") or alpha)
            normal = bool(float(p_value) >= threshold)
            return normal, {
                "available": True,
                "method": normal_candidate.get("method") or "normal_candidate",
                "p_value": float(p_value),
                "threshold": threshold,
                "normal": normal,
            }
    explicit = distribution.get("normal_ok")
    if isinstance(explicit, (bool, np.bool_)):
        return bool(explicit), {
            "available": True,
            "method": "explicit_normal_ok",
            "p_value": None,
            "threshold": alpha,
            "normal": bool(explicit),
        }
    return None, {
        "available": False,
        "reason_code": "AGGREGATE_NORMALITY_UNAVAILABLE",
    }


def diagnose_time_model(
    chart_set: SpcChartSet,
    subgroups: Iterable[SpcSubgroup],
    distribution: Mapping[str, Any],
    *,
    stability: Mapping[str, Any] | None = None,
    alpha: float = .05,
) -> dict[str, Any]:
    """產生含完整可稽核證據的 A1/A2/B/C1-C4/D 候選，不自動確認。"""

    alpha = _validate_alpha(alpha)
    groups = tuple(subgroups)
    _validate_chart_lengths(chart_set, len(groups))
    means = np.asarray(chart_set.location.values, dtype=float)
    base = {"diagnostic_version": DIAGNOSTIC_VERSION, "alpha": alpha, "candidate": None, "candidate_options": [], "confirmed": False, "statistically_controlled": False}
    if len(groups) < MIN_SUBGROUPS:
        return {**base, "reason_code": "TIME_DIAGNOSTIC_SAMPLE_INSUFFICIENT", "evidence": {"subgroup_count": len(groups), "minimum_subgroups": MIN_SUBGROUPS}}
    if not np.all(np.isfinite(means)):
        raise ValueError("管制圖位置資料必須全部為有限數值")
    for name, series in (("location", chart_set.location), ("variation", chart_set.variation)):
        numeric_values = [float(value) for value in series.values if value is not None]
        if not all(isfinite(value) for value in numeric_values):
            raise ValueError(f"{name}.values 的非空值必須全部為有限數值")
        for field in ("cl", "ucl", "lcl"):
            if not np.all(np.isfinite(np.asarray(getattr(series, field), dtype=float))):
                raise ValueError(f"{name}.{field} 必須全部為有限數值")
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
    random_location, random_location_rows = _random_location_effect(groups, alpha)
    values = np.concatenate([
        np.asarray(group.distribution_values or group.values, dtype=float)
        for group in groups
    ])
    instantaneous, instantaneous_rows = _instantaneous(groups, alpha)
    modality = _modality(values)
    aggregate_normal, aggregate_normality = _aggregate_normality(
        distribution, modality, alpha
    )
    formal = _formal_stability_evidence(
        stability if stability is not None else evaluate_study_stability(chart_set)
    )
    evidence = {
        "trend": trend,
        "change_points": changes,
        "variance_change": variance,
        "random_location": random_location,
        "formal_stability": formal,
        "instantaneous_distribution": instantaneous,
        "aggregate_modality": modality,
        "aggregate_normality": aggregate_normality,
        "aggregate_distribution": dict(distribution),
        "multiple_testing": {
            "method": "Holm",
            "families": {
                "trend": trend_rows,
                "mean_change": change_rows,
                "variance_change": variance_rows,
                "random_location": random_location_rows,
                "instantaneous_distribution": instantaneous_rows,
            },
        },
        "thresholds": {
            "alpha": alpha,
            "minimum_subgroups": MIN_SUBGROUPS,
            "min_segment": MIN_SEGMENT,
            "random_location_omega_squared": RANDOM_EFFECT_THRESHOLD,
        },
        "subgroup_count": len(groups),
    }
    location_changed = bool(
        formal["location"]["stable"] is False
        or trend["detected"]
        or changes["detected"]
        or random_location["reject"]
    )
    variance_changed = bool(
        formal["variation"]["stable"] is False or variance["detected"]
    )
    reason_code = None
    if variance_changed and location_changed:
        candidate = "D"
    elif variance_changed:
        candidate = "B"
    elif trend["detected"]:
        candidate = "C3"
    elif changes["detected"]:
        candidate = "C4"
    elif location_changed:
        if aggregate_normal is None:
            candidate = None
            reason_code = "TIME_DIAGNOSTIC_DISTRIBUTION_UNAVAILABLE"
        else:
            candidate = "C1" if aggregate_normal else "C2"
    elif formal.get("stable") is not True:
        candidate = None
        reason_code = "TIME_DIAGNOSTIC_STABILITY_UNAVAILABLE"
    elif not instantaneous.get("available") or not instantaneous.get("accepted"):
        candidate = None
        reason_code = "TIME_DIAGNOSTIC_DISTRIBUTION_UNAVAILABLE"
    else:
        candidate = "A1" if instantaneous.get("normal") else "A2"
    return {
        **base,
        "candidate": candidate,
        "candidate_options": list(TIME_MODELS) if candidate is not None else [],
        "statistically_controlled": bool(
            formal.get("stable") is True and candidate in {"A1", "A2"}
        ),
        "reason_code": reason_code,
        "evidence": evidence,
    }
