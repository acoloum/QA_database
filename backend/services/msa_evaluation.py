"""以凍結準則快照對統計結果做三層判定。

三層刻意分開：
1. statistical_result — 客觀數字，永遠不因人工意見改變。
2. system_disposition — 系統依準則得到的處置建議。
3. engineering_judgment — 人工工程判斷，只能由後續決策附加，
   絕不回頭改寫前兩層。
"""

# 百分比口徑對應統計輸出的欄位
_PERCENT_FIELDS = {
    "tolerance": "percent_tolerance",
    "study_variation": "percent_study_variation",
    "process_variation": "percent_process",
}

ACCEPTABLE = "acceptable"
CONDITIONAL = "conditionally_acceptable"
UNACCEPTABLE = "unacceptable"
INDETERMINATE = "indeterminate"

_GRR_METHODS = {
    "MSA4_GRR_RANGE_1_0",
    "MSA4_GRR_XBAR_R_1_0",
    "MSA4_GRR_ANOVA_1_0",
}


def evaluate(method_code: str, statistics: dict, criteria_snapshot: dict):
    """回傳 (conclusion, blockers)；blockers 代表無法據以放行的原因。"""
    thresholds = dict((criteria_snapshot or {}).get("thresholds") or {})
    basis = (criteria_snapshot or {}).get("percent_basis") or "study_variation"

    if method_code in _GRR_METHODS:
        return _evaluate_grr(statistics, thresholds, basis)
    if method_code == "MSA4_NONREPEATABLE_1_0":
        return _evaluate_nonrepeatable(statistics, thresholds, basis)
    if method_code == "MSA4_BIAS_1_0":
        return _evaluate_bias(statistics)
    if method_code == "MSA4_LINEARITY_1_0":
        return _evaluate_linearity(statistics)
    if method_code == "MSA4_STABILITY_1_0":
        return _evaluate_stability(statistics)
    if method_code == "MSA4_ATTRIBUTE_1_0":
        return _evaluate_attribute(statistics, thresholds)
    return _conclusion(
        INDETERMINATE,
        {"method_code": method_code},
        ["方法沒有對應的判定規則"],
    ), [{
        "code": "MSA_EVALUATION_RULE_MISSING",
        "message": "方法沒有對應的判定規則，無法產生系統處置",
    }]


def _conclusion(disposition, statistical_result, reasons, *, basis=None):
    return {
        "statistical_result": statistical_result,
        "system_disposition": disposition,
        "engineering_judgment": None,
        "reasons": reasons,
        "percent_basis": basis,
    }


def _percent_value(statistics: dict, basis: str, key: str):
    field = _PERCENT_FIELDS.get(basis)
    section = statistics.get(field) if field else None
    if not isinstance(section, dict):
        return None
    return section.get(key)


def _evaluate_grr(statistics, thresholds, basis):
    percent = _percent_value(statistics, basis, "grr")
    ndc = statistics.get("ndc")
    accept_max = thresholds.get("grr_accept_max")
    conditional_max = thresholds.get("grr_conditional_max")
    ndc_min = thresholds.get("ndc_min")

    statistical_result = {
        "percent_grr": percent,
        "percent_basis": basis,
        "ndc": ndc,
        "grr_sigma": statistics.get("grr"),
    }
    blockers = []
    reasons = []

    if percent is None:
        blockers.append({
            "code": "MSA_PERCENT_BASIS_UNAVAILABLE",
            "message": (
                f"計畫選定的百分比口徑（{basis}）沒有可用數值，無法判定"
            ),
        })
        return _conclusion(
            INDETERMINATE, statistical_result,
            ["選定口徑無可用百分比"], basis=basis,
        ), blockers
    if accept_max is None or conditional_max is None:
        blockers.append({
            "code": "MSA_CRITERIA_THRESHOLD_MISSING",
            "message": "準則快照缺少 GRR 門檻，無法判定",
        })
        return _conclusion(
            INDETERMINATE, statistical_result,
            ["準則缺少 GRR 門檻"], basis=basis,
        ), blockers

    ndc_ok = True
    if ndc_min is not None:
        if ndc is None:
            ndc_ok = False
            reasons.append("無法計算 ndc，不得直接視為合格")
        elif ndc < ndc_min:
            ndc_ok = False
            reasons.append(f"ndc {ndc} 低於準則要求的 {ndc_min}")

    if percent > conditional_max:
        reasons.insert(0, f"%GRR {percent:.4f} 超過上限 {conditional_max}")
        disposition = UNACCEPTABLE
    elif percent < accept_max and ndc_ok:
        reasons.insert(0, f"%GRR {percent:.4f} 低於允收上限 {accept_max}")
        disposition = ACCEPTABLE
    else:
        reasons.insert(
            0, f"%GRR {percent:.4f} 落在條件接受區間或 ndc 不足"
        )
        disposition = CONDITIONAL

    return _conclusion(
        disposition, statistical_result, reasons, basis=basis,
    ), blockers


def _evaluate_nonrepeatable(statistics, thresholds, basis):
    percent = _percent_value(statistics, basis, "repeatability")
    accept_max = thresholds.get("grr_accept_max")
    conditional_max = thresholds.get("grr_conditional_max")
    statistical_result = {
        "percent_repeatability": percent,
        "percent_basis": basis,
        "design_type": statistics.get("design_type"),
        "unidentifiable_sources": statistics.get("unidentifiable_sources"),
    }
    if percent is None or accept_max is None or conditional_max is None:
        return _conclusion(
            INDETERMINATE, statistical_result,
            ["缺少可用百分比或門檻"], basis=basis,
        ), [{
            "code": "MSA_PERCENT_BASIS_UNAVAILABLE",
            "message": "不可重複研究缺少可用百分比或準則門檻",
        }]

    if percent > conditional_max:
        disposition, reason = UNACCEPTABLE, "重複性超過上限"
    elif percent < accept_max:
        disposition, reason = ACCEPTABLE, "重複性低於允收上限"
    else:
        disposition, reason = CONDITIONAL, "重複性落在條件接受區間"
    return _conclusion(
        disposition,
        statistical_result,
        [
            f"{reason}（{percent:.4f}%）",
            "本設計無法分離再現性與零件變差，結論僅涵蓋可辨識來源",
        ],
        basis=basis,
    ), []


def _evaluate_bias(statistics):
    significant = statistics.get("significant")
    statistical_result = {
        "bias": statistics.get("bias"),
        "p_value": statistics.get("p_value"),
        "confidence_interval": statistics.get("confidence_interval"),
    }
    if significant is None:
        return _conclusion(
            INDETERMINATE, statistical_result, ["無法判定偏倚顯著性"],
        ), [{
            "code": "MSA_BIAS_UNDETERMINED",
            "message": "偏倚顯著性無法判定",
        }]
    if significant:
        return _conclusion(
            UNACCEPTABLE, statistical_result,
            ["偏倚信賴區間不包含 0，存在顯著偏倚"],
        ), []
    return _conclusion(
        ACCEPTABLE, statistical_result,
        ["偏倚信賴區間包含 0，未觀察到顯著偏倚"],
    ), []


def _evaluate_linearity(statistics):
    evidence = statistics.get("linearity_evidence") or {}
    statistical_result = {
        "slope": (statistics.get("regression") or {}).get("slope"),
        "slope_p_value": (
            (statistics.get("regression") or {}).get("slope_p_value")
        ),
        "levels_excluding_zero": evidence.get("levels_excluding_zero"),
    }
    if evidence.get("acceptable"):
        return _conclusion(
            ACCEPTABLE, statistical_result,
            ["斜率與截距未達顯著，且各量程偏倚區間皆包含 0"],
        ), []
    reasons = []
    if evidence.get("slope_significant"):
        reasons.append("斜率顯著不為 0，偏倚隨量程改變")
    if evidence.get("intercept_significant"):
        reasons.append("截距顯著不為 0，存在整體偏倚")
    if evidence.get("levels_excluding_zero"):
        reasons.append(
            f"{evidence['levels_excluding_zero']} 個量程的偏倚區間不含 0"
        )
    return _conclusion(UNACCEPTABLE, statistical_result, reasons), []


def _evaluate_stability(statistics):
    stable = statistics.get("stable")
    violations = statistics.get("rule_violations") or []
    statistical_result = {
        "chart_type": statistics.get("chart_type"),
        "stable": stable,
        "violation_count": len(violations),
    }
    if stable:
        return _conclusion(
            ACCEPTABLE, statistical_result, ["基準期間沒有判異訊號"],
        ), []
    return _conclusion(
        UNACCEPTABLE, statistical_result,
        [f"基準期間出現 {len(violations)} 次判異訊號"],
    ), []


def _evaluate_attribute(statistics, thresholds):
    if not statistics.get("accuracy_available"):
        return _conclusion(
            INDETERMINATE,
            {"accuracy_available": False},
            ["缺少可信參考標準，只能報告一致性，不得判定正確性"],
        ), [{
            "code": "MSA_ATTRIBUTE_REFERENCE_UNAVAILABLE",
            "message": "沒有可信參考標準，無法判定計數型量測系統是否可接受",
        }]

    overall = (statistics.get("against_reference") or {}).get("overall") or {}
    kappa = overall.get("kappa")
    effectiveness = statistics.get("effectiveness")
    false_accept = statistics.get("false_accept_rate")
    false_reject = statistics.get("false_reject_rate")
    statistical_result = {
        "kappa": kappa,
        "effectiveness": effectiveness,
        "false_accept_rate": false_accept,
        "false_reject_rate": false_reject,
    }

    failures = []
    if thresholds.get("kappa_min") is not None:
        if kappa is None:
            failures.append("無法估計 Kappa")
        elif kappa < thresholds["kappa_min"]:
            failures.append(
                f"Kappa {kappa:.4f} 低於要求 {thresholds['kappa_min']}"
            )
    if thresholds.get("effectiveness_min") is not None:
        if effectiveness is None:
            failures.append("無法計算有效性")
        elif effectiveness < thresholds["effectiveness_min"]:
            failures.append(
                f"有效性 {effectiveness:.2f}% 低於要求 "
                f"{thresholds['effectiveness_min']}%"
            )
    for label, value, key in (
        ("誤收率", false_accept, "false_accept_max"),
        ("誤拒率", false_reject, "false_reject_max"),
    ):
        limit = thresholds.get(key)
        if limit is None:
            continue
        if value is None:
            failures.append(f"無法估計{label}")
        elif value > limit:
            failures.append(f"{label} {value:.2f}% 超過上限 {limit}%")

    if not failures:
        return _conclusion(
            ACCEPTABLE, statistical_result, ["所有計數型指標皆符合準則"],
        ), []
    return _conclusion(UNACCEPTABLE, statistical_result, failures), []
