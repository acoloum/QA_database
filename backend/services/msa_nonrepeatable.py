"""不可重複／破壞性量測系統研究。

破壞性試驗無法對同一件重複量測，因此所有結論都建立在明確的物理
假設之上。假設未經確認時直接判定不適用，絕不退回交叉型 GRR 充數。
"""

from collections import defaultdict
import math

from .msa_contracts import MsaAnalysisOutput, MsaMethodContext
from .msa_errors import MsaMethodNotApplicable
from .msa_numeric import require_finite_reading as _finite


# 這些假設一旦不成立，配對差就不只反映量測系統，結論即無效。
REQUIRED_CONFIRMATIONS = (
    "sample_homogeneity",
    "shelf_life",
    "process_stability",
    "pairing_assumption",
)

MIN_PAIRS = 10
MIN_LOTS = 5
MIN_STATIONS = 2


def analyze_nonrepeatable(observations, context: MsaMethodContext):
    """依設計型態分派；不提供交叉型 GRR 作為退路。"""
    criteria = context.criteria or {}
    _assert_confirmations(criteria.get("confirmations"))

    design_type = criteria.get("design_type")
    analyzer = ANALYZERS.get(design_type)
    if analyzer is None:
        raise MsaMethodNotApplicable(
            "unsupported_design_type",
            "不可重複研究必須指定受控的設計型態",
            details={
                "design_type": design_type,
                "supported": sorted(ANALYZERS),
            },
        )
    return analyzer(observations, context)


def _assert_confirmations(confirmations) -> None:
    values = confirmations or {}
    missing = [
        name for name in REQUIRED_CONFIRMATIONS if not values.get(name)
    ]
    if missing:
        raise MsaMethodNotApplicable(
            "physical_assumptions_unconfirmed",
            "不可重複研究的物理假設尚未全部確認，結論不具效力",
            details={
                "missing_confirmations": missing,
                "required": list(REQUIRED_CONFIRMATIONS),
            },
        )


# ----------------------------------------------------------------------
# 配對型設計
# ----------------------------------------------------------------------


def _paired_analysis(observations, context, *, design_type, unit_label):
    """分割樣本與連續配對共用的配對差分析。"""
    pairs = defaultdict(dict)
    for index, row in enumerate(observations or []):
        unit = row.get("unit")
        position = row.get("position")
        if unit is None or position not in (1, 2):
            raise MsaMethodNotApplicable(
                "invalid_pairing",
                f"{unit_label}必須以 unit 與 position（1 或 2）成對表示",
                details={"index": index},
            )
        if position in pairs[unit]:
            raise MsaMethodNotApplicable(
                "invalid_pairing",
                f"同一{unit_label}的同一位置出現重複讀值",
                details={"unit": unit, "position": position},
            )
        pairs[unit][position] = _finite(row.get("value"), "value")

    incomplete = sorted(
        unit for unit, values in pairs.items() if len(values) != 2
    )
    if incomplete:
        raise MsaMethodNotApplicable(
            "incomplete_pairs",
            f"有{unit_label}沒有完整的兩筆配對讀值",
            details={"incomplete_units": incomplete[:20]},
        )
    if len(pairs) < MIN_PAIRS:
        raise MsaMethodNotApplicable(
            "insufficient_pairs",
            f"配對型設計至少需要 {MIN_PAIRS} 組配對",
            details={"pairs": len(pairs)},
        )

    units = sorted(pairs)
    firsts = [pairs[unit][1] for unit in units]
    seconds = [pairs[unit][2] for unit in units]
    differences = [b - a for a, b in zip(firsts, seconds)]
    count = len(differences)
    mean_difference = sum(differences) / count
    sd_difference = math.sqrt(
        sum((value - mean_difference) ** 2 for value in differences)
        / (count - 1)
    )
    # 兩筆獨立量測之差的變異數是單筆的兩倍
    paired_repeatability_sigma = sd_difference / math.sqrt(2)

    all_values = firsts + seconds
    overall_mean = sum(all_values) / len(all_values)
    total_sd = math.sqrt(
        sum((value - overall_mean) ** 2 for value in all_values)
        / (len(all_values) - 1)
    )

    warnings = []
    if abs(mean_difference) > sd_difference:
        warnings.append({
            "code": "MSA_NONREPEATABLE_PAIR_BIAS",
            "message": (
                "配對差平均明顯不為 0，可能存在位置或順序效應，"
                "配對假設需重新檢討"
            ),
        })

    sigmas = {"repeatability": paired_repeatability_sigma}
    statistics = {
        "method": "nonrepeatable",
        "design_type": design_type,
        "pairs": count,
        "mean_difference": mean_difference,
        "sd_difference": sd_difference,
        "repeatability_sigma": paired_repeatability_sigma,
        "observed_total_sd": total_sd,
        "study_variation_multiplier": context.study_variation_multiplier,
        "study_variation": {
            "repeatability": (
                context.study_variation_multiplier
                * paired_repeatability_sigma
            )
        },
        "percent_tolerance": _percent_tolerance(sigmas, context, warnings),
        "identifiable_sources": ["repeatability"],
        "unidentifiable_sources": [
            "reproducibility", "part_variation", "part_appraiser_interaction",
        ],
        "assumptions": list(REQUIRED_CONFIRMATIONS),
    }
    applicability = {
        "method": "nonrepeatable",
        "design_type": design_type,
        "applicable": True,
        "pairs": count,
        "tolerance_available": context.tolerance is not None,
        "limitations": [
            "破壞性試驗無法重複量測同一件，再現性與零件變差無法從本設計分離",
        ],
    }
    chart_data = {
        "pairs": [
            {"unit": unit, "first": first, "second": second,
             "difference": difference}
            for unit, first, second, difference
            in zip(units, firsts, seconds, differences)
        ],
        "mean_difference": mean_difference,
        "zero_line": 0.0,
    }
    return MsaAnalysisOutput(
        applicability=applicability,
        statistics=statistics,
        chart_data=chart_data,
        warnings=tuple(warnings),
    )


def analyze_split_sample(observations, context: MsaMethodContext):
    """分割樣本：同一件切分為兩份分別量測。"""
    return _paired_analysis(
        observations, context,
        design_type="split_sample", unit_label="分割樣本",
    )


def analyze_consecutive_pairs(observations, context: MsaMethodContext):
    """連續配對：假設連續產出的兩件在製程上等價。"""
    return _paired_analysis(
        observations, context,
        design_type="consecutive_paired", unit_label="連續配對",
    )


# ----------------------------------------------------------------------
# 巢狀設計
# ----------------------------------------------------------------------


def _nested_analysis(observations, context, *, design_type, group_key,
                     min_groups, group_label):
    """同質批次與多試驗台共用的單層巢狀變異數分析。"""
    groups = defaultdict(list)
    for index, row in enumerate(observations or []):
        group = row.get(group_key)
        if group is None:
            raise MsaMethodNotApplicable(
                "incomplete_observation",
                f"每筆讀值都必須標示所屬{group_label}",
                details={"index": index, "field": group_key},
            )
        groups[group].append(_finite(row.get("value"), "value"))

    if len(groups) < min_groups:
        raise MsaMethodNotApplicable(
            "insufficient_groups",
            f"{group_label}數量不足，至少需要 {min_groups} 組",
            details={"groups": len(groups)},
        )

    sizes = {len(values) for values in groups.values()}
    if len(sizes) != 1:
        raise MsaMethodNotApplicable(
            "unbalanced_design",
            "巢狀設計不平衡，目前沒有受控的混合模型方法版本可用",
            details={"group_sizes": sorted(sizes)},
        )
    size = sizes.pop()
    if size < 2:
        raise MsaMethodNotApplicable(
            "insufficient_replicates",
            f"每個{group_label}至少需要兩筆讀值才能估計組內變異",
            details={"replicates": size},
        )

    names = sorted(groups)
    all_values = [value for name in names for value in groups[name]]
    grand_mean = sum(all_values) / len(all_values)
    group_means = {
        name: sum(groups[name]) / size for name in names
    }

    ss_between = size * sum(
        (group_means[name] - grand_mean) ** 2 for name in names
    )
    ss_within = sum(
        (value - group_means[name]) ** 2
        for name in names for value in groups[name]
    )
    df_between = len(names) - 1
    df_within = len(names) * (size - 1)
    ms_between = ss_between / df_between
    ms_within = ss_within / df_within

    var_within = ms_within
    var_between_raw = (ms_between - ms_within) / size
    var_between = max(var_between_raw, 0.0)

    warnings = []
    if var_between_raw < 0:
        warnings.append({
            "code": "MSA_NONREPEATABLE_COMPONENT_CLAMPED",
            "message": f"{group_label}間變異數計算為負，依受控規則取 0",
        })

    repeatability_sigma = math.sqrt(var_within)
    sigmas = {"repeatability": repeatability_sigma}
    statistics = {
        "method": "nonrepeatable",
        "design_type": design_type,
        "groups": len(names),
        "replicates_per_group": size,
        "anova": {
            "table": [
                {
                    "source": f"between_{group_key}", "ss": ss_between,
                    "df": df_between, "ms": ms_between,
                },
                {
                    "source": "within_group", "ss": ss_within,
                    "df": df_within, "ms": ms_within,
                },
            ],
            "raw_variance_components": {
                f"between_{group_key}": var_between_raw,
                "within_group": var_within,
            },
            "adjusted_variance_components": {
                f"between_{group_key}": var_between,
                "within_group": var_within,
            },
        },
        "repeatability_sigma": repeatability_sigma,
        "study_variation_multiplier": context.study_variation_multiplier,
        "study_variation": {
            "repeatability": (
                context.study_variation_multiplier * repeatability_sigma
            )
        },
        "percent_tolerance": _percent_tolerance(sigmas, context, warnings),
        "identifiable_sources": ["repeatability", f"between_{group_key}"],
        "unidentifiable_sources": ["reproducibility", "part_variation"],
        "assumptions": list(REQUIRED_CONFIRMATIONS),
    }
    applicability = {
        "method": "nonrepeatable",
        "design_type": design_type,
        "applicable": True,
        "groups": len(names),
        "balanced": True,
        "tolerance_available": context.tolerance is not None,
        "limitations": [
            f"{group_label}間變異與真實零件變差在本設計下無法完全分離",
        ],
    }
    chart_data = {
        "group_means": group_means,
        "grand_mean": grand_mean,
        "group_values": {name: groups[name] for name in names},
    }
    return MsaAnalysisOutput(
        applicability=applicability,
        statistics=statistics,
        chart_data=chart_data,
        warnings=tuple(warnings),
    )


def analyze_homogeneous_lot(observations, context: MsaMethodContext):
    """同質批次：假設同批內各件的真值相同。"""
    return _nested_analysis(
        observations, context,
        design_type="homogeneous_lot", group_key="lot",
        min_groups=MIN_LOTS, group_label="批次",
    )


def analyze_multiple_stations(observations, context: MsaMethodContext):
    """多試驗台：比較各試驗台之間的差異與台內重複性。"""
    return _nested_analysis(
        observations, context,
        design_type="multiple_stations", group_key="station",
        min_groups=MIN_STATIONS, group_label="試驗台",
    )


ANALYZERS = {
    "split_sample": analyze_split_sample,
    "consecutive_paired": analyze_consecutive_pairs,
    "homogeneous_lot": analyze_homogeneous_lot,
    "multiple_stations": analyze_multiple_stations,
}


# ----------------------------------------------------------------------
# 共用
# ----------------------------------------------------------------------


def _percent_tolerance(sigmas: dict, context: MsaMethodContext, warnings):
    if not context.tolerance or context.tolerance <= 0:
        warnings.append({
            "code": "MSA_TOLERANCE_UNAVAILABLE",
            "message": "研究沒有可用公差，無法計算 %Tolerance",
        })
        return None
    return {
        key: (
            100.0 * context.study_variation_multiplier * value
            / context.tolerance
        )
        for key, value in sigmas.items()
    }
