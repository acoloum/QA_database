"""偏倚與線性統計引擎。

兩者都是純函式。線性結論不得只看 R²：必須同時檢查斜率顯著性、
截距顯著性與各參考量程平均偏倚的信賴區間是否穿越 0。
"""

import math

from scipy import stats

from .msa_contracts import MsaAnalysisOutput, MsaMethodContext
from .msa_errors import MsaMethodNotApplicable


MIN_REFERENCE_LEVELS = 5
# 參考量程跨度小於此比例時，回歸結論外推風險高，必須警告
MIN_RANGE_COVERAGE_RATIO = 0.05


def analyze_bias(payload, context: MsaMethodContext):
    """單一參考件重複量測的偏倚與 t 檢定。"""
    data = payload or {}
    reference_value = data.get("reference_value")
    if reference_value is None:
        raise MsaMethodNotApplicable(
            "reference_value_missing",
            "偏倚研究必須有可追溯的參考值",
            details={},
        )
    reference_value = _finite(reference_value, "reference_value")
    readings = [
        _finite(value, "reading") for value in (data.get("readings") or [])
    ]
    if len(readings) < 2:
        raise MsaMethodNotApplicable(
            "insufficient_readings",
            "偏倚研究至少需要兩次量測才能估計重複性",
            details={"readings": len(readings)},
        )

    count = len(readings)
    mean_value = sum(readings) / count
    bias = mean_value - reference_value
    variance = sum((value - mean_value) ** 2 for value in readings) / (
        count - 1
    )
    repeatability_sd = math.sqrt(variance)
    standard_error = repeatability_sd / math.sqrt(count)

    warnings = []
    t_value = p_value = None
    confidence_interval = None
    estimability_note = None
    if standard_error > 0:
        t_value = bias / standard_error
        p_value = float(2 * stats.t.sf(abs(t_value), df=count - 1))
        t_critical = float(stats.t.ppf(1 - context.alpha / 2, df=count - 1))
        confidence_interval = [
            bias - t_critical * standard_error,
            bias + t_critical * standard_error,
        ]
        significant = not (
            confidence_interval[0] <= 0 <= confidence_interval[1]
        )
    elif bias == 0:
        significant = False
        estimability_note = (
            "重複性標準差為 0 且偏倚為 0，無法進行 t 檢定但未觀察到偏倚"
        )
        warnings.append({
            "code": "MSA_BIAS_NOT_ESTIMABLE",
            "message": estimability_note,
        })
    else:
        significant = True
        estimability_note = (
            "重複性標準差為 0 但偏倚不為 0，判定為明顯偏倚且無法估計檢定統計量"
        )
        warnings.append({
            "code": "MSA_BIAS_NOT_ESTIMABLE",
            "message": estimability_note,
        })

    percent_of_tolerance = None
    if context.tolerance and context.tolerance > 0:
        percent_of_tolerance = 100.0 * abs(bias) / context.tolerance
    else:
        warnings.append({
            "code": "MSA_TOLERANCE_UNAVAILABLE",
            "message": "研究沒有可用公差，無法計算偏倚佔公差比例",
        })

    statistics = {
        "method": "bias",
        "n": count,
        "reference_value": reference_value,
        "mean": mean_value,
        "bias": bias,
        "repeatability_sd": repeatability_sd,
        "standard_error": standard_error,
        "t_value": t_value,
        "p_value": p_value,
        "confidence_interval": confidence_interval,
        "confidence_interval_excludes_zero": (
            None if confidence_interval is None else significant
        ),
        "significant": significant,
        "estimability_note": estimability_note,
        "percent_bias_of_tolerance": percent_of_tolerance,
        "alpha": context.alpha,
    }
    applicability = {
        "method": "bias",
        "applicable": True,
        "readings": count,
        "tolerance_available": context.tolerance is not None,
        "t_test_available": t_value is not None,
    }
    chart_data = {
        "readings": readings,
        "reference_value": reference_value,
        "mean": mean_value,
        "confidence_interval": confidence_interval,
        "zero_line": 0.0,
    }
    return MsaAnalysisOutput(
        applicability=applicability,
        statistics=statistics,
        chart_data=chart_data,
        warnings=tuple(warnings),
    )


def analyze_linearity(groups, context: MsaMethodContext):
    """跨參考量程的偏倚回歸與各量程信賴區間。"""
    levels = list(groups or [])
    if len(levels) < MIN_REFERENCE_LEVELS:
        raise MsaMethodNotApplicable(
            "insufficient_reference_levels",
            f"線性研究至少需要 {MIN_REFERENCE_LEVELS} 個參考量程",
            details={"levels": len(levels)},
        )

    xs, ys = [], []
    level_stats = []
    for index, group in enumerate(levels):
        reference_value = group.get("reference_value")
        if reference_value is None:
            raise MsaMethodNotApplicable(
                "reference_value_missing",
                "每個參考量程都必須有參考值",
                details={"index": index},
            )
        reference_value = _finite(reference_value, "reference_value")
        readings = [
            _finite(value, "reading") for value in (group.get("readings") or [])
        ]
        if len(readings) < 2:
            raise MsaMethodNotApplicable(
                "insufficient_trials",
                "每個參考量程至少需要兩次量測才能估計該量程的變異",
                details={"index": index, "readings": len(readings)},
            )
        biases = [value - reference_value for value in readings]
        xs.extend([reference_value] * len(biases))
        ys.extend(biases)

        count = len(biases)
        mean_bias = sum(biases) / count
        sd = math.sqrt(
            sum((value - mean_bias) ** 2 for value in biases) / (count - 1)
        )
        standard_error = sd / math.sqrt(count)
        t_critical = float(stats.t.ppf(1 - context.alpha / 2, df=count - 1))
        lower = mean_bias - t_critical * standard_error
        upper = mean_bias + t_critical * standard_error
        level_stats.append({
            "reference_value": reference_value,
            "n": count,
            "mean_bias": mean_bias,
            "sd": sd,
            "confidence_interval": [lower, upper],
            "crosses_zero": lower <= 0 <= upper,
        })

    x_mean = sum(xs) / len(xs)
    sxx = sum((x - x_mean) ** 2 for x in xs)
    if sxx <= 0:
        raise MsaMethodNotApplicable(
            "singular_design",
            "所有參考值相同，無法估計線性回歸斜率",
            details={"sxx": sxx},
        )

    result = stats.linregress(xs, ys)
    slope = float(result.slope)
    intercept = float(result.intercept)
    slope_se = float(result.stderr)
    intercept_se = float(result.intercept_stderr)
    r_squared = float(result.rvalue) ** 2
    df_residual = len(xs) - 2
    fitted = [intercept + slope * x for x in xs]
    residuals = [y - f for y, f in zip(ys, fitted)]
    residual_mse = sum(value ** 2 for value in residuals) / df_residual
    t_critical = float(stats.t.ppf(1 - context.alpha / 2, df=df_residual))

    slope_t = slope / slope_se if slope_se > 0 else None
    slope_p = (
        float(2 * stats.t.sf(abs(slope_t), df=df_residual))
        if slope_t is not None else None
    )
    intercept_t = intercept / intercept_se if intercept_se > 0 else None
    intercept_p = (
        float(2 * stats.t.sf(abs(intercept_t), df=df_residual))
        if intercept_t is not None else None
    )

    warnings = []
    span = max(xs) - min(xs)
    coverage_base = max(abs(max(xs)), abs(min(xs)), 1e-12)
    if span / coverage_base < MIN_RANGE_COVERAGE_RATIO:
        warnings.append({
            "code": "MSA_LINEARITY_RANGE_COVERAGE_LOW",
            "message": (
                "參考量程跨度過窄，回歸結論不可外推到實際使用量程"
            ),
        })

    slope_significant = bool(slope_p is not None and slope_p < context.alpha)
    intercept_significant = bool(
        intercept_p is not None and intercept_p < context.alpha
    )
    levels_excluding_zero = sum(
        1 for level in level_stats if not level["crosses_zero"]
    )
    # 結論刻意不納入 R²：高 R² 只代表偏倚隨量程規律變化，不代表線性合格
    linearity_evidence = {
        "decision_basis": [
            "slope_significant",
            "intercept_significant",
            "levels_excluding_zero",
        ],
        "slope_significant": slope_significant,
        "intercept_significant": intercept_significant,
        "levels_excluding_zero": levels_excluding_zero,
        "level_count": len(level_stats),
        "acceptable": not (
            slope_significant
            or intercept_significant
            or levels_excluding_zero > 0
        ),
    }

    percent_of_tolerance = None
    if context.tolerance and context.tolerance > 0:
        percent_of_tolerance = (
            100.0 * abs(slope) * context.study_variation_multiplier
            / context.tolerance
        )

    statistics = {
        "method": "linearity",
        "regression": {
            "slope": slope,
            "intercept": intercept,
            "slope_std_error": slope_se,
            "intercept_std_error": intercept_se,
            "slope_t_value": slope_t,
            "slope_p_value": slope_p,
            "intercept_t_value": intercept_t,
            "intercept_p_value": intercept_p,
            "slope_confidence_interval": [
                slope - t_critical * slope_se,
                slope + t_critical * slope_se,
            ],
            "intercept_confidence_interval": [
                intercept - t_critical * intercept_se,
                intercept + t_critical * intercept_se,
            ],
            "r_squared": r_squared,
            "residual_df": df_residual,
            "residual_mse": residual_mse,
        },
        "reference_levels": level_stats,
        "linearity_evidence": linearity_evidence,
        "linearity_percent_of_tolerance": percent_of_tolerance,
        "alpha": context.alpha,
    }
    applicability = {
        "method": "linearity",
        "applicable": True,
        "reference_levels": len(level_stats),
        "observations": len(xs),
        "tolerance_available": context.tolerance is not None,
    }
    chart_data = _linearity_chart(
        xs, ys, fitted, residuals, slope, intercept, x_mean, sxx,
        residual_mse, t_critical,
    )
    return MsaAnalysisOutput(
        applicability=applicability,
        statistics=statistics,
        chart_data=chart_data,
        warnings=tuple(warnings),
    )


def _linearity_chart(
    xs, ys, fitted, residuals, slope, intercept, x_mean, sxx,
    residual_mse, t_critical,
):
    """輸出擬合線、平均信賴帶、個別預測帶與殘差。"""
    grid = sorted(set(xs))
    confidence_band = []
    prediction_band = []
    for x in grid:
        predicted = intercept + slope * x
        leverage = 1.0 / len(xs) + ((x - x_mean) ** 2) / sxx
        mean_se = math.sqrt(residual_mse * leverage)
        individual_se = math.sqrt(residual_mse * (1.0 + leverage))
        confidence_band.append({
            "x": x,
            "lower": predicted - t_critical * mean_se,
            "upper": predicted + t_critical * mean_se,
        })
        prediction_band.append({
            "x": x,
            "lower": predicted - t_critical * individual_se,
            "upper": predicted + t_critical * individual_se,
        })

    return {
        "points": [{"x": x, "y": y} for x, y in zip(xs, ys)],
        "fitted_line": [
            {"x": x, "y": intercept + slope * x} for x in grid
        ],
        "confidence_band": confidence_band,
        "prediction_band": prediction_band,
        "residuals": [
            {"fitted": f, "residual": r} for f, r in zip(fitted, residuals)
        ],
        "zero_line": 0.0,
    }


def _finite(value, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise MsaMethodNotApplicable(
            "non_numeric_reading",
            f"{field} 必須是數值",
            details={"field": field},
        )
    if not math.isfinite(value):
        raise MsaMethodNotApplicable(
            "non_finite_reading",
            f"{field} 不得為 NaN 或 Infinity",
            details={"field": field},
        )
    return float(value)
