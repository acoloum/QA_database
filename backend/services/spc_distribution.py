"""統計分布評估 — AIAG-VDA SPC 2026 §6.8.1

- 形狀公差特性（圓度/同心度/直度等）理論分布為摺疊常態（§6.8.1）
- 其他特性以 Anderson-Darling 檢定常態性；非常態時擇一擬合分布
- 供 G 法（分位數法）指數計算與依分布之 PPM 估算（§6.8.2.1/6.8.2.3）
"""
from typing import Any, Dict, List, Optional

import numpy as np
from scipy import stats as scipy_stats

# 自然下界為 0 的形狀公差特性
SHAPE_FIELDS = {"同心度", "真圓度", "真直度", "圓度", "平面度", "直線度"}

MODEL_LABELS = {
    "normal": "常態分布",
    "folded_normal": "摺疊常態分布（形狀公差）",
    "lognormal": "對數常態分布",
}


def assess_distribution(all_values: List[float], field: Optional[str] = None) -> Dict[str, Any]:
    """評估適當的分布模型並擬合參數。"""
    arr = np.asarray(all_values, dtype=float)
    result: Dict[str, Any] = {
        "model": "normal",
        "label": MODEL_LABELS["normal"],
        "params": (float(np.mean(arr)) if arr.size else 0.0,
                   float(np.std(arr, ddof=1)) if arr.size >= 2 else 0.0),
        "ad_stat": None,
        "normal_ok": True,
        "n": int(arr.size),
    }
    if arr.size < 20 or float(np.std(arr, ddof=1)) == 0:
        return result  # 樣本太少：以常態近似，不做檢定

    # 形狀公差：直接採摺疊常態（§6.8.1 理論分布），不看 AD 檢定
    if field in SHAPE_FIELDS:
        c, loc, scale = scipy_stats.foldnorm.fit(arr, floc=0)
        result.update({
            "model": "folded_normal",
            "label": MODEL_LABELS["folded_normal"],
            "params": (float(c), 0.0, float(scale)),
            "normal_ok": False,
        })
        return result

    ad = scipy_stats.anderson(arr, dist="norm")
    result["ad_stat"] = float(ad.statistic)
    # 臨界值索引 2 對應顯著水準 5%
    normal_ok = ad.statistic < ad.critical_values[2]
    result["normal_ok"] = bool(normal_ok)
    if normal_ok:
        return result

    # 非常態：正值資料嘗試對數常態，以對數概似擇優；否則維持常態近似並標示
    if np.all(arr > 0):
        s, loc, scale = scipy_stats.lognorm.fit(arr, floc=0)
        ll_lognorm = float(np.sum(scipy_stats.lognorm.logpdf(arr, s, loc, scale)))
        mu, sd = float(np.mean(arr)), float(np.std(arr, ddof=1))
        ll_norm = float(np.sum(scipy_stats.norm.logpdf(arr, mu, sd)))
        if ll_lognorm > ll_norm:
            result.update({
                "model": "lognormal",
                "label": MODEL_LABELS["lognormal"],
                "params": (float(s), float(loc), float(scale)),
            })
    return result


def _frozen(dist: Dict[str, Any]):
    model = dist["model"]
    p = dist["params"]
    if model == "folded_normal":
        return scipy_stats.foldnorm(p[0], loc=p[1], scale=p[2])
    if model == "lognormal":
        return scipy_stats.lognorm(p[0], loc=p[1], scale=p[2])
    return scipy_stats.norm(p[0], p[1])


def dist_quantiles(dist: Dict[str, Any]):
    """回傳 G 法所需分位數 (X0.135%, X50%, X99.865%)（§6.8.2.1）"""
    f = _frozen(dist)
    return float(f.ppf(0.00135)), float(f.ppf(0.5)), float(f.ppf(0.99865))


def tail_ppm(dist: Dict[str, Any], usl: Optional[float], lsl: Optional[float]) -> Dict[str, float]:
    """依擬合分布估算超規 PPM（§6.8.2.3 Z 法：OOS 比例）"""
    f = _frozen(dist)
    upper = float(f.sf(usl) * 1_000_000) if usl is not None else 0.0
    lower = float(f.cdf(lsl) * 1_000_000) if lsl is not None else 0.0
    return {"upper": round(upper, 1), "lower": round(lower, 1), "total": round(upper + lower, 1)}
