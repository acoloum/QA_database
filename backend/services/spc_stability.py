"""穩定性準則（失控準則）判定 — AIAG-VDA SPC 2026 §9.2.2

每增加一條準則會提高誤警率約 10%（§9.2.2.1），
因此預設僅啟用精簡集，其餘準則以參數啟用。
"""
from typing import Any, Dict, List, Optional

# 預設精簡準則集（§9.2.2.1：避免同時套用多項準則）
DEFAULT_STABILITY_RULES = ["beyond_limits", "run_9_same_side", "trend_6"]

# 手冊 §9.2.2 列舉的完整準則（Western Electric / Nelson 子集）
ALL_STABILITY_RULES = [
    "beyond_limits",           # 單點超出管制界限（±3σ）
    "two_of_three_beyond_2s",  # 連續3點中2點位於同側且超出2σ
    "four_of_five_beyond_1s",  # 連續5點中4點位於同側且超出1σ
    "run_9_same_side",         # 連續9點位於中心線同側
    "trend_6",                 # 連續6點持續上升或下降
    "fifteen_within_1s",       # 連續15點皆在中心線±1σ內
]

RULE_LABELS = {
    "beyond_limits": "單點超出管制界限",
    "two_of_three_beyond_2s": "3點中2點超出同側2σ",
    "four_of_five_beyond_1s": "5點中4點超出同側1σ",
    "run_9_same_side": "連續9點同側",
    "trend_6": "連續6點趨勢",
    "fifteen_within_1s": "連續15點在1σ內",
}


def evaluate_stability(
    avgs: List[float],
    x_cl: float,
    x_ucl: float,
    x_lcl: float,
    enabled_rules: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """依啟用的穩定性準則評估製程是否統計受控。

    回傳 evaluated=False 表示資料不足無法評估（此時只能報 Pp/Ppk，§6.2）。
    """
    rules = enabled_rules if enabled_rules is not None else DEFAULT_STABILITY_RULES
    result: Dict[str, Any] = {
        "evaluated": False,
        "stable": None,
        "violations": [],
        "rules_used": rules,
    }
    if len(avgs) < 5 or x_ucl <= x_cl:
        return result

    sigma = (x_ucl - x_cl) / 3
    violations: List[Dict[str, Any]] = []

    def add(idx: int, rule: str) -> None:
        violations.append({"index": idx, "rule": rule, "label": RULE_LABELS[rule]})

    for i, v in enumerate(avgs):
        if "beyond_limits" in rules and (v > x_ucl or v < x_lcl):
            add(i, "beyond_limits")
        if "two_of_three_beyond_2s" in rules and i >= 2:
            w = avgs[i - 2:i + 1]
            above = sum(1 for x in w if x > x_cl + 2 * sigma)
            below = sum(1 for x in w if x < x_cl - 2 * sigma)
            if above >= 2 or below >= 2:
                add(i, "two_of_three_beyond_2s")
        if "four_of_five_beyond_1s" in rules and i >= 4:
            w = avgs[i - 4:i + 1]
            above = sum(1 for x in w if x > x_cl + sigma)
            below = sum(1 for x in w if x < x_cl - sigma)
            if above >= 4 or below >= 4:
                add(i, "four_of_five_beyond_1s")
        if "run_9_same_side" in rules and i >= 8:
            w = avgs[i - 8:i + 1]
            if all(x > x_cl for x in w) or all(x < x_cl for x in w):
                add(i, "run_9_same_side")
        if "trend_6" in rules and i >= 5:
            w = avgs[i - 5:i + 1]
            inc = all(w[j] > w[j - 1] for j in range(1, 6))
            dec = all(w[j] < w[j - 1] for j in range(1, 6))
            if inc or dec:
                add(i, "trend_6")
        if "fifteen_within_1s" in rules and i >= 14:
            w = avgs[i - 14:i + 1]
            if all(abs(x - x_cl) <= sigma for x in w):
                add(i, "fifteen_within_1s")

    result["evaluated"] = True
    result["stable"] = len(violations) == 0
    result["violations"] = violations
    return result
