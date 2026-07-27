"""計數型量測系統分析：一致性、Kappa 與錯誤率。

沒有可信參考標準時，只能報告「一致性」，不得輸出任何暗示正確性的
指標；分母為 0 的比率一律回報不可用與原因，不以 0 混充。
"""

from collections import defaultdict
import math

from .msa_contracts import MsaAnalysisOutput, MsaMethodContext
from .msa_errors import MsaMethodNotApplicable


# 常態近似的雙尾 95% 臨界值；alpha 不同時改由 context 帶入。
_Z_BY_ALPHA = {
    0.10: 1.6448536269514722,
    0.05: 1.959963984540054,
    0.01: 2.5758293035489004,
}

MIN_TRIALS = 2


def analyze_attribute(observations, context: MsaMethodContext):
    """計算評價人內／間一致性、相對參考標準的 Kappa 與錯誤率。"""
    rows = _validated(observations)
    samples = sorted({row["sample"] for row in rows})
    appraisers = sorted({row["appraiser"] for row in rows})
    labels = sorted({row["value"] for row in rows} | {
        row["reference"] for row in rows if row.get("reference") is not None
    })

    by_appraiser_sample = defaultdict(list)
    for row in rows:
        by_appraiser_sample[(row["appraiser"], row["sample"])].append(
            row["value"]
        )

    trial_counts = {len(values) for values in by_appraiser_sample.values()}
    if len(by_appraiser_sample) != len(appraisers) * len(samples):
        raise MsaMethodNotApplicable(
            "unbalanced_design",
            "有評價人與樣本的組合沒有任何判定",
            details={
                "expected_cells": len(appraisers) * len(samples),
                "actual_cells": len(by_appraiser_sample),
            },
        )
    if min(trial_counts) < MIN_TRIALS:
        raise MsaMethodNotApplicable(
            "insufficient_trials",
            "計數型研究每位評價人對每件樣本至少要判定兩次",
            details={"trial_counts": sorted(trial_counts)},
        )

    warnings = []
    accuracy_available, reference_by_sample = _reference_truth(rows, warnings)

    statistics = {
        "method": "attribute",
        "labels": labels,
        "samples": len(samples),
        "appraisers": len(appraisers),
        "accuracy_available": accuracy_available,
        "within_appraiser": _within_appraiser(
            appraisers, samples, by_appraiser_sample
        ),
        "between_appraiser": _between_appraiser(
            appraisers, samples, by_appraiser_sample
        ),
    }

    if accuracy_available:
        statistics.update(
            _accuracy_section(
                rows, samples, appraisers, labels, by_appraiser_sample,
                reference_by_sample, context, warnings,
            )
        )

    applicability = {
        "method": "attribute",
        "applicable": True,
        "samples": len(samples),
        "appraisers": len(appraisers),
        "trials": sorted(trial_counts)[0],
        "label_count": len(labels),
        "binary": len(labels) == 2,
        "accuracy_available": accuracy_available,
    }
    chart_data = {
        "confusion_matrix": statistics.get("confusion_matrix"),
        "within_appraiser": statistics["within_appraiser"],
        "between_appraiser": statistics["between_appraiser"],
        "strata": statistics.get("strata"),
    }
    return MsaAnalysisOutput(
        applicability=applicability,
        statistics=statistics,
        chart_data=chart_data,
        warnings=tuple(warnings),
    )


# ----------------------------------------------------------------------
# 輸入
# ----------------------------------------------------------------------


def _validated(observations):
    rows = list(observations or [])
    if not rows:
        raise MsaMethodNotApplicable(
            "no_observations", "沒有可分析的計數型判定", details={},
        )
    for index, row in enumerate(rows):
        for field in ("sample", "appraiser", "value"):
            if not row.get(field):
                raise MsaMethodNotApplicable(
                    "incomplete_observation",
                    f"計數型判定缺少 {field}",
                    details={"index": index, "field": field},
                )
    return rows


def _reference_truth(rows, warnings):
    """判斷是否有可用且可信的參考標準。"""
    has_reference = all(row.get("reference") is not None for row in rows)
    if not has_reference:
        warnings.append({
            "code": "MSA_ATTRIBUTE_REFERENCE_UNAVAILABLE",
            "message": (
                "缺少可追溯的參考標準，只能報告評價人之間的一致性，"
                "不得推論判定是否正確"
            ),
        })
        return False, {}

    if any(row.get("reference_trusted") is False for row in rows):
        warnings.append({
            "code": "MSA_ATTRIBUTE_REFERENCE_NOT_TRUSTED",
            "message": (
                "參考標準被標示為不可信，已阻擋所有正確辨識相關結論"
            ),
        })
        return False, {}

    truth = {}
    for row in rows:
        existing = truth.setdefault(row["sample"], row["reference"])
        if existing != row["reference"]:
            raise MsaMethodNotApplicable(
                "conflicting_reference",
                "同一樣本出現不一致的參考標準",
                details={"sample": row["sample"]},
            )
    return True, truth


# ----------------------------------------------------------------------
# 一致性
# ----------------------------------------------------------------------


def _within_appraiser(appraisers, samples, by_appraiser_sample):
    result = {}
    for appraiser in appraisers:
        consistent = sum(
            1 for sample in samples
            if len(set(by_appraiser_sample[(appraiser, sample)])) == 1
        )
        result[appraiser] = {
            "consistent": consistent,
            "total": len(samples),
            "agreement": consistent / len(samples),
        }
    return result


def _between_appraiser(appraisers, samples, by_appraiser_sample):
    consistent = 0
    for sample in samples:
        verdicts = {
            value
            for appraiser in appraisers
            for value in by_appraiser_sample[(appraiser, sample)]
        }
        if len(verdicts) == 1:
            consistent += 1
    return {
        "consistent": consistent,
        "total": len(samples),
        "agreement": consistent / len(samples),
    }


# ----------------------------------------------------------------------
# 相對參考標準
# ----------------------------------------------------------------------


def _accuracy_section(
    rows, samples, appraisers, labels, by_appraiser_sample,
    reference_by_sample, context, warnings,
):
    decisions = [(row["value"], row["reference"]) for row in rows]
    total = len(decisions)

    observed_agreement = sum(1 for a, b in decisions if a == b) / total
    row_total = {
        label: sum(1 for a, _b in decisions if a == label) / total
        for label in labels
    }
    col_total = {
        label: sum(1 for _a, b in decisions if b == label) / total
        for label in labels
    }
    expected_agreement = sum(
        row_total[label] * col_total[label] for label in labels
    )

    kappa = kappa_se = None
    kappa_ci = None
    kappa_unavailable_reason = None
    if expected_agreement >= 1:
        kappa_unavailable_reason = "期望一致性為 1，Kappa 分母為 0，無法估計"
        warnings.append({
            "code": "MSA_ATTRIBUTE_KAPPA_UNAVAILABLE",
            "message": kappa_unavailable_reason,
        })
    else:
        kappa = (observed_agreement - expected_agreement) / (
            1 - expected_agreement
        )
        kappa_se = math.sqrt(
            observed_agreement * (1 - observed_agreement)
            / (total * (1 - expected_agreement) ** 2)
        )
        z = _Z_BY_ALPHA.get(context.alpha)
        if z is None:
            warnings.append({
                "code": "MSA_ATTRIBUTE_KAPPA_CI_UNAVAILABLE",
                "message": "準則指定的顯著水準沒有受控臨界值，未輸出 Kappa 區間",
            })
        else:
            kappa_ci = [kappa - z * kappa_se, kappa + z * kappa_se]

    per_appraiser = {}
    for appraiser in appraisers:
        correct = sum(
            1 for sample in samples
            if all(
                value == reference_by_sample[sample]
                for value in by_appraiser_sample[(appraiser, sample)]
            )
        )
        per_appraiser[appraiser] = {
            "correct": correct,
            "total": len(samples),
            "agreement": correct / len(samples),
        }

    overall_correct = sum(
        1 for sample in samples
        if all(
            value == reference_by_sample[sample]
            for appraiser in appraisers
            for value in by_appraiser_sample[(appraiser, sample)]
        )
    )
    effectiveness = 100.0 * overall_correct / len(samples)

    confusion = {
        actual: {
            predicted: sum(
                1 for a, b in decisions if b == actual and a == predicted
            )
            for predicted in labels
        }
        for actual in labels
    }

    section = {
        "against_reference": {
            "per_appraiser": per_appraiser,
            "overall": {
                "correct": overall_correct,
                "total": len(samples),
                "agreement": overall_correct / len(samples),
                "observed_agreement": observed_agreement,
                "expected_agreement": expected_agreement,
                "kappa": kappa,
                "kappa_standard_error": kappa_se,
                "kappa_confidence_interval": kappa_ci,
                "kappa_unavailable_reason": kappa_unavailable_reason,
                "kappa_method": "cohen_vs_reference",
            },
        },
        "effectiveness": effectiveness,
        "confusion_matrix": confusion,
        "strata": _strata(rows),
    }
    section.update(_error_rates(decisions, labels, warnings))
    return section


def _error_rates(decisions, labels, warnings):
    """誤收與誤拒率；只適用二分類，分母為 0 時回不可用。

    只出現一種類別時仍視為二分類研究，只是缺少對照類別的樣本，
    因此回報的是分母不足而非「不是二分類」。
    """
    if len(labels) > 2:
        reason = "誤收與誤拒率只適用於二分類判定"
        warnings.append({
            "code": "MSA_ATTRIBUTE_ERROR_RATES_UNAVAILABLE",
            "message": reason,
        })
        return {
            "false_accept_rate": None,
            "false_reject_rate": None,
            "false_accept_unavailable_reason": reason,
            "false_reject_unavailable_reason": reason,
        }

    # 以字典序較小者為「合格」語意之外的判定，仍以顯式標籤表示
    accept_label, reject_label = _binary_labels(labels)
    reject_decisions = sum(1 for _a, b in decisions if b == reject_label)
    accept_decisions = sum(1 for _a, b in decisions if b == accept_label)
    false_accept = sum(
        1 for a, b in decisions if b == reject_label and a == accept_label
    )
    false_reject = sum(
        1 for a, b in decisions if b == accept_label and a == reject_label
    )

    result = {
        "accept_label": accept_label,
        "reject_label": reject_label,
        "false_accept_count": false_accept,
        "false_reject_count": false_reject,
    }
    if reject_decisions == 0:
        reason = "參考標準中沒有應判退的樣本，無法估計誤收率"
        warnings.append({
            "code": "MSA_ATTRIBUTE_ERROR_RATES_UNAVAILABLE",
            "message": reason,
        })
        result["false_accept_rate"] = None
        result["false_accept_unavailable_reason"] = reason
    else:
        result["false_accept_rate"] = 100.0 * false_accept / reject_decisions

    if accept_decisions == 0:
        reason = "參考標準中沒有應判合格的樣本，無法估計誤拒率"
        warnings.append({
            "code": "MSA_ATTRIBUTE_ERROR_RATES_UNAVAILABLE",
            "message": reason,
        })
        result["false_reject_rate"] = None
        result["false_reject_unavailable_reason"] = reason
    else:
        result["false_reject_rate"] = 100.0 * false_reject / accept_decisions

    return result


def _binary_labels(labels):
    """辨識合格／不合格標籤；缺少的一側回 None，不臆造對照類別。"""
    accept_candidates = {"pass", "accept", "ok", "good", "合格"}
    reject_candidates = {"fail", "reject", "ng", "bad", "不合格"}
    accept = next(
        (label for label in labels if str(label).lower() in accept_candidates),
        None,
    )
    reject = next(
        (label for label in labels if str(label).lower() in reject_candidates),
        None,
    )
    if accept is not None and reject is not None:
        return accept, reject
    if len(labels) == 2:
        # 無法由名稱辨識語意時，以固定順序表示，不臆測哪一邊是合格
        return labels[0], labels[1]
    single = labels[0]
    if accept is not None:
        return single, None
    if reject is not None:
        return None, single
    return single, None


def _strata(rows):
    """把灰色區與非灰色區分開報告，避免界限附近的問題被整體平均稀釋。"""
    if not any("grey_zone" in row for row in rows):
        return None
    result = {}
    for name, predicate in (
        ("grey_zone", lambda row: bool(row.get("grey_zone"))),
        ("non_grey_zone", lambda row: not row.get("grey_zone")),
    ):
        subset = [row for row in rows if predicate(row)]
        if not subset:
            continue
        correct = sum(
            1 for row in subset if row["value"] == row["reference"]
        )
        result[name] = {
            "decisions": len(subset),
            "correct": correct,
            "agreement": correct / len(subset),
        }
    return result
