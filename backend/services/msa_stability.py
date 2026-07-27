"""MSA 穩定性分析：以基準件的時間序列判定量測系統是否隨時間漂移。

刻意不輸出任何單一「穩定性指數」——穩定與否由受控判異規則的違反
清單表達，不以一個數字掩蓋實際發生了什麼。
"""

from datetime import date, datetime
import math

from .msa_contracts import MsaAnalysisOutput, MsaMethodContext
from .msa_errors import MsaMethodNotApplicable


# 管制圖常數，只涵蓋受控子組大小；超出範圍不得外插。
A2 = {2: 1.880, 3: 1.023, 4: 0.729, 5: 0.577, 6: 0.483, 7: 0.419,
      8: 0.373, 9: 0.337, 10: 0.308}
D3 = {2: 0.0, 3: 0.0, 4: 0.0, 5: 0.0, 6: 0.0, 7: 0.076, 8: 0.136,
      9: 0.184, 10: 0.223}
D4 = {2: 3.267, 3: 2.574, 4: 2.282, 5: 2.114, 6: 2.004, 7: 1.924,
      8: 1.864, 9: 1.816, 10: 1.777}
D2_MR = 1.128  # I-MR 圖以移動全距（n=2）估計標準差

MIN_SUBGROUPS = 20
MAX_SUBGROUP_SIZE_FOR_RANGE = 10

SUPPORTED_RULES = (1, 2, 3, 4)


def analyze_stability(subgroups, context: MsaMethodContext):
    """依子組大小選用 I-MR、Xbar-R 或 Xbar-S，並套用受控判異規則。"""
    series = _validated_series(subgroups)
    sizes = {len(item["readings"]) for item in series}
    if len(sizes) != 1:
        raise MsaMethodNotApplicable(
            "inconsistent_subgroup_size",
            "各期子組大小不一致，不可套用固定管制圖常數",
            details={"sizes": sorted(sizes)},
        )
    size = sizes.pop()

    if size == 1:
        chart_type = "i_mr"
    elif size <= MAX_SUBGROUP_SIZE_FOR_RANGE:
        chart_type = "xbar_r"
    else:
        chart_type = "xbar_s"

    if len(series) < MIN_SUBGROUPS:
        raise MsaMethodNotApplicable(
            "insufficient_baseline",
            f"穩定性研究至少需要 {MIN_SUBGROUPS} 期基準資料",
            details={"subgroups": len(series)},
        )

    if chart_type == "i_mr":
        primary, secondary = _i_mr_limits(series)
    elif chart_type == "xbar_r":
        primary, secondary = _xbar_r_limits(series, size)
    else:
        primary, secondary = _xbar_s_limits(series, size)

    enabled_rules = _enabled_rules(context)
    violations = _apply_rules(primary, enabled_rules)
    violations.extend(_limit_violations(secondary, secondary["label"]))

    missing_intervals = _missing_intervals(series)
    warnings = []
    if missing_intervals:
        warnings.append({
            "code": "MSA_STABILITY_MISSING_INTERVALS",
            "message": "基準期之間有明顯遺漏的量測間隔，趨勢判讀需留意",
        })

    statistics = {
        "method": "stability",
        "chart_type": chart_type,
        "subgroup_size": size,
        "baseline_period": {
            "from": series[0]["measured_on"],
            "to": series[-1]["measured_on"],
            "count": len(series),
        },
        "stable": not violations,
        "rule_set": "WECO",
        "enabled_rules": list(enabled_rules),
        "rule_violations": violations,
        "missing_intervals": missing_intervals,
        "center_line": primary["center"],
        "control_limits": {
            "ucl": primary["ucl"], "lcl": primary["lcl"],
        },
        "dispersion_limits": {
            "label": secondary["label"],
            "center": secondary["center"],
            "ucl": secondary["ucl"],
            "lcl": secondary["lcl"],
        },
    }
    applicability = {
        "method": "stability",
        "applicable": True,
        "chart_type": chart_type,
        "subgroups": len(series),
        "subgroup_size": size,
    }
    chart_data = {
        "primary_chart": {
            "label": primary["label"],
            "center": primary["center"],
            "ucl": primary["ucl"],
            "lcl": primary["lcl"],
            "points": [
                {
                    "measured_on": item["measured_on"],
                    "value": value,
                    "readings": item["readings"],
                }
                for item, value in zip(series, primary["values"])
            ],
        },
        "dispersion_chart": {
            "label": secondary["label"],
            "center": secondary["center"],
            "ucl": secondary["ucl"],
            "lcl": secondary["lcl"],
            "points": [
                {"measured_on": item["measured_on"], "value": value}
                for item, value in zip(
                    series[-len(secondary["values"]):], secondary["values"]
                )
            ],
        },
        "event_markers": [
            {
                "measured_on": item["measured_on"],
                "event": item["event"],
            }
            for item in series if item.get("event")
        ],
    }
    return MsaAnalysisOutput(
        applicability=applicability,
        statistics=statistics,
        chart_data=chart_data,
        warnings=tuple(warnings),
    )


# ----------------------------------------------------------------------
# 輸入整理
# ----------------------------------------------------------------------


def _validated_series(subgroups):
    rows = list(subgroups or [])
    if not rows:
        raise MsaMethodNotApplicable(
            "no_observations", "沒有可分析的穩定性資料", details={},
        )

    series = []
    for index, row in enumerate(rows):
        measured_on = row.get("measured_on")
        if not measured_on:
            raise MsaMethodNotApplicable(
                "missing_timestamp",
                "每期穩定性資料都必須有量測日期",
                details={"index": index},
            )
        readings = [
            _finite(value, "reading") for value in (row.get("readings") or [])
        ]
        if not readings:
            raise MsaMethodNotApplicable(
                "empty_subgroup",
                "每期至少要有一筆讀值",
                details={"index": index},
            )
        series.append({
            "measured_on": str(measured_on),
            "readings": readings,
            "event": row.get("event"),
        })

    ordered = [item["measured_on"] for item in series]
    if ordered != sorted(ordered):
        raise MsaMethodNotApplicable(
            "unsorted_time_series",
            "穩定性資料必須依量測時間排序",
            details={},
        )
    return series


def _enabled_rules(context: MsaMethodContext):
    rules = (context.criteria or {}).get("stability_rules") or {}
    enabled = rules.get("enabled_rules") or list(SUPPORTED_RULES)
    unsupported = sorted(set(enabled) - set(SUPPORTED_RULES))
    if unsupported:
        raise MsaMethodNotApplicable(
            "unsupported_stability_rule",
            "準則指定了尚未實作的判異規則",
            details={"unsupported": unsupported},
        )
    return tuple(sorted(enabled))


# ----------------------------------------------------------------------
# 管制界限
# ----------------------------------------------------------------------


def _i_mr_limits(series):
    values = [item["readings"][0] for item in series]
    moving_ranges = [
        abs(values[index] - values[index - 1])
        for index in range(1, len(values))
    ]
    mr_bar = sum(moving_ranges) / len(moving_ranges)
    center = sum(values) / len(values)
    sigma = mr_bar / D2_MR
    primary = {
        "label": "individual",
        "values": values,
        "center": center,
        "ucl": center + 3 * sigma,
        "lcl": center - 3 * sigma,
    }
    secondary = {
        "label": "moving_range",
        "values": moving_ranges,
        "center": mr_bar,
        "ucl": D4[2] * mr_bar,
        "lcl": D3[2] * mr_bar,
    }
    return primary, secondary


def _xbar_r_limits(series, size):
    if size not in A2:
        raise MsaMethodNotApplicable(
            "constants_out_of_range",
            "子組大小超出受控管制圖常數表，不得外插",
            details={"subgroup_size": size, "supported": sorted(A2)},
        )
    means = [sum(item["readings"]) / size for item in series]
    ranges = [
        max(item["readings"]) - min(item["readings"]) for item in series
    ]
    center = sum(means) / len(means)
    r_bar = sum(ranges) / len(ranges)
    primary = {
        "label": "xbar",
        "values": means,
        "center": center,
        "ucl": center + A2[size] * r_bar,
        "lcl": center - A2[size] * r_bar,
    }
    secondary = {
        "label": "range",
        "values": ranges,
        "center": r_bar,
        "ucl": D4[size] * r_bar,
        "lcl": D3[size] * r_bar,
    }
    return primary, secondary


def _xbar_s_limits(series, size):
    means = [sum(item["readings"]) / size for item in series]
    sds = []
    for item in series:
        mean = sum(item["readings"]) / size
        sds.append(math.sqrt(
            sum((value - mean) ** 2 for value in item["readings"])
            / (size - 1)
        ))
    center = sum(means) / len(means)
    s_bar = sum(sds) / len(sds)
    c4 = _c4(size)
    sigma = s_bar / c4
    a3 = 3.0 / (c4 * math.sqrt(size))
    b3 = max(0.0, 1 - 3 * math.sqrt(1 - c4 ** 2) / c4)
    b4 = 1 + 3 * math.sqrt(1 - c4 ** 2) / c4
    primary = {
        "label": "xbar",
        "values": means,
        "center": center,
        "ucl": center + a3 * s_bar,
        "lcl": center - a3 * s_bar,
    }
    secondary = {
        "label": "sd",
        "values": sds,
        "center": s_bar,
        "ucl": b4 * s_bar,
        "lcl": b3 * s_bar,
        "sigma": sigma,
    }
    return primary, secondary


def _c4(size: int) -> float:
    """c4 無偏常數；以 Gamma 函式精確計算，不查近似表。"""
    return (
        math.sqrt(2.0 / (size - 1))
        * math.gamma(size / 2.0)
        / math.gamma((size - 1) / 2.0)
    )


# ----------------------------------------------------------------------
# 判異規則
# ----------------------------------------------------------------------


def _apply_rules(primary, enabled_rules):
    """套用 WECO 規則 1–4，逐點回報違反的規則。"""
    values = primary["values"]
    center = primary["center"]
    sigma = (primary["ucl"] - center) / 3.0 if primary["ucl"] > center else 0.0
    violations = []

    if 1 in enabled_rules:
        for index, value in enumerate(values):
            if value > primary["ucl"] or value < primary["lcl"]:
                violations.append(_violation(1, index, "點超出 3 倍標準差管制界限"))

    if sigma > 0 and 2 in enabled_rules:
        violations.extend(_zone_rule(
            values, center, sigma, window=3, needed=2, multiplier=2,
            rule=2, message="連續 3 點中有 2 點落在同側 2 倍標準差之外",
        ))
    if sigma > 0 and 3 in enabled_rules:
        violations.extend(_zone_rule(
            values, center, sigma, window=5, needed=4, multiplier=1,
            rule=3, message="連續 5 點中有 4 點落在同側 1 倍標準差之外",
        ))
    if 4 in enabled_rules:
        violations.extend(_run_rule(values, center))

    violations.sort(key=lambda item: (item["index"], item["rule"]))
    return violations


def _violation(rule: int, index: int, message: str) -> dict:
    return {"rule": rule, "index": index, "message": message}


def _zone_rule(values, center, sigma, *, window, needed, multiplier, rule,
               message):
    found = []
    for start in range(0, len(values) - window + 1):
        chunk = values[start:start + window]
        for sign in (1, -1):
            boundary = center + sign * multiplier * sigma
            hits = sum(
                1 for value in chunk
                if (value > boundary if sign > 0 else value < boundary)
            )
            if hits >= needed:
                found.append(_violation(rule, start + window - 1, message))
                break
    return found


def _run_rule(values, center):
    """規則 4：連續 8 點落在中心線同一側。"""
    found = []
    streak = 0
    last_sign = 0
    for index, value in enumerate(values):
        sign = 1 if value > center else (-1 if value < center else 0)
        if sign == 0:
            streak, last_sign = 0, 0
            continue
        streak = streak + 1 if sign == last_sign else 1
        last_sign = sign
        if streak >= 8:
            found.append(_violation(4, index, "連續 8 點落在中心線同一側"))
    return found


def _limit_violations(secondary, label):
    return [
        {
            "rule": 1,
            "index": index,
            "chart": label,
            "message": f"{label} 圖第 {index + 1} 點超出管制界限",
        }
        for index, value in enumerate(secondary["values"])
        if value > secondary["ucl"] or value < secondary["lcl"]
    ]


def _missing_intervals(series):
    """以中位間隔為基準，找出明顯遺漏量測的期間。"""
    parsed = []
    for item in series:
        moment = _parse_date(item["measured_on"])
        if moment is None:
            return []
        parsed.append(moment)
    if len(parsed) < 3:
        return []

    gaps = [
        (parsed[index] - parsed[index - 1]).days
        for index in range(1, len(parsed))
    ]
    ordered = sorted(gaps)
    median = ordered[len(ordered) // 2]
    if median <= 0:
        return []
    return [
        {
            "from": series[index]["measured_on"],
            "to": series[index + 1]["measured_on"],
            "days": gap,
            "expected_days": median,
        }
        for index, gap in enumerate(gaps) if gap > median * 2
    ]


def _parse_date(value):
    try:
        parsed = datetime.fromisoformat(str(value))
    except ValueError:
        return None
    return parsed.date() if isinstance(parsed, datetime) else parsed


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
