from collections import defaultdict
from typing import Any, Dict, List, Optional

import numpy as np
from scipy import stats as scipy_stats

from .spc_constants import SPC_CONSTANTS


def calculate_control_limits(
    avgs: List[float],
    ranges: List[float],
    subgroup_sizes: List[int],
    baseline_limit: int = 25,
) -> Dict[str, float]:
    """依基準子群體計算 X-bar/R 管制限。"""
    if len(avgs) < 5:
        return {
            "x_cl": 0.0,
            "x_ucl": 0.0,
            "x_lcl": 0.0,
            "r_cl": 0.0,
            "r_ucl": 0.0,
            "r_lcl": 0.0,
            "d2": 2.326,
            "avg_n": 5,
            "baseline_count": 0,
        }

    baseline_count = min(baseline_limit, len(avgs))
    base_avgs = avgs[:baseline_count]
    base_ranges = ranges[:baseline_count]
    base_ns = subgroup_sizes[:baseline_count]

    avg_n = round(float(np.mean(base_ns)))
    avg_n = max(2, min(10, avg_n))
    A2, D3, D4, d2 = SPC_CONSTANTS[avg_n]

    x_cl = float(np.mean(base_avgs))
    r_cl = float(np.mean(base_ranges))
    x_ucl = x_cl + A2 * r_cl
    x_lcl = max(x_cl - A2 * r_cl, 0)

    return {
        "x_cl": x_cl,
        "x_ucl": x_ucl,
        "x_lcl": x_lcl,
        "r_cl": r_cl,
        "r_ucl": D4 * r_cl,
        "r_lcl": D3 * r_cl,
        "d2": d2,
        "avg_n": avg_n,
        "baseline_count": baseline_count,
    }


def calculate_process_capability(
    avgs: List[float],
    all_values: List[float],
    r_cl: float,
    d2: float,
    tolerance_limits: Dict[str, Any],
    include_reason: bool = True,
) -> Dict[str, Any]:
    """計算 Cp/Cpk/Pp/Ppk 與 PPM，支援雙側與單側下限規格。"""
    process_capability: Dict[str, Any] = {"available": False}
    if include_reason:
        process_capability["reason"] = "no_tolerance"

    usl = tolerance_limits.get("USL")
    lsl = tolerance_limits.get("LSL")

    if len(avgs) < 5:
        if (usl is not None and lsl is not None) or (tolerance_limits.get("one_sided") == "lower" and lsl is not None):
            if include_reason:
                process_capability["reason"] = "insufficient_data"
            process_capability["valid_count"] = len(avgs)
        return process_capability

    x_bar = float(np.mean(avgs))
    sigma_within = r_cl / d2 if r_cl > 0 else 0
    sigma_overall = float(np.std(all_values, ddof=1)) if len(all_values) >= 2 else 0

    if tolerance_limits.get("one_sided") == "lower" and lsl is not None:
        process_capability.update({
            "available": True,
            "one_sided": "lower",
            "lsl": float(lsl),
            "usl": None,
        })
        if sigma_within > 0:
            cpl = (x_bar - float(lsl)) / (3 * sigma_within)
            process_capability.update({"cp": None, "cpk": round(cpl, 3), "cpu": None, "cpl": round(cpl, 3)})
        else:
            process_capability.update({"cp": None, "cpk": None, "cpu": None, "cpl": None})
        if sigma_overall > 0:
            ppl = (x_bar - float(lsl)) / (3 * sigma_overall)
            process_capability.update({"pp": None, "ppk": round(ppl, 3), "ppu": None, "ppl": round(ppl, 3)})
        else:
            process_capability.update({"pp": None, "ppk": None, "ppu": None, "ppl": None})
        process_capability["sigma_within"] = round(sigma_within, 6)
        process_capability["sigma_overall"] = round(sigma_overall, 6)
        return process_capability

    if usl is None or lsl is None:
        return process_capability

    process_capability.update({
        "available": True,
        "usl": float(usl),
        "lsl": float(lsl),
    })

    if sigma_within > 0:
        cp = (float(usl) - float(lsl)) / (6 * sigma_within)
        cpu = (float(usl) - x_bar) / (3 * sigma_within)
        cpl = (x_bar - float(lsl)) / (3 * sigma_within)
        cpk = min(cpu, cpl)
        process_capability.update({
            "cp": round(cp, 3),
            "cpk": round(cpk, 3),
            "cpu": round(cpu, 3),
            "cpl": round(cpl, 3),
        })
    else:
        process_capability.update({"cp": None, "cpk": None, "cpu": None, "cpl": None})

    if sigma_overall > 0:
        pp = (float(usl) - float(lsl)) / (6 * sigma_overall)
        ppu = (float(usl) - x_bar) / (3 * sigma_overall)
        ppl = (x_bar - float(lsl)) / (3 * sigma_overall)
        ppk = min(ppu, ppl)
        z_upper = (float(usl) - x_bar) / sigma_overall
        z_lower = (x_bar - float(lsl)) / sigma_overall
        ppm_upper = round(float(scipy_stats.norm.sf(z_upper) * 1_000_000), 1)
        ppm_lower = round(float(scipy_stats.norm.sf(z_lower) * 1_000_000), 1)
        process_capability.update({
            "pp": round(pp, 3),
            "ppk": round(ppk, 3),
            "ppu": round(ppu, 3),
            "ppl": round(ppl, 3),
            "ppm": {"upper": ppm_upper, "lower": ppm_lower, "total": round(ppm_upper + ppm_lower, 1)},
        })
    else:
        process_capability.update({
            "pp": None,
            "ppk": None,
            "ppu": None,
            "ppl": None,
            "ppm": {"upper": 0, "lower": 0, "total": 0},
        })

    process_capability["sigma_within"] = round(sigma_within, 6)
    process_capability["sigma_overall"] = round(sigma_overall, 6)
    return process_capability


def calculate_distribution_stats(all_values: List[float]) -> Dict[str, Any]:
    """計算偏態、峰態與常態性文字判讀。"""
    if len(all_values) < 4:
        return {}

    arr = np.array(all_values, dtype=float)
    skewness = round(float(scipy_stats.skew(arr)), 3)
    kurtosis = round(float(scipy_stats.kurtosis(arr)), 3)
    sk = abs(skewness)
    ku = abs(kurtosis)

    if sk < 0.5 and ku < 1.0:
        normality = "good"
        normality_label = "分佈接近常態"
    elif sk < 1.0 and ku < 2.0:
        normality = "moderate"
        normality_label = "分佈略偏，Cpk 僅供參考"
    else:
        normality = "poor"
        normality_label = "分佈明顯非常態，Cpk 可能不準確"

    return {
        "skewness": skewness,
        "kurtosis": kurtosis,
        "normality": normality,
        "normality_label": normality_label,
    }


def calculate_cpk_trend(
    all_values: List[float],
    dates_valid: List[str],
    subgroup_sizes: List[int],
    usl: Optional[float],
    lsl: Optional[float],
    is_minmax: bool = False,
) -> List[Dict[str, Any]]:
    """依月份彙整個別值並計算月 Cpk 趨勢。"""
    if usl is None or lsl is None or len(subgroup_sizes) < 5:
        return []

    monthly_values: Dict[str, List[float]] = defaultdict(list)
    val_idx = 0
    for i, subgroup_size in enumerate(subgroup_sizes):
        month_key = dates_valid[i][:7] if i < len(dates_valid) and dates_valid[i] else "unknown"
        n_raw = subgroup_size * 2 if is_minmax else subgroup_size
        for _ in range(n_raw):
            if val_idx < len(all_values):
                monthly_values[month_key].append(all_values[val_idx])
                val_idx += 1

    cpk_trend = []
    for month_key in sorted(monthly_values.keys()):
        vals = monthly_values[month_key]
        if len(vals) >= 5:
            m_mean = float(np.mean(vals))
            m_std = float(np.std(vals, ddof=1))
            if m_std > 0:
                m_cpu = (float(usl) - m_mean) / (3 * m_std)
                m_cpl = (m_mean - float(lsl)) / (3 * m_std)
                cpk_trend.append({"month": month_key, "cpk": round(min(m_cpu, m_cpl), 3), "count": len(vals)})

    return cpk_trend
