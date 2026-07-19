"""AIAG & VDA SPC 2026 分布評估與 G 法分位數工具。"""

from math import isfinite
from typing import Any, Dict, List, Optional

import numpy as np
from scipy import stats as scipy_stats

from .spc_transformations import evaluate_transformations


SHAPE_FIELDS = {"同心度", "真圓度", "真直度", "圓度", "平面度", "直線度"}
MIN_DISTRIBUTION_SAMPLE = 20
DEFAULT_ALPHA = 0.05

MODEL_LABELS = {
    "normal": "常態分布",
    "folded_normal": "摺疊常態分布（形狀公差）",
    "lognormal": "對數常態分布",
}


def _base_result(n: int, alpha: float) -> Dict[str, Any]:
    return {
        "model": None,
        "label": "分布模型未確認",
        "params": (),
        "accepted": False,
        "normal_ok": False,
        "unimodal": False,
        "ad_stat": None,
        "reason_code": "DISTRIBUTION_UNCONFIRMED",
        "candidates": [],
        "fit_method": None,
        "alpha": alpha,
        "n": n,
        "transformation_candidates": [],
        "transformation_recommendation": None,
        "transformation_reason_code": None,
    }


def _attach_transformations(
    result: Dict[str, Any], arr: np.ndarray, alpha: float
) -> Dict[str, Any]:
    """保存候選證據；原始分布已通過時不主動推薦轉換。"""

    evaluation = evaluate_transformations(arr, alpha=alpha)
    result["transformation_candidates"] = evaluation["candidates"]
    result["transformation_evidence"] = {
        key: value for key, value in evaluation.items()
        if key not in {"candidates", "recommended"}
    }
    if result.get("accepted"):
        result["transformation_recommendation"] = None
        result["transformation_reason_code"] = "ORIGINAL_DISTRIBUTION_ACCEPTED"
    else:
        result["transformation_recommendation"] = evaluation["recommended"]
        result["transformation_reason_code"] = evaluation["reason_code"]
    return result


def _candidate(
    model: str,
    params: tuple[float, ...],
    statistic: float,
    p_value: float,
    method: str,
    alpha: float,
) -> Dict[str, Any]:
    accepted = bool(isfinite(p_value) and p_value >= alpha)
    return {
        "model": model,
        "params": params,
        "statistic": float(statistic),
        "p_value": float(p_value),
        "method": method,
        "accepted": accepted,
        "reason_code": None if accepted else "GOODNESS_OF_FIT_REJECTED",
    }


def _accept(result: Dict[str, Any], candidate: Dict[str, Any], *, normal_ok: bool) -> Dict[str, Any]:
    result.update({
        "model": candidate["model"],
        "label": MODEL_LABELS[candidate["model"]],
        "params": candidate["params"],
        "accepted": True,
        "normal_ok": normal_ok,
        "unimodal": True,
        "reason_code": None,
        "fit_method": candidate["method"],
    })
    return result


def assess_distribution(
    all_values: List[float],
    field: Optional[str] = None,
    *,
    alpha: float = DEFAULT_ALPHA,
    include_transformations: bool = True,
) -> Dict[str, Any]:
    """評估可接受的分布；沒有候選通過時不回退到常態。"""

    arr = np.asarray(all_values, dtype=float)
    result = _base_result(int(arr.size), alpha)
    if arr.size < MIN_DISTRIBUTION_SAMPLE:
        result["reason_code"] = "INSUFFICIENT_DISTRIBUTION_DATA"
        return result
    if not np.all(np.isfinite(arr)) or float(np.std(arr, ddof=1)) <= 0:
        result["reason_code"] = "DEGENERATE_DISTRIBUTION_DATA"
        return result

    if field in SHAPE_FIELDS:
        if np.any(arr < 0):
            result["reason_code"] = "SHAPE_DISTRIBUTION_NEGATIVE_VALUE"
            return _attach_transformations(result, arr, alpha) if include_transformations else result
        params = tuple(float(value) for value in scipy_stats.foldnorm.fit(arr, floc=0))
        fit = scipy_stats.kstest(arr, scipy_stats.foldnorm.cdf, args=params)
        folded = _candidate(
            "folded_normal", params, float(fit.statistic), float(fit.pvalue),
            "kolmogorov_smirnov", alpha,
        )
        result["candidates"].append(folded)
        if folded["accepted"]:
            _accept(result, folded, normal_ok=False)
        return _attach_transformations(result, arr, alpha) if include_transformations else result

    mean = float(np.mean(arr))
    std = float(np.std(arr, ddof=1))
    ad = scipy_stats.anderson(arr, dist="norm", method="interpolate")
    normal = _candidate(
        "normal",
        (mean, std),
        float(ad.statistic),
        float(ad.pvalue),
        "anderson_darling",
        alpha,
    )
    result["ad_stat"] = float(ad.statistic)
    result["candidates"].append(normal)
    if normal["accepted"]:
        _accept(result, normal, normal_ok=True)
        return _attach_transformations(result, arr, alpha) if include_transformations else result

    if np.all(arr > 0):
        params = tuple(float(value) for value in scipy_stats.lognorm.fit(arr, floc=0))
        fit = scipy_stats.kstest(arr, scipy_stats.lognorm.cdf, args=params)
        lognormal = _candidate(
            "lognormal", params, float(fit.statistic), float(fit.pvalue),
            "kolmogorov_smirnov", alpha,
        )
        result["candidates"].append(lognormal)
        if lognormal["accepted"]:
            _accept(result, lognormal, normal_ok=False)
            return _attach_transformations(result, arr, alpha) if include_transformations else result

    return _attach_transformations(result, arr, alpha) if include_transformations else result


def _frozen(dist: Dict[str, Any]):
    if not dist.get("accepted"):
        return None
    model = dist.get("model")
    params = dist.get("params", ())
    if model == "folded_normal":
        return scipy_stats.foldnorm(params[0], loc=params[1], scale=params[2])
    if model == "lognormal":
        return scipy_stats.lognorm(params[0], loc=params[1], scale=params[2])
    if model == "normal":
        return scipy_stats.norm(params[0], params[1])
    return None


def _is_degenerate(dist: Dict[str, Any]) -> bool:
    frozen = _frozen(dist)
    if frozen is None:
        return True
    params = dist.get("params", ())
    model = dist.get("model")
    scale = params[1] if model == "normal" else params[2]
    return not isfinite(float(scale)) or float(scale) <= 0


def dist_quantiles(dist: Dict[str, Any]):
    """回傳 G 法所需的 0.135%、50%、99.865% 分位數。"""

    if _is_degenerate(dist):
        return None, None, None
    frozen = _frozen(dist)
    return (
        float(frozen.ppf(0.00135)),
        float(frozen.ppf(0.5)),
        float(frozen.ppf(0.99865)),
    )


def tail_ppm(
    dist: Dict[str, Any],
    usl: Optional[float],
    lsl: Optional[float],
) -> Dict[str, Optional[float]]:
    """依已確認分布估算規格外 PPM；未確認時明確回傳 None。"""

    if _is_degenerate(dist):
        return {"upper": None, "lower": None, "total": None}
    frozen = _frozen(dist)
    upper = float(frozen.sf(usl) * 1_000_000) if usl is not None else 0.0
    lower = float(frozen.cdf(lsl) * 1_000_000) if lsl is not None else 0.0
    return {
        "upper": round(upper, 1),
        "lower": round(lower, 1),
        "total": round(upper + lower, 1),
    }
