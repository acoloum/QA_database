"""計量型 GRR 統計引擎：極差法與平均值－極差法。

引擎是純函式：不查資料庫、不取用目前時間、不改寫輸入。任何無法
以本方法正確計算的情形一律拋出 MSA_METHOD_NOT_APPLICABLE，
不產生看起來合理但沒有依據的數字。
"""

from collections import defaultdict
import math

from scipy import stats

from .msa_contracts import MsaAnalysisOutput, MsaMethodContext
from .msa_control_chart_constants import A2, D3, D4
from .msa_errors import MsaMethodNotApplicable
from .msa_numeric import MsaNumericError, require_finite_tree


# AIAG MSA 第四版的 d2 常數（子組大小 2..10）；超出範圍不得外插。
D2 = {
    2: 1.128, 3: 1.693, 4: 2.059, 5: 2.326,
    6: 2.534, 7: 2.704, 8: 2.847, 9: 2.970, 10: 3.078,
}

NDC_CONSTANT = 1.41


def analyze_xbar_r(observations, context: MsaMethodContext):
    """平均值－極差法：拆解 EV、AV、GRR、PV 與 ndc。"""
    matrix, parts, appraisers, trials = _balanced_matrix(observations)
    if trials < 2:
        raise MsaMethodNotApplicable(
            "insufficient_trials",
            "平均值－極差法至少需要兩次試驗才能估計重複性",
            details={"trials": trials},
        )
    _require_d2(trials, "trials")
    _require_d2(len(parts), "parts")

    # 1. 重複性（EV）：各 appraiser×part cell 極差的平均
    cell_ranges = [
        max(values) - min(values) for values in matrix.values()
    ]
    r_bar = sum(cell_ranges) / len(cell_ranges)
    ev_sigma = r_bar / D2[trials]

    # 2. 再現性（AV）：評價人平均的極差，扣掉其中已含的重複性
    appraiser_means = {
        appraiser: _mean([
            value
            for (a, _part), values in matrix.items() if a == appraiser
            for value in values
        ])
        for appraiser in appraisers
    }
    reproducibility_available = len(appraisers) >= 2
    av_sigma = None
    av_raw_variance = None
    av_adjustment_reason = None
    if reproducibility_available:
        _require_d2(len(appraisers), "appraisers")
        appraiser_range = (
            max(appraiser_means.values()) - min(appraiser_means.values())
        )
        av_raw_variance = (
            (appraiser_range / D2[len(appraisers)]) ** 2
            - (ev_sigma ** 2) / (len(parts) * trials)
        )
        if av_raw_variance < 0:
            av_adjustment_reason = "再現性變異數計算為負，依 MSA 第四版取 0"
        av_sigma = math.sqrt(max(av_raw_variance, 0.0))

    # 3. GRR、零件變差與總變差
    grr_sigma = math.sqrt(ev_sigma ** 2 + (av_sigma or 0.0) ** 2)
    part_means = {
        part: _mean([
            value
            for (_a, p), values in matrix.items() if p == part
            for value in values
        ])
        for part in parts
    }
    part_mean_range = max(part_means.values()) - min(part_means.values())
    pv_sigma = part_mean_range / D2[len(parts)]
    tv_sigma = math.sqrt(grr_sigma ** 2 + pv_sigma ** 2)

    warnings = []
    ndc = None
    if grr_sigma > 0:
        ndc = math.floor(NDC_CONSTANT * pv_sigma / grr_sigma)
    else:
        warnings.append({
            "code": "MSA_GRR_ZERO_VARIATION",
            "message": "量測系統變差為 0，可能是解析度不足或資料異常，無法計算 ndc",
        })
    if not reproducibility_available:
        warnings.append({
            "code": "MSA_REPRODUCIBILITY_UNAVAILABLE",
            "message": "只有一位評價人，無法估計再現性；GRR 僅反映重複性",
        })
    if av_adjustment_reason:
        warnings.append({
            "code": "MSA_AV_VARIANCE_CLAMPED",
            "message": av_adjustment_reason,
        })

    sigmas = {
        "ev": ev_sigma,
        "av": av_sigma,
        "grr": grr_sigma,
        "pv": pv_sigma,
        "tv": tv_sigma,
    }
    percent_tolerance = _percent_tolerance(sigmas, context, warnings)
    statistics = {
        "method": "xbar_r",
        "r_bar": r_bar,
        "ev": ev_sigma,
        "av": av_sigma,
        "av_raw_variance": av_raw_variance,
        "av_adjusted_variance": (
            None if av_sigma is None else av_sigma ** 2
        ),
        "av_adjustment_reason": av_adjustment_reason,
        "grr": grr_sigma,
        "pv": pv_sigma,
        "tv": tv_sigma,
        "ndc": ndc,
        "study_variation_multiplier": context.study_variation_multiplier,
        "study_variation": {
            key: (
                None if value is None
                else context.study_variation_multiplier * value
            )
            for key, value in sigmas.items()
        },
        "percent_study_variation": _percent_study_variation(sigmas, tv_sigma),
        "percent_tolerance": percent_tolerance,
        "percent_process": _percent_process(sigmas, context),
        "d2": {
            "trials": D2[trials],
            "parts": D2[len(parts)],
            "appraisers": (
                D2[len(appraisers)] if reproducibility_available else None
            ),
        },
    }
    applicability = {
        "method": "xbar_r",
        "applicable": True,
        "balanced": True,
        "parts": len(parts),
        "appraisers": len(appraisers),
        "trials": trials,
        "reproducibility_available": reproducibility_available,
        "tolerance_available": context.tolerance is not None,
        "process_sigma_available": context.process_sigma is not None,
    }
    chart_data = _build_chart_data(
        matrix, parts, appraisers, trials, part_means, appraiser_means, r_bar,
    )
    return MsaAnalysisOutput(
        applicability=applicability,
        statistics=statistics,
        chart_data=chart_data,
        warnings=tuple(warnings),
    )


def analyze_range(observations, context: MsaMethodContext):
    """極差法：只給整體 GRR，不拆解 EV/AV/PV。"""
    matrix, parts, appraisers, trials = _balanced_matrix(observations)
    if trials < 2:
        raise MsaMethodNotApplicable(
            "insufficient_trials",
            "極差法至少需要兩次試驗才能取得極差",
            details={"trials": trials},
        )
    _require_d2(trials, "trials")

    cell_ranges = [max(values) - min(values) for values in matrix.values()]
    sample_size = len(cell_ranges)
    r_bar = sum(cell_ranges) / sample_size
    grr_sigma = r_bar / D2[trials]

    warnings = []
    sigmas = {"grr": grr_sigma}
    statistics = {
        "method": "range",
        "detail_components_available": False,
        "sample_size": sample_size,
        "d2": D2[trials],
        "r_bar": r_bar,
        "grr": grr_sigma,
        "study_variation_multiplier": context.study_variation_multiplier,
        "study_variation": {
            "grr": context.study_variation_multiplier * grr_sigma
        },
        "percent_tolerance": _percent_tolerance(sigmas, context, warnings),
        "percent_process": _percent_process(sigmas, context),
    }
    applicability = {
        "method": "range",
        "applicable": True,
        "parts": len(parts),
        "appraisers": len(appraisers),
        "trials": trials,
        "tolerance_available": context.tolerance is not None,
        "limitations": [
            "極差法只提供整體量測系統變差，不拆解重複性、再現性與零件變差",
        ],
    }
    return MsaAnalysisOutput(
        applicability=applicability,
        statistics=statistics,
        chart_data={"cell_ranges": cell_ranges},
        warnings=tuple(warnings),
    )


def analyze_crossed_anova(observations, context: MsaMethodContext):
    """交叉型 ANOVA：保存完整與縮減模型證據，依交互作用顯著性選用。"""
    matrix, parts, appraisers, trials = _balanced_matrix(observations)
    part_count, appraiser_count = len(parts), len(appraisers)
    if appraiser_count < 2:
        raise MsaMethodNotApplicable(
            "insufficient_appraisers",
            "交叉型 ANOVA 需要至少兩位評價人",
            details={"appraisers": appraiser_count},
        )
    if part_count < 2:
        raise MsaMethodNotApplicable(
            "insufficient_parts",
            "交叉型 ANOVA 需要至少兩個零件",
            details={"parts": part_count},
        )
    df_repeatability = part_count * appraiser_count * (trials - 1)
    if df_repeatability <= 0:
        raise MsaMethodNotApplicable(
            "no_error_degrees_of_freedom",
            "每個組合只有一次試驗，誤差自由度為 0，無法估計重複性",
            details={"trials": trials},
        )

    values = [value for cell in matrix.values() for value in cell]
    grand_mean = _mean(values)
    cell_mean = {key: _mean(cell) for key, cell in matrix.items()}
    part_mean = {
        part: _mean([
            value for (_a, p), cell in matrix.items() if p == part
            for value in cell
        ])
        for part in parts
    }
    appraiser_mean = {
        appraiser: _mean([
            value for (a, _p), cell in matrix.items() if a == appraiser
            for value in cell
        ])
        for appraiser in appraisers
    }

    ss_part = appraiser_count * trials * sum(
        (part_mean[part] - grand_mean) ** 2 for part in parts
    )
    ss_appraiser = part_count * trials * sum(
        (appraiser_mean[appraiser] - grand_mean) ** 2
        for appraiser in appraisers
    )
    ss_interaction = trials * sum(
        (
            cell_mean[(appraiser, part)] - part_mean[part]
            - appraiser_mean[appraiser] + grand_mean
        ) ** 2
        for part in parts for appraiser in appraisers
    )
    ss_repeatability = sum(
        (value - cell_mean[key]) ** 2
        for key, cell in matrix.items() for value in cell
    )

    df_part = part_count - 1
    df_appraiser = appraiser_count - 1
    df_interaction = df_part * df_appraiser
    ms_part = ss_part / df_part
    ms_appraiser = ss_appraiser / df_appraiser
    ms_interaction = ss_interaction / df_interaction
    ms_repeatability = ss_repeatability / df_repeatability

    if ms_repeatability <= 0 or ms_interaction <= 0:
        raise MsaMethodNotApplicable(
            "degenerate_model",
            "重複性或交互作用均方為 0，F 值無定義，無法產生正式結果",
            details={
                "ms_repeatability": ms_repeatability,
                "ms_interaction": ms_interaction,
            },
        )

    f_part = ms_part / ms_interaction
    f_appraiser = ms_appraiser / ms_interaction
    f_interaction = ms_interaction / ms_repeatability
    p_part = float(stats.f.sf(f_part, df_part, df_interaction))
    p_appraiser = float(stats.f.sf(f_appraiser, df_appraiser, df_interaction))
    p_interaction = float(
        stats.f.sf(f_interaction, df_interaction, df_repeatability)
    )

    full_raw = {
        "repeatability": ms_repeatability,
        "part_appraiser": (ms_interaction - ms_repeatability) / trials,
        "appraiser": (
            (ms_appraiser - ms_interaction) / (part_count * trials)
        ),
        "part": (ms_part - ms_interaction) / (appraiser_count * trials),
    }
    full_adjusted = {
        key: max(value, 0.0) for key, value in full_raw.items()
    }
    full_model = {
        "table": [
            {
                "source": "part", "ss": ss_part, "df": df_part,
                "ms": ms_part, "f": f_part, "p": p_part,
            },
            {
                "source": "appraiser", "ss": ss_appraiser,
                "df": df_appraiser, "ms": ms_appraiser,
                "f": f_appraiser, "p": p_appraiser,
            },
            {
                "source": "part_appraiser", "ss": ss_interaction,
                "df": df_interaction, "ms": ms_interaction,
                "f": f_interaction, "p": p_interaction,
            },
            {
                "source": "repeatability", "ss": ss_repeatability,
                "df": df_repeatability, "ms": ms_repeatability,
                "f": None, "p": None,
            },
        ],
        "raw_variance_components": full_raw,
        "adjusted_variance_components": full_adjusted,
    }

    # 縮減模型：交互作用併入誤差後重新估計零件與評價人分量
    ss_reduced_error = ss_interaction + ss_repeatability
    df_reduced_error = df_interaction + df_repeatability
    ms_reduced_error = ss_reduced_error / df_reduced_error
    reduced_raw = {
        "repeatability": ms_reduced_error,
        "appraiser": (
            (ms_appraiser - ms_reduced_error) / (part_count * trials)
        ),
        "part": (ms_part - ms_reduced_error) / (appraiser_count * trials),
    }
    reduced_adjusted = {
        key: max(value, 0.0) for key, value in reduced_raw.items()
    }
    reduced_model = {
        "error_ss": ss_reduced_error,
        "error_df": df_reduced_error,
        "error_ms": ms_reduced_error,
        "raw_variance_components": reduced_raw,
        "adjusted_variance_components": reduced_adjusted,
    }

    warnings = []
    selected = "full" if p_interaction < context.alpha else "reduced"
    if selected == "reduced":
        warnings.append({
            "code": "MSA_ANOVA_INTERACTION_POOLED",
            "message": (
                "交互作用未達顯著水準，依受控規則併入誤差；"
                "完整模型證據仍完整保存"
            ),
        })
        grr_variance = (
            reduced_adjusted["repeatability"] + reduced_adjusted["appraiser"]
        )
        pv_variance = reduced_adjusted["part"]
    else:
        grr_variance = (
            full_adjusted["repeatability"] + full_adjusted["appraiser"]
            + full_adjusted["part_appraiser"]
        )
        pv_variance = full_adjusted["part"]

    for key, value in full_raw.items():
        if value < 0:
            warnings.append({
                "code": "MSA_ANOVA_COMPONENT_CLAMPED",
                "message": f"變異數分量 {key} 計算為負，依受控規則取 0",
            })

    grr_sigma = math.sqrt(grr_variance)
    pv_sigma = math.sqrt(pv_variance)
    tv_sigma = math.sqrt(grr_variance + pv_variance)
    ndc = None
    if grr_sigma > 0:
        ndc = math.floor(NDC_CONSTANT * pv_sigma / grr_sigma)
    else:
        warnings.append({
            "code": "MSA_GRR_ZERO_VARIATION",
            "message": "量測系統變差為 0，無法計算 ndc",
        })

    sigmas = {"grr": grr_sigma, "pv": pv_sigma, "tv": tv_sigma}
    statistics = {
        "method": "crossed_anova",
        "anova": {
            "selected_model": selected,
            "interaction_policy": "reduce_when_p_ge_alpha",
            "alpha": context.alpha,
            "p_interaction": p_interaction,
            "full_model": full_model,
            "reduced_model": reduced_model,
        },
        "grr": grr_sigma,
        "pv": pv_sigma,
        "tv": tv_sigma,
        "ndc": ndc,
        "study_variation_multiplier": context.study_variation_multiplier,
        "study_variation": {
            key: context.study_variation_multiplier * value
            for key, value in sigmas.items()
        },
        "percent_study_variation": _percent_study_variation(sigmas, tv_sigma),
        "percent_tolerance": _percent_tolerance(sigmas, context, warnings),
        "percent_process": _percent_process(sigmas, context),
    }
    applicability = {
        "method": "crossed_anova",
        "applicable": True,
        "balanced": True,
        "parts": part_count,
        "appraisers": appraiser_count,
        "trials": trials,
        "error_degrees_of_freedom": df_repeatability,
        "tolerance_available": context.tolerance is not None,
    }
    chart_data = _build_chart_data(
        matrix, parts, appraisers, trials, part_mean, appraiser_mean,
        _mean([max(cell) - min(cell) for cell in matrix.values()]),
    )

    try:
        require_finite_tree(statistics)
    except MsaNumericError as error:
        raise MsaMethodNotApplicable(
            "non_finite_statistics",
            "ANOVA 統計結果出現非有限值，拒絕產生正式結果",
            details={"path": error.path},
        ) from error

    return MsaAnalysisOutput(
        applicability=applicability,
        statistics=statistics,
        chart_data=chart_data,
        warnings=tuple(warnings),
    )


# ----------------------------------------------------------------------
# 共用
# ----------------------------------------------------------------------


def _balanced_matrix(observations):
    """整理成 (appraiser, part) → 讀值序列，並確認設計平衡且無缺格。"""
    if not observations:
        raise MsaMethodNotApplicable(
            "no_observations", "沒有可分析的觀測資料", details={},
        )

    matrix = defaultdict(list)
    parts = []
    appraisers = []
    for row in observations:
        part = row.get("part")
        appraiser = row.get("appraiser")
        value = row.get("value")
        if part is None or appraiser is None:
            raise MsaMethodNotApplicable(
                "incomplete_observation",
                "觀測缺少零件或評價人識別",
                details={"observation": _describe(row)},
            )
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            raise MsaMethodNotApplicable(
                "non_numeric_reading",
                "計量型分析只接受數值讀值",
                details={"observation": _describe(row)},
            )
        if not math.isfinite(value):
            raise MsaMethodNotApplicable(
                "non_finite_reading",
                "讀值不得為 NaN 或 Infinity",
                details={"observation": _describe(row)},
            )
        if part not in parts:
            parts.append(part)
        if appraiser not in appraisers:
            appraisers.append(appraiser)
        matrix[(appraiser, part)].append(float(value))

    parts.sort()
    appraisers.sort()

    expected_cells = len(parts) * len(appraisers)
    if len(matrix) != expected_cells:
        raise MsaMethodNotApplicable(
            "unbalanced_design",
            "設計不完整：有評價人與零件的組合沒有任何讀值",
            details={
                "expected_cells": expected_cells,
                "actual_cells": len(matrix),
            },
        )

    sizes = {len(values) for values in matrix.values()}
    if len(sizes) != 1:
        raise MsaMethodNotApplicable(
            "unbalanced_design",
            "設計不平衡：各組合的試驗次數不一致，不可套用平衡公式",
            details={"trial_counts": sorted(sizes)},
        )

    return dict(matrix), parts, appraisers, sizes.pop()


def _require_d2(size: int, dimension: str) -> None:
    if size not in D2:
        raise MsaMethodNotApplicable(
            "d2_out_of_range",
            "設計規模超出受控 d2 常數表，不得外插",
            details={
                "dimension": dimension,
                "size": size,
                "supported": sorted(D2),
            },
        )


def _mean(values):
    return sum(values) / len(values)


def _percent_study_variation(sigmas: dict, tv_sigma: float):
    if tv_sigma <= 0:
        return None
    return {
        key: (None if value is None else 100.0 * value / tv_sigma)
        for key, value in sigmas.items()
    }


def _percent_tolerance(sigmas: dict, context: MsaMethodContext, warnings):
    if not context.tolerance or context.tolerance <= 0:
        warnings.append({
            "code": "MSA_TOLERANCE_UNAVAILABLE",
            "message": "研究沒有可用公差，無法計算 %Tolerance",
        })
        return None
    return {
        key: (
            None if value is None
            else 100.0 * context.study_variation_multiplier * value
            / context.tolerance
        )
        for key, value in sigmas.items()
    }


def _percent_process(sigmas: dict, context: MsaMethodContext):
    if not context.process_sigma or context.process_sigma <= 0:
        return None
    return {
        key: (
            None if value is None
            else 100.0 * value / context.process_sigma
        )
        for key, value in sigmas.items()
    }


def _build_chart_data(
    matrix, parts, appraisers, trials, part_means, appraiser_means, r_bar,
):
    """輸出 Xbar/R 管制圖所需的中心線、管制界限與超限點。"""
    subgroup_means = {}
    subgroup_ranges = {}
    for (appraiser, part), values in matrix.items():
        key = f"{appraiser}|{part}"
        subgroup_means[key] = _mean(values)
        subgroup_ranges[key] = max(values) - min(values)

    xbar_center = _mean(list(subgroup_means.values()))
    xbar_ucl = xbar_center + A2[trials] * r_bar
    xbar_lcl = xbar_center - A2[trials] * r_bar
    range_ucl = D4[trials] * r_bar
    range_lcl = D3[trials] * r_bar

    return {
        "part_means": part_means,
        "appraiser_means": appraiser_means,
        "xbar_chart": {
            "center": xbar_center,
            "ucl": xbar_ucl,
            "lcl": xbar_lcl,
            "points": subgroup_means,
            # Xbar 圖刻意希望零件差異超出界限，超限點代表可鑑別零件
            "out_of_control_points": sorted(
                key for key, value in subgroup_means.items()
                if value > xbar_ucl or value < xbar_lcl
            ),
        },
        "range_chart": {
            "center": r_bar,
            "ucl": range_ucl,
            "lcl": range_lcl,
            "points": subgroup_ranges,
            "out_of_control_points": sorted(
                key for key, value in subgroup_ranges.items()
                if value > range_ucl or value < range_lcl
            ),
        },
    }


def _describe(row):
    return {
        key: row.get(key) for key in ("part", "appraiser", "trial")
    }
