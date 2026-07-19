"""SPC 2026.2 Box-Cox 與 Johnson 分布轉換候選引擎。"""

from __future__ import annotations

from math import isfinite
from typing import Any, Mapping
import warnings

import numpy as np
from scipy import stats as scipy_stats


TRANSFORMATION_MODELS = ("boxcox", "johnson_su", "johnson_sb", "johnson_sl")
MODEL_LABELS = {
    "boxcox": "Box-Cox",
    "johnson_su": "Johnson SU",
    "johnson_sb": "Johnson SB",
    "johnson_sl": "Johnson SL（對數常態）",
}
MIN_TRANSFORMATION_SAMPLE = 25
DEFAULT_ALPHA = 0.05
MACHINE_EPSILON = float(np.finfo(float).eps)


def _numeric_input(values: Any) -> tuple[np.ndarray, bool]:
    scalar = np.isscalar(values)
    try:
        arr = np.asarray([values] if scalar else values, dtype=float)
    except (TypeError, ValueError) as exc:
        raise ValueError("轉換輸入必須是數值") from exc
    if arr.ndim != 1:
        raise ValueError("轉換輸入必須是一維數值")
    if not np.all(np.isfinite(arr)):
        raise ValueError("轉換輸入必須全部為有限值")
    return arr, scalar


def _finite_number(value: Any, name: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"轉換參數 {name} 無效") from exc
    if not isfinite(number):
        raise ValueError(f"轉換參數 {name} 必須為有限值")
    return number


def _validated_decision(decision: Mapping[str, Any]) -> tuple[str, dict[str, float], float]:
    if not isinstance(decision, Mapping):
        raise ValueError("轉換決定格式無效")
    model = decision.get("model")
    if model not in TRANSFORMATION_MODELS:
        raise ValueError("不受支援的分布轉換模型")
    raw_params = decision.get("params")
    if not isinstance(raw_params, Mapping):
        raise ValueError("轉換參數格式無效")
    required = {
        "boxcox": ("lambda",),
        "johnson_su": ("a", "b", "loc", "scale"),
        "johnson_sb": ("a", "b", "loc", "scale"),
        "johnson_sl": ("shape", "loc", "scale"),
    }[model]
    params = {name: _finite_number(raw_params.get(name), name) for name in required}
    if model in {"johnson_su", "johnson_sb"} and params["b"] <= 0:
        raise ValueError("Johnson 轉換參數 b 必須大於零")
    if model.startswith("johnson_") and params["scale"] <= 0:
        raise ValueError("Johnson 轉換參數 scale 必須大於零")
    if model == "johnson_sl" and params["shape"] <= 0:
        raise ValueError("Johnson SL 轉換參數 shape 必須大於零")
    epsilon = _finite_number(decision.get("epsilon", MACHINE_EPSILON), "epsilon")
    if not 0 < epsilon < 0.5:
        raise ValueError("轉換參數 epsilon 必須介於 0 與 0.5")
    return str(model), params, epsilon


def _frozen(model: str, params: Mapping[str, float]):
    if model == "johnson_su":
        return scipy_stats.johnsonsu(
            params["a"], params["b"], loc=params["loc"], scale=params["scale"]
        )
    if model == "johnson_sb":
        return scipy_stats.johnsonsb(
            params["a"], params["b"], loc=params["loc"], scale=params["scale"]
        )
    if model == "johnson_sl":
        return scipy_stats.lognorm(
            params["shape"], loc=params["loc"], scale=params["scale"]
        )
    return None


def transform_values(values: Any, decision: Mapping[str, Any]):
    """依已保存決定轉換 scalar 或一維 array；不接受 NaN/Inf。"""

    arr, scalar = _numeric_input(values)
    model, params, epsilon = _validated_decision(decision)
    if model == "boxcox":
        if np.any(arr <= 0):
            raise ValueError("Box-Cox 轉換只接受嚴格大於零的數值")
        transformed = scipy_stats.boxcox(arr, lmbda=params["lambda"])
    else:
        frozen = _frozen(model, params)
        probabilities = np.asarray(frozen.cdf(arr), dtype=float)
        probabilities = np.clip(probabilities, epsilon, 1.0 - epsilon)
        transformed = scipy_stats.norm.ppf(probabilities)
    if not np.all(np.isfinite(transformed)):
        raise ValueError("轉換結果包含非有限值")
    return float(transformed[0]) if scalar else np.asarray(transformed, dtype=float)


def inverse_values(values: Any, decision: Mapping[str, Any]):
    """將轉換尺度還原為原始尺度。"""

    arr, scalar = _numeric_input(values)
    model, params, epsilon = _validated_decision(decision)
    if model == "boxcox":
        lambda_value = params["lambda"]
        if abs(lambda_value) < 1e-12:
            restored = np.exp(arr)
        else:
            base = lambda_value * arr + 1.0
            if np.any(base <= 0):
                raise ValueError("Box-Cox 反轉換超出已配適定義域")
            restored = np.power(base, 1.0 / lambda_value)
    else:
        frozen = _frozen(model, params)
        probabilities = np.asarray(scipy_stats.norm.cdf(arr), dtype=float)
        probabilities = np.clip(probabilities, epsilon, 1.0 - epsilon)
        restored = frozen.ppf(probabilities)
    if not np.all(np.isfinite(restored)):
        raise ValueError("反轉換結果包含非有限值")
    return float(restored[0]) if scalar else np.asarray(restored, dtype=float)


def _empty_candidate(model: str, reason_code: str) -> dict[str, Any]:
    return {
        "model": model,
        "label": MODEL_LABELS[model],
        "params": {},
        "epsilon": MACHINE_EPSILON,
        "fit_method": None,
        "ad_statistic": None,
        "ad_p_value": None,
        "tail_quantiles": [],
        "monotonic": False,
        "roundtrip_relative_error": None,
        "accepted": False,
        "reason_code": reason_code,
        "rank": None,
    }


def _controlled_rejection(
    arr: np.ndarray, alpha: float, reason_code: str
) -> dict[str, Any]:
    candidates = [
        _empty_candidate(model, reason_code) for model in TRANSFORMATION_MODELS
    ]
    return {
        "available": False,
        "reason_code": reason_code,
        "n": int(arr.size),
        "minimum_sample_size": MIN_TRANSFORMATION_SAMPLE,
        "alpha": float(alpha),
        "fit_bias_note": "候選未配適；輸入資料未通過受控資格檢查。",
        "candidates": candidates,
        "recommended": None,
    }


def _fit_candidate(model: str, arr: np.ndarray, alpha: float) -> dict[str, Any]:
    if model == "boxcox":
        if np.any(arr <= 0):
            return _empty_candidate(model, "BOXCOX_POSITIVE_VALUES_REQUIRED")
        lambda_value = float(scipy_stats.boxcox_normmax(arr, method="mle"))
        params = {"lambda": lambda_value, "loc": 0.0}
        method = "boxcox_mle"
    elif model == "johnson_su":
        a, b, loc, scale = (float(value) for value in scipy_stats.johnsonsu.fit(arr))
        params = {"a": a, "b": b, "loc": loc, "scale": scale}
        method = "johnson_su_mle"
    elif model == "johnson_sb":
        a, b, loc, scale = (float(value) for value in scipy_stats.johnsonsb.fit(arr))
        params = {"a": a, "b": b, "loc": loc, "scale": scale}
        if not (loc < float(np.min(arr)) and float(np.max(arr)) < loc + scale):
            return _empty_candidate(model, "JOHNSON_SB_SUPPORT_INVALID")
        method = "johnson_sb_mle"
    else:
        if np.any(arr <= 0):
            return _empty_candidate(model, "JOHNSON_SL_POSITIVE_VALUES_REQUIRED")
        shape, loc, scale = (
            float(value) for value in scipy_stats.lognorm.fit(arr, floc=0)
        )
        params = {"shape": shape, "loc": loc, "scale": scale}
        method = "johnson_sl_lognormal_mle"

    candidate: dict[str, Any] = {
        "model": model,
        "label": MODEL_LABELS[model],
        "params": params,
        "epsilon": MACHINE_EPSILON,
        "fit_method": method,
    }
    transformed = np.asarray(transform_values(arr, candidate), dtype=float)
    ad = scipy_stats.anderson(transformed, dist="norm", method="interpolate")
    ad_statistic = float(ad.statistic)
    ad_p_value = float(ad.pvalue)

    if model == "boxcox":
        transformed_mean = float(np.mean(transformed))
        transformed_std = float(np.std(transformed, ddof=1))
        candidate["params"].update({
            "transformed_mean": transformed_mean,
            "transformed_std": transformed_std,
        })
        normal_tail = scipy_stats.norm.ppf(
            [0.00135, 0.5, 0.99865], loc=transformed_mean, scale=transformed_std
        )
        tails = np.asarray(inverse_values(normal_tail, candidate), dtype=float)
    else:
        tails = np.asarray(
            _frozen(model, candidate["params"]).ppf([0.00135, 0.5, 0.99865]),
            dtype=float,
        )

    unique = np.unique(arr)
    monotonic = bool(
        unique.size > 1
        and np.all(np.diff(np.asarray(transform_values(unique, candidate))) > 0)
    )
    restored = np.asarray(
        inverse_values(transform_values(arr, candidate), candidate), dtype=float
    )
    relative_error = float(
        np.max(np.abs(restored - arr) / np.maximum(np.abs(arr), 1.0))
    )
    tails_finite = bool(np.all(np.isfinite(tails)) and np.all(np.diff(tails) > 0))
    accepted = bool(
        isfinite(ad_statistic)
        and isfinite(ad_p_value)
        and ad_p_value >= alpha
        and tails_finite
        and monotonic
        and relative_error <= 1e-9
    )
    if not isfinite(ad_statistic) or not isfinite(ad_p_value) or ad_p_value < alpha:
        reason_code = "TRANSFORMED_NORMALITY_REJECTED"
    elif not tails_finite:
        reason_code = "TRANSFORMATION_TAIL_QUANTILES_INVALID"
    elif not monotonic:
        reason_code = "TRANSFORMATION_NOT_STRICTLY_MONOTONIC"
    elif relative_error > 1e-9:
        reason_code = "TRANSFORMATION_ROUNDTRIP_UNSTABLE"
    else:
        reason_code = None
    candidate.update({
        "ad_statistic": ad_statistic,
        "ad_p_value": ad_p_value,
        "tail_quantiles": [float(value) for value in tails],
        "monotonic": monotonic,
        "roundtrip_relative_error": relative_error,
        "accepted": accepted,
        "reason_code": reason_code,
        "rank": None,
    })
    return candidate


def evaluate_transformations(values: Any, alpha: float = DEFAULT_ALPHA) -> dict[str, Any]:
    """評估四種候選；配適與 AD 使用同筆資料，結果屬探索性證據。"""

    try:
        arr = np.asarray([values] if np.isscalar(values) else values, dtype=float)
    except (TypeError, ValueError) as exc:
        raise ValueError("轉換輸入必須是數值") from exc
    if arr.ndim != 1:
        raise ValueError("轉換輸入必須是一維數值")
    if not 0 < float(alpha) < 1:
        raise ValueError("alpha 必須介於 0 與 1")
    if not np.all(np.isfinite(arr)):
        return _controlled_rejection(arr, float(alpha), "NONFINITE_DISTRIBUTION_DATA")
    if arr.size < MIN_TRANSFORMATION_SAMPLE:
        return _controlled_rejection(
            arr, float(alpha), "TRANSFORMATION_SAMPLE_INSUFFICIENT"
        )
    if float(np.std(arr, ddof=1)) <= 0:
        return _controlled_rejection(
            arr, float(alpha), "DEGENERATE_DISTRIBUTION_DATA"
        )

    candidates = []
    for model in TRANSFORMATION_MODELS:
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", RuntimeWarning)
                candidate = _fit_candidate(model, arr, float(alpha))
        except (ValueError, RuntimeError, FloatingPointError, OverflowError) as exc:
            candidate = _empty_candidate(model, "TRANSFORMATION_FIT_FAILED")
            candidate["fit_error"] = str(exc)
        candidates.append(candidate)

    accepted = sorted(
        (candidate for candidate in candidates if candidate["accepted"]),
        key=lambda candidate: (
            -float(candidate["ad_p_value"]),
            float(candidate["ad_statistic"]),
            str(candidate["model"]),
        ),
    )
    for rank, candidate in enumerate(accepted, start=1):
        candidate["rank"] = rank
    rejected = sorted(
        (candidate for candidate in candidates if not candidate["accepted"]),
        key=lambda candidate: TRANSFORMATION_MODELS.index(candidate["model"]),
    )
    ordered = accepted + rejected
    return {
        "available": True,
        "reason_code": None if accepted else "TRANSFORMATION_UNCONFIRMED",
        "n": int(arr.size),
        "minimum_sample_size": MIN_TRANSFORMATION_SAMPLE,
        "alpha": float(alpha),
        "fit_bias_note": "候選配適與常態性檢定使用同筆資料，p 值可能偏樂觀，必須人工確認。",
        "candidates": ordered,
        "recommended": dict(accepted[0]) if accepted else None,
    }
