"""ISO 22514-2 時間相依分布模型的保守候選判定。"""

from typing import Any, Dict

from .spc_contracts import SpcChartSet


def classify_time_model(
    chart_set: SpcChartSet,
    stability: Dict[str, Any],
    distribution: Dict[str, Any],
) -> Dict[str, Any]:
    """產生 A1/A2/B/C/D 候選與證據，不自動核准模型。"""

    location = stability.get("location", {})
    variation = stability.get("variation", {})
    location_stable = location.get("stable")
    variation_stable = variation.get("stable")
    location_rules = [item.get("rule") for item in location.get("violations", [])]
    evidence = {
        "chart_type": chart_set.chart_type,
        "location_stable": location_stable,
        "variation_stable": variation_stable,
        "location_rules": location_rules,
        "distribution_model": distribution.get("model"),
        "distribution_accepted": bool(distribution.get("accepted")),
    }
    result = {
        "candidate": None,
        "candidate_options": [],
        "confirmed": False,
        "statistically_controlled": False,
        "reason_code": "TIME_MODEL_UNCONFIRMED",
        "evidence": evidence,
    }
    if not stability.get("evaluated"):
        return result

    if location_stable is True and variation_stable is True:
        if not distribution.get("accepted") or not distribution.get("unimodal"):
            return result
        result["candidate"] = "A1" if distribution.get("model") == "normal" else "A2"
        result["statistically_controlled"] = True
    elif location_stable is True and variation_stable is False:
        result["candidate"] = "B"
    elif location_stable is False and variation_stable is True:
        result["candidate"] = "C3" if "trend_6" in location_rules else "C4"
        result["candidate_options"] = ["C1", "C2", "C3", "C4"]
    elif location_stable is False and variation_stable is False:
        result["candidate"] = "D"

    if result["candidate"] is not None:
        if not result["candidate_options"]:
            result["candidate_options"] = [result["candidate"]]
        result["reason_code"] = None
    return result
