from collections import defaultdict
from typing import Any, Dict, List, Optional

import numpy as np
from scipy import stats as scipy_stats

from .spc_constants import SPC_CONSTANTS
from .spc_distribution import assess_distribution, dist_quantiles, tail_ppm
from .spc_targets import resolve_targets


def calculate_control_limits(
    avgs: List[float],
    ranges: List[float],
    subgroup_sizes: List[int],
    baseline_limit: int = 25,
) -> Dict[str, Any]:
    """依基準子組估計變異，並按每組實際 n 產生 X̄/R 界限。

    此函式是舊 API 的相容包裝。新研究流程使用 ``spc_chart_engine``；
    這裡仍保留純量欄位，但逐點陣列才是不等子組的正式界限。
    """
    if len(avgs) < 5:
        empty_limits = [0.0] * len(avgs)
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
            "x_ucls": empty_limits,
            "x_lcls": empty_limits,
            "r_cls": empty_limits,
            "r_ucls": empty_limits,
            "r_lcls": empty_limits,
            "variable_subgroup_size": len(set(subgroup_sizes)) > 1,
            "sigma_within": 0.0,
        }

    baseline_count = min(baseline_limit, len(avgs))
    base_avgs = avgs[:baseline_count]
    base_ranges = ranges[:baseline_count]
    base_ns = subgroup_sizes[:baseline_count]

    normalized_base_ns = [max(2, min(10, int(n))) for n in base_ns]
    sigma_estimates = [
        float(group_range) / SPC_CONSTANTS[n][3]
        for group_range, n in zip(base_ranges, normalized_base_ns)
    ]
    sigma_within = float(np.mean(sigma_estimates))
    x_cl = float(np.mean(base_avgs))
    point_ns = [max(2, min(10, int(n))) for n in subgroup_sizes]
    x_ucls = []
    x_lcls = []
    r_cls = []
    r_ucls = []
    r_lcls = []
    for n in point_ns:
        a2, d3, d4, d2_n = SPC_CONSTANTS[n]
        expected_range = d2_n * sigma_within
        x_ucls.append(x_cl + a2 * expected_range)
        x_lcls.append(x_cl - a2 * expected_range)
        r_cls.append(expected_range)
        r_ucls.append(d4 * expected_range)
        r_lcls.append(d3 * expected_range)

    variable_n = len(set(point_ns)) > 1
    avg_n = max(2, min(10, round(float(np.mean(base_ns)))))
    d2 = SPC_CONSTANTS[avg_n][3]

    # 固定 n 時完全維持舊純量語意；不等 n 時純量只提供保守相容值，
    # 新契約與前端必須使用上方逐點陣列。
    x_ucl = x_ucls[0] if not variable_n else max(x_ucls)
    x_lcl = x_lcls[0] if not variable_n else min(x_lcls)
    r_cl = r_cls[0] if not variable_n else float(np.mean(r_cls))
    r_ucl = r_ucls[0] if not variable_n else max(r_ucls)
    r_lcl = r_lcls[0] if not variable_n else min(r_lcls)

    return {
        "x_cl": x_cl,
        "x_ucl": x_ucl,
        "x_lcl": x_lcl,
        "r_cl": r_cl,
        "r_ucl": r_ucl,
        "r_lcl": r_lcl,
        "d2": d2,
        "avg_n": avg_n,
        "baseline_count": baseline_count,
        "x_ucls": x_ucls,
        "x_lcls": x_lcls,
        "r_cls": r_cls,
        "r_ucls": r_ucls,
        "r_lcls": r_lcls,
        "variable_subgroup_size": variable_n,
        "sigma_within": sigma_within,
    }


def calculate_process_capability(
    avgs: List[float],
    all_values: List[float],
    r_cl: float,
    d2: float,
    tolerance_limits: Dict[str, Any],
    include_reason: bool = True,
    stability: Optional[Dict[str, Any]] = None,
    characteristic_class: str = "其他",
    confidence: str = "95%",
    field: Optional[str] = None,
    dist: Optional[Dict[str, Any]] = None,
    time_model: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """計算能力/績效指數 — AIAG-VDA SPC 2026。

    - Pp/Ppk 與 Cp/Cpk 公式相同，皆採整體變異（§6.2、§6.8.2.1 常態 G 法）
    - 僅在兩圖穩定且時間模型已確認為 A1/A2 時回報 Cp/Cpk
    - 組內變異（R̄/d2）之指數另列為 Cw/Cwk 參考值，不再命名為 Cp/Cpk
    - 單側規格只計算對應側指數（§6.8.2.2）
    """
    process_capability: Dict[str, Any] = {"available": False}
    if include_reason:
        process_capability["reason"] = "no_tolerance"

    usl = tolerance_limits.get("USL")
    lsl = tolerance_limits.get("LSL")
    one_sided = tolerance_limits.get("one_sided")

    has_spec = (
        (one_sided == "lower" and lsl is not None)
        or (one_sided == "upper" and usl is not None)
        or (one_sided is None and usl is not None and lsl is not None)
    )
    if len(avgs) < 5:
        if has_spec:
            if include_reason:
                process_capability["reason"] = "insufficient_data"
            process_capability["valid_count"] = len(avgs)
        return process_capability
    if not has_spec:
        return process_capability

    x_bar = float(np.mean(all_values)) if all_values else float(np.mean(avgs))
    sigma_overall = float(np.std(all_values, ddof=1)) if len(all_values) >= 2 else 0.0
    sigma_within = r_cl / d2 if r_cl > 0 else 0.0
    is_stable = bool(stability and stability.get("stable"))
    time_model_name = (time_model or {}).get("model") or (time_model or {}).get("candidate")
    time_model_confirmed = bool(
        (time_model or {}).get("confirmed") and time_model_name in {"A1", "A2"}
    )
    is_capability = is_stable and time_model_confirmed

    def _r3(v):
        return round(v, 3) if v is not None else None

    # --- 分布評估（§6.8.1）：形狀公差固定摺疊常態，其餘以 AD 檢定判斷 ---
    # 呼叫端若已算過（同一份 all_values/field）可傳入 dist 避免重複擬合（MLE 成本高）
    if dist is None:
        dist = assess_distribution(all_values, field=field)
    process_capability_dist = {
        "model": dist.get("model"), "label": dist.get("label"),
        "accepted": bool(dist.get("accepted")),
        "normal_ok": dist.get("normal_ok"), "ad_stat": dist.get("ad_stat"),
        "params": dist.get("params", ()),
        "reason_code": dist.get("reason_code"),
        "candidates": dist.get("candidates", []),
        "fit_method": dist.get("fit_method"),
        "alpha": dist.get("alpha"),
    }
    if not dist.get("accepted"):
        process_capability.update({
            "available": False,
            "reason": "distribution_unconfirmed",
            "valid_count": len(all_values),
            "pp": None, "ppk": None, "ppu": None, "ppl": None,
            "cp": None, "cpk": None, "cpu": None, "cpl": None,
            "cw": None, "cwk": None,
            "applicable": None,
            "capability_reason": dist.get("reason_code") or "DISTRIBUTION_UNCONFIRMED",
            "stability_stable": stability.get("stable") if stability else None,
            "time_model": time_model,
            "distribution": process_capability_dist,
            "ppm": {"upper": None, "lower": None, "total": None},
        })
        return process_capability
    use_percentile = dist["model"] != "normal"
    q_lo = q_mid = q_hi = None
    if use_percentile:
        q_lo, q_mid, q_hi = dist_quantiles(dist)

    # --- 整體變異指數（常態：G 法常態公式 §6.8.2.1；非常態：G 法分位數公式 §6.8.2.1）---
    p_val = pu = pl = pk = None
    if use_percentile and q_lo is not None and q_hi is not None and (q_hi - q_lo) > 0:
        # G 法分位數公式（§6.8.2.1）
        if one_sided == "lower":
            pl = (q_mid - float(lsl)) / (q_mid - q_lo) if (q_mid - q_lo) > 0 else None
            pk = pl
        elif one_sided == "upper":
            pu = (float(usl) - q_mid) / (q_hi - q_mid) if (q_hi - q_mid) > 0 else None
            pk = pu
        else:
            p_val = (float(usl) - float(lsl)) / (q_hi - q_lo)
            pu = (float(usl) - q_mid) / (q_hi - q_mid) if (q_hi - q_mid) > 0 else None
            pl = (q_mid - float(lsl)) / (q_mid - q_lo) if (q_mid - q_lo) > 0 else None
            pk = min(v for v in [pu, pl] if v is not None) if (pu is not None or pl is not None) else None
    elif sigma_overall > 0:
        # 常態：G 法退化公式（(U−L)/6s 等）
        if one_sided == "lower":
            pl = (x_bar - float(lsl)) / (3 * sigma_overall)
            pk = pl
        elif one_sided == "upper":
            pu = (float(usl) - x_bar) / (3 * sigma_overall)
            pk = pu
        else:
            p_val = (float(usl) - float(lsl)) / (6 * sigma_overall)
            pu = (float(usl) - x_bar) / (3 * sigma_overall)
            pl = (x_bar - float(lsl)) / (3 * sigma_overall)
            pk = min(pu, pl)

    # --- 組內參考指數 Cw/Cwk ---
    cw = cwk = None
    if sigma_within > 0:
        if one_sided == "lower":
            cwk = (x_bar - float(lsl)) / (3 * sigma_within)
        elif one_sided == "upper":
            cwk = (float(usl) - x_bar) / (3 * sigma_within)
        else:
            cw = (float(usl) - float(lsl)) / (6 * sigma_within)
            cwk = min(
                (float(usl) - x_bar) / (3 * sigma_within),
                (x_bar - float(lsl)) / (3 * sigma_within),
            )

    # --- PPM：只使用已確認分布；不得在樣本或擬合不足時退回常態 Z 法 ---
    ppm = tail_ppm(
        dist,
        usl=float(usl) if usl is not None else None,
        lsl=float(lsl) if (lsl is not None and one_sided != "upper") else None,
    )

    # --- 目標值（表 8-3～8-5）與達標判定 ---
    targets = resolve_targets(characteristic_class, n_values=len(all_values), confidence=confidence)
    achieved = pk is not None and pk >= targets["pk_target"]

    # 已成功計算時不得殘留初始化階段的 no_tolerance／insufficient_data 理由。
    process_capability.pop("reason", None)
    process_capability.update({
        "available": True,
        "usl": float(usl) if usl is not None else None,
        "lsl": float(lsl) if lsl is not None else None,
        "one_sided": one_sided,
        "method": "G",  # §6.8.2：G 法（常態情形之公式）
        # 績效指數（一律計算）
        "pp": _r3(p_val), "ppk": _r3(pk), "ppu": _r3(pu), "ppl": _r3(pl),
        # 能力指數（僅穩定時回報；數值同績效指數，§6.2）
        "cp": _r3(p_val) if is_capability else None,
        "cpk": _r3(pk) if is_capability else None,
        "cpu": _r3(pu) if is_capability else None,
        "cpl": _r3(pl) if is_capability else None,
        # 組內參考指數
        "cw": _r3(cw), "cwk": _r3(cwk),
        "applicable": "capability" if is_capability else "performance",
        "capability_reason": (
            None if is_capability
            else "PROCESS_UNSTABLE" if not is_stable
            else "TIME_MODEL_UNCONFIRMED"
        ),
        "stability_stable": stability.get("stable") if stability else None,
        "time_model": time_model,
        "sigma_within": round(sigma_within, 6),
        "sigma_overall": round(sigma_overall, 6),
        "ppm": ppm,
        "targets": targets,
        "distribution": process_capability_dist,
        "achieved": achieved,
        # 手冊建議 n≥125、k≥25 子組（表 6-4）；不足時標示為初步值
        "preliminary": len(all_values) < 125 or len(avgs) < 25,
    })
    return process_capability


def calculate_distribution_stats(
    all_values: List[float],
    field: Optional[str] = None,
    dist: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
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

    if dist is None:
        dist = assess_distribution(all_values, field=field)

    return {
        "skewness": skewness,
        "kurtosis": kurtosis,
        "normality": normality,
        "normality_label": normality_label,
        "model": dist["model"],
        "model_label": dist["label"],
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
