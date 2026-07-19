"""穩定性準則（失控準則）判定 — AIAG-VDA SPC 2026 §9.2.2

每增加一條準則會提高誤警率約 10%（§9.2.2.1），
因此預設僅啟用精簡集，其餘準則以參數啟用。
"""
from collections.abc import Sequence
from numbers import Real
from typing import Any, Dict, List, Optional

from .spc_contracts import SpcChartSet

# 預設精簡準則集（§9.2.2.1：避免同時套用多項準則）。本模組是正式判定
# 的唯一權威；前端 spcAnalysis.ts 僅保留展示與測試工具，不得覆蓋此結果。
DEFAULT_STABILITY_RULES = ["beyond_limits", "run_9_same_side", "trend_6"]

# 手冊 §9.2.2 列舉的完整準則（Western Electric / Nelson 子集）。規則代碼是
# API 與報表的受控契約；前端只顯示後端回傳的代碼與違規視窗。
ALL_STABILITY_RULES = [
    "beyond_limits",           # 單點超出管制界限（±3σ）
    "two_of_three_beyond_2s",  # 連續3點中2點位於同側且超出2σ
    "four_of_five_beyond_1s",  # 連續5點中4點位於同側且超出1σ
    "run_9_same_side",         # 連續9點位於中心線同側
    "trend_6",                 # 連續6點持續上升或下降
    "fifteen_within_1s",       # 連續15點皆在中心線±1σ內
    "alternating_14",          # 連續14點交替上升下降
    "eight_beyond_1s_both",    # 連續8點在中心線兩側但都不在1σ內
]

RULE_LABELS = {
    "beyond_limits": "單點超出管制界限",
    "two_of_three_beyond_2s": "3點中2點超出同側2σ",
    "four_of_five_beyond_1s": "5點中4點超出同側1σ",
    "run_9_same_side": "連續9點同側",
    "trend_6": "連續6點趨勢",
    "fifteen_within_1s": "連續15點在1σ內",
    "alternating_14": "連續14點交替上升下降",
    "eight_beyond_1s_both": "連續8點在1σ外且兩側",
}


def _limit_array(value: Real | Sequence[float], count: int, name: str) -> tuple[float, ...]:
    if isinstance(value, Real):
        return (float(value),) * count
    result = tuple(float(item) for item in value)
    if len(result) != count:
        raise ValueError(f"{name} 長度必須與資料點一致")
    return result


def evaluate_chart_stability(
    values: Sequence[Optional[float]],
    cl: Real | Sequence[float],
    ucl: Real | Sequence[float],
    lcl: Real | Sequence[float],
    *,
    chart_kind: str,
    enabled_rules: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """依每個資料點實際界限評估單一管制圖。"""

    rules = list(enabled_rules if enabled_rules is not None else DEFAULT_STABILITY_RULES)
    point_values = tuple(float(value) if value is not None else None for value in values)
    count = len(point_values)
    centers = _limit_array(cl, count, "CL")
    upper_limits = _limit_array(ucl, count, "UCL")
    lower_limits = _limit_array(lcl, count, "LCL")
    result: Dict[str, Any] = {
        "evaluated": False,
        "stable": None,
        "violations": [],
        "rules_used": rules,
        "chart_kind": chart_kind,
    }
    numeric_count = sum(value is not None for value in point_values)
    if numeric_count < 5 or any(upper <= center for upper, center in zip(upper_limits, centers)):
        return result

    upper_sigmas = tuple(
        (upper - center) / 3.0 for upper, center in zip(upper_limits, centers)
    )
    lower_sigmas = tuple(
        (center - lower) / 3.0 for lower, center in zip(lower_limits, centers)
    )
    violations: List[Dict[str, Any]] = []
    seen: set[tuple[int, str, str]] = set()

    def add(index: int, rule: str, window_start: int) -> None:
        key = (index, rule, chart_kind)
        if key in seen:
            return
        seen.add(key)
        violations.append({
            "index": index,
            "window_start": window_start,
            "window_end": index,
            "rule": rule,
            "label": RULE_LABELS[rule],
            "chart_kind": chart_kind,
        })

    def complete_window(start: int, end: int) -> Optional[tuple[float, ...]]:
        window = point_values[start:end]
        if any(value is None for value in window):
            return None
        return tuple(value for value in window if value is not None)

    for index, value in enumerate(point_values):
        if value is None:
            continue
        if "beyond_limits" in rules and (
            value > upper_limits[index] or value < lower_limits[index]
        ):
            add(index, "beyond_limits", index)

        if "two_of_three_beyond_2s" in rules and index >= 2:
            start = index - 2
            window = complete_window(start, index + 1)
            if window is not None:
                above = sum(
                    point_values[j] > centers[j] + 2 * upper_sigmas[j]
                    for j in range(start, index + 1)
                )
                below = sum(
                    point_values[j] < centers[j] - 2 * lower_sigmas[j]
                    for j in range(start, index + 1)
                )
                if above >= 2 or below >= 2:
                    add(index, "two_of_three_beyond_2s", start)

        if "four_of_five_beyond_1s" in rules and index >= 4:
            start = index - 4
            window = complete_window(start, index + 1)
            if window is not None:
                above = sum(
                    point_values[j] > centers[j] + upper_sigmas[j]
                    for j in range(start, index + 1)
                )
                below = sum(
                    point_values[j] < centers[j] - lower_sigmas[j]
                    for j in range(start, index + 1)
                )
                if above >= 4 or below >= 4:
                    add(index, "four_of_five_beyond_1s", start)

        if "run_9_same_side" in rules and index >= 8:
            start = index - 8
            window = complete_window(start, index + 1)
            if window is not None:
                all_above = all(point_values[j] > centers[j] for j in range(start, index + 1))
                all_below = all(point_values[j] < centers[j] for j in range(start, index + 1))
                if all_above or all_below:
                    add(index, "run_9_same_side", start)

        if "trend_6" in rules and index >= 5:
            start = index - 5
            window = complete_window(start, index + 1)
            if window is not None:
                increasing = all(window[j] > window[j - 1] for j in range(1, len(window)))
                decreasing = all(window[j] < window[j - 1] for j in range(1, len(window)))
                if increasing or decreasing:
                    add(index, "trend_6", start)

        if "fifteen_within_1s" in rules and index >= 14:
            start = index - 14
            window = complete_window(start, index + 1)
            if window is not None and all(
                centers[j] - lower_sigmas[j]
                <= point_values[j]
                <= centers[j] + upper_sigmas[j]
                for j in range(start, index + 1)
            ):
                add(index, "fifteen_within_1s", start)

        if "alternating_14" in rules and index >= 13:
            start = index - 13
            window = complete_window(start, index + 1)
            if window is not None:
                differences = [window[j] - window[j - 1] for j in range(1, len(window))]
                if all(difference != 0 for difference in differences) and all(
                    differences[j] * differences[j - 1] < 0
                    for j in range(1, len(differences))
                ):
                    add(index, "alternating_14", start)

        if "eight_beyond_1s_both" in rules and index >= 7:
            start = index - 7
            window = complete_window(start, index + 1)
            if window is not None:
                outside_zone_c = all(
                    point_values[j] < centers[j] - lower_sigmas[j]
                    or point_values[j] > centers[j] + upper_sigmas[j]
                    for j in range(start, index + 1)
                )
                has_above = any(point_values[j] > centers[j] for j in range(start, index + 1))
                has_below = any(point_values[j] < centers[j] for j in range(start, index + 1))
                if outside_zone_c and has_above and has_below:
                    add(index, "eight_beyond_1s_both", start)

    result["evaluated"] = True
    result["stable"] = not violations
    result["violations"] = violations
    return result


def evaluate_study_stability(
    chart_set: SpcChartSet,
    enabled_rules: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """位置圖與變異圖共同決定研究是否統計受控。"""

    variation = evaluate_chart_stability(
        chart_set.variation.values,
        chart_set.variation.cl,
        chart_set.variation.ucl,
        chart_set.variation.lcl,
        chart_kind="variation",
        enabled_rules=enabled_rules,
    )
    location = evaluate_chart_stability(
        chart_set.location.values,
        chart_set.location.cl,
        chart_set.location.ucl,
        chart_set.location.lcl,
        chart_kind="location",
        enabled_rules=enabled_rules,
    )
    evaluated = bool(variation["evaluated"] and location["evaluated"])
    stable = bool(variation["stable"] and location["stable"]) if evaluated else None
    return {
        "evaluated": evaluated,
        "stable": stable,
        "location": location,
        "variation": variation,
        "violations": variation["violations"] + location["violations"],
        "rules_used": list(enabled_rules if enabled_rules is not None else DEFAULT_STABILITY_RULES),
    }


def evaluate_attribute_stability(
    chart: Dict[str, Any], enabled_rules: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """以精確計數界限及 Pearson 殘差評估屬性型 SPC。"""

    rules = list(enabled_rules if enabled_rules is not None else DEFAULT_STABILITY_RULES)
    residuals = list(chart.get("pearson_residuals") or [])
    # beyond-limits 的離散邊界只能依 raw count 的精確二項語意判斷；其餘規則
    # 則以中心為 0、三 sigma 為 ±3 的 Pearson 殘差判定。
    residual_rules = [rule for rule in rules if rule != "beyond_limits"]
    residual = evaluate_chart_stability(
        residuals, 0.0, 3.0, -3.0, chart_kind="location",
        enabled_rules=residual_rules,
    )
    violations = list(residual["violations"])
    for index, flag in enumerate(chart.get("ooc_flags") or []):
        if "beyond_limits" in rules and flag.get("out_of_control"):
            violations.append({
                "index": index, "window_start": index, "window_end": index,
                "rule": "beyond_limits", "label": RULE_LABELS["beyond_limits"],
                "chart_kind": "location",
            })
    location = {
        **residual,
        "evaluated": len(residuals) >= 5,
        "stable": not violations if len(residuals) >= 5 else None,
        "violations": violations,
        "rules_used": rules,
        "residual_method": "binomial_pearson",
        "center": 0.0,
    }
    variation = {
        "evaluated": True, "stable": True, "violations": [],
        "rules_used": rules, "chart_kind": "variation", "not_applicable": True,
    }
    return {
        "evaluated": location["evaluated"], "stable": location["stable"],
        "location": location, "variation": variation, "violations": violations,
        "rules_used": rules, "residual_method": "binomial_pearson",
    }


def evaluate_stability(
    avgs: List[float],
    x_cl: float,
    x_ucl: float,
    x_lcl: float,
    enabled_rules: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """舊 X̄ 純量 API 的相容包裝。"""

    return evaluate_chart_stability(
        avgs,
        x_cl,
        x_ucl,
        x_lcl,
        chart_kind="location",
        enabled_rules=enabled_rules,
    )
