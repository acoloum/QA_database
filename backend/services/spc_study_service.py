"""SPC 不可變研究版本與正式基準的生命週期服務。"""

from dataclasses import asdict, replace
from datetime import date, datetime, timedelta, timezone
from html import escape
import hashlib
import inspect
import json
import os
from typing import Any, Callable, Mapping

import numpy as np
from sqlalchemy import func, update
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from ..extensions import db
from ..models import (
    Role,
    SpcEvent,
    SpcLimitVersion,
    SPCCache,
    SpcStudy,
    SpcStudySample,
    SpcStudyVersion,
    User,
    utc_now,
)
from ..utils import log_audit
from .spc_adapters.patrol import build_patrol_study_input
from .spc_adapters.shipping import build_shipping_study_input
from .spc_adapters.attribute import build_attribute_study_input
from .spc_analysis_service import calculate_process_capability
from .spc_machine_performance import calculate_machine_performance
from .spc_chart_engine import (
    SpcChartNotApplicable,
    calculate_chart_observations,
    calculate_chart_set,
)
from .spc_contracts import (
    AnalysisFamily,
    SpcChartSeries,
    SpcChartSet,
    SpcStudyInput,
    SpcSubgroup,
)
from .spc_attribute_engine import (
    calculate_attribute_chart,
    calculate_attribute_observations,
)
from .spc_adapters.common import SPC_INPUT_CONTRACT_VERSION
from .spc_attribute_options import (
    ATTRIBUTE_OPTION_DEFAULTS,
    canonical_attribute_options,
)
from .spc_distribution import assess_distribution
from .spc_errors import (
    SpcConflict,
    SpcForbidden,
    SpcNotFound,
    SpcValidationError,
)
from .spc_stability import evaluate_attribute_stability, evaluate_study_stability
from .spc_time_model import classify_time_model


SPC_METHOD_VERSION = "2026.2"
SPC_CODE_VERSION = os.environ.get("SPC_CODE_VERSION", "2026.1")
ANALYSIS_FAMILIES = {"variable", "attribute", "machine"}
ADAPTERS: dict[str, Callable[[Mapping[str, Any]], SpcStudyInput]] = {
    "shipping": build_shipping_study_input,
    "patrol": build_patrol_study_input,
}
ATTRIBUTE_ADAPTERS: dict[str, Callable[..., SpcStudyInput]] = {
    "shipping": build_attribute_study_input,
    "patrol": build_attribute_study_input,
}

MACHINE_REQUIRED_FILTERS = ("m_id", "mat", "spec", "item", "pos")
MACHINE_OPTION_KEYS = {"conditions_confirmed", "condition_reason"}


def _canonical_machine_filters(
    source: str, filters: Mapping[str, Any]
) -> dict[str, Any]:
    """驗證機器研究的固定製程流，拒絕全段與多值篩選。"""

    if source != "patrol":
        raise SpcValidationError("MACHINE_SOURCE_UNSUPPORTED", "機器績效研究只接受巡檢資料")
    if not isinstance(filters, Mapping):
        raise SpcValidationError("MACHINE_STREAM_NOT_FIXED", "機器研究篩選條件必須是物件")
    canonical = dict(filters)
    for name in MACHINE_REQUIRED_FILTERS:
        value = canonical.get(name)
        if isinstance(value, (list, tuple, set, dict)):
            raise SpcValidationError("MACHINE_STREAM_NOT_FIXED", f"機器研究的 {name} 必須是單一值")
        if name == "m_id":
            if isinstance(value, bool):
                raise SpcValidationError("MACHINE_STREAM_NOT_FIXED", "機器研究必須指定單一機台")
            try:
                parsed = int(value)
            except (TypeError, ValueError):
                raise SpcValidationError("MACHINE_STREAM_NOT_FIXED", "機器研究必須指定單一機台") from None
            if parsed <= 0 or str(value).strip() != str(parsed):
                raise SpcValidationError("MACHINE_STREAM_NOT_FIXED", "機器研究必須指定單一機台")
            canonical[name] = parsed
            continue
        text = str(value or "").strip()
        if not text or text in {"全部", "全段"} or any(token in text for token in (",", "|", ";")):
            raise SpcValidationError("MACHINE_STREAM_NOT_FIXED", f"機器研究的 {name} 必須是單一且精確的值")
        canonical[name] = text
    return canonical


def _canonical_machine_options(options: Mapping[str, Any] | None) -> dict[str, Any]:
    """固定保存研究條件證據，避免未知欄位或真值轉型改變雜湊。"""

    if not isinstance(options, Mapping) or set(options) != MACHINE_OPTION_KEYS:
        raise SpcValidationError("SPC_ANALYSIS_OPTIONS_INVALID", "機器研究僅接受受控條件確認與理由")
    confirmed = options.get("conditions_confirmed")
    if type(confirmed) is not bool:
        raise SpcValidationError("SPC_ANALYSIS_OPTIONS_INVALID", "conditions_confirmed 必須是布林值")
    reason = options.get("condition_reason")
    if not isinstance(reason, str):
        raise SpcValidationError("SPC_ANALYSIS_OPTIONS_INVALID", "condition_reason 必須是文字")
    reason = escape(reason.strip(), quote=False)
    if not 2 <= len(reason) <= 500:
        raise SpcValidationError("SPC_ANALYSIS_OPTIONS_INVALID", "condition_reason 長度或內容不符合規範")
    return {"conditions_confirmed": confirmed, "condition_reason": reason}
def _canonical_attribute_options(options: Mapping[str, Any] | None) -> dict[str, Any]:
    """相容既有 service 私有入口；實作由 adapter 共用模組提供。"""

    return canonical_attribute_options(options)


def _upsert_preview_cache(
    cache_key: str, result: Mapping[str, Any], expires_at: datetime
) -> None:
    """以資料庫原子 upsert 保存預覽，避免相同 cache key 競態。"""

    table = SPCCache.__table__
    values = {
        "快取鍵": cache_key,
        "計算結果": dict(result),
        "過期時間": expires_at,
    }
    dialect_name = db.session.get_bind().dialect.name
    insert_factory = (
        postgresql_insert if dialect_name == "postgresql" else sqlite_insert
    )
    statement = insert_factory(table).values(values).on_conflict_do_update(
        index_elements=[table.c["快取鍵"]],
        set_={
            "計算結果": dict(result),
            "過期時間": expires_at,
        },
    )
    db.session.execute(statement)


def _require_reason(reason: str | None) -> str:
    normalized = (reason or "").strip()
    if not normalized:
        raise SpcValidationError("REASON_REQUIRED", "狀態轉換必須填寫理由")
    return normalized


def _require_permission(actor_id: int, permission: str) -> User:
    actor = db.session.get(User, actor_id)
    if actor is None or not actor.is_active:
        raise SpcForbidden("SPC_ACTOR_FORBIDDEN", "使用者不存在或已停用")
    if actor.role == "admin":
        return actor
    role = Role.query.filter_by(code=actor.role).first()
    allowed = bool(role and role.has_permission(permission))
    if role is not None and permission == "spc.view":
        allowed = allowed or role.has_permission("spc.manage") or role.has_permission("spc.approve")
    if not allowed:
        code = "SPC_APPROVE_FORBIDDEN" if permission == "spc.approve" else "SPC_MANAGE_FORBIDDEN"
        raise SpcForbidden(code, "權限不足")
    return actor


def _get_version(version_id: int) -> SpcStudyVersion:
    version = db.session.get(SpcStudyVersion, version_id)
    if version is None:
        raise SpcNotFound("SPC_STUDY_VERSION_NOT_FOUND", "找不到 SPC 研究版本")
    return version


def _resolve_monitoring_limit(version: SpcStudyVersion) -> SpcLimitVersion | None:
    """依 immutable monitoring reference 取得並驗證歷史界限，不依目前 active 狀態猜測。"""

    limit_id = (version.time_model_result or {}).get("limit_version_id")
    if not limit_id:
        return None
    limit = (
        SpcLimitVersion.query.options(
            selectinload(SpcLimitVersion.events),
            selectinload(SpcLimitVersion.study_version).selectinload(SpcStudyVersion.study),
        ).filter_by(id=limit_id).first()
    )
    if limit is None:
        raise SpcValidationError("SPC_MONITORING_LIMIT_NOT_FOUND", "監控版本引用的界限不存在")
    _validate_monitoring_limit_ownership(version, limit)
    return limit


def _validate_monitoring_limit_ownership(
    version: SpcStudyVersion, limit: SpcLimitVersion
) -> None:
    """驗證已 eager load 的 immutable monitoring limit ownership，不進行查詢。"""

    baseline_study = limit.study_version.study
    current_study = version.study
    if (
        limit.analysis_family != current_study.analysis_family
        or limit.process_stream_key != current_study.process_stream_key
        or limit.characteristic != current_study.characteristic
        or baseline_study.source != current_study.source
        or baseline_study.analysis_family != current_study.analysis_family
    ):
        raise SpcValidationError("SPC_MONITORING_LIMIT_MISMATCH", "監控界限與研究版本的不可變範圍不一致")


def _adapter_input(
    source: str,
    filters: Mapping[str, Any],
    *,
    analysis_family: AnalysisFamily = "variable",
    options: Mapping[str, Any] | None = None,
    input_contract_version: str = SPC_INPUT_CONTRACT_VERSION,
) -> SpcStudyInput:
    if analysis_family == "attribute":
        canonical_options = _canonical_attribute_options(options)
        adapter = ATTRIBUTE_ADAPTERS.get(source)
        if adapter is None:
            raise SpcValidationError("SPC_SOURCE_UNSUPPORTED", f"不支援的 SPC 資料來源：{source}")
        study_input = adapter(
            source, filters, options=canonical_options,
            input_contract_version=input_contract_version,
        )
        return replace(
            study_input, analysis_family="attribute", options=canonical_options,
        )
    adapter = ADAPTERS.get(source)
    if adapter is None:
        raise SpcValidationError("SPC_SOURCE_UNSUPPORTED", f"不支援的 SPC 資料來源：{source}")
    parameters = inspect.signature(adapter).parameters.values()
    supports_context = any(
        parameter.kind == parameter.VAR_KEYWORD
        for parameter in parameters
    ) or {"analysis_family", "options", "input_contract_version"}.issubset(
        inspect.signature(adapter).parameters
    )
    study_input = (
        adapter(
            filters,
            analysis_family=analysis_family,
            options=dict(options or {}),
            input_contract_version=input_contract_version,
        )
        if supports_context else adapter(filters)
    )
    return replace(
        study_input,
        analysis_family=analysis_family,
        options=dict(options or {}),
    )


def _chart_result(chart_set: SpcChartSet) -> dict[str, Any]:
    def plain(value):
        if isinstance(value, dict):
            return {key: plain(item) for key, item in value.items()}
        if isinstance(value, (list, tuple)):
            return [plain(item) for item in value]
        return value

    return plain(asdict(chart_set))


def _calculate_results(study_input: SpcStudyInput) -> dict[str, Any]:
    if study_input.analysis_family == "attribute":
        return _calculate_attribute_results(study_input)
    if study_input.analysis_family == "machine":
        return _calculate_machine_results(study_input)
    all_values = [
        value
        for subgroup in study_input.subgroups
        for value in (subgroup.distribution_values or subgroup.values)
    ]
    distribution = assess_distribution(all_values, field=study_input.characteristic)
    try:
        chart_set = calculate_chart_set(study_input.subgroups)
    except SpcChartNotApplicable as exc:
        return {
            "chart_result": None,
            "stability_result": {
                "evaluated": False, "stable": None,
                "location": {"stable": None, "violations": []},
                "variation": {"stable": None, "violations": []},
                "violations": [], "reason_code": exc.code,
            },
            "distribution_result": distribution,
            "time_model_result": {
                "candidate": None, "confirmed": False,
                "statistically_controlled": False, "reason_code": exc.code,
            },
            "capability_result": {
                "available": False, "reason": "chart_not_applicable",
                "capability_reason": exc.code,
            },
            "applicability_result": {
                "applicable": False, "reason_code": exc.code, "message": str(exc),
            },
        }

    stability = evaluate_study_stability(chart_set)
    time_model = classify_time_model(chart_set, stability, distribution)
    location_values = [float(value) for value in chart_set.location.values if value is not None]
    variation_center = float(np.mean(chart_set.variation.cl))
    capability = calculate_process_capability(
        avgs=location_values,
        all_values=all_values,
        r_cl=variation_center,
        d2=variation_center / chart_set.sigma_within,
        tolerance_limits=dict(study_input.specification),
        stability=stability,
        field=study_input.characteristic,
        dist=distribution,
        time_model=time_model,
        characteristic_class=str(
            study_input.specification.get("characteristic_class") or "其他"
        ),
    )
    return {
        "chart_result": _chart_result(chart_set),
        "stability_result": stability,
        "distribution_result": distribution,
        "time_model_result": time_model,
        "capability_result": capability,
        "applicability_result": {
            "applicable": True, "reason_code": None,
            "chart_type": chart_set.chart_type,
        },
    }


def _calculate_machine_results(study_input: SpcStudyInput) -> dict[str, Any]:
    """機器研究不產生管制圖、持續監控或 OCAP，只保存績效證據。"""

    all_values = [
        float(value)
        for subgroup in study_input.subgroups
        for value in (subgroup.distribution_values or subgroup.values)
    ]
    distribution = assess_distribution(all_values, field=study_input.characteristic)
    capability = calculate_machine_performance(
        all_values, dict(study_input.specification), distribution,
        str(study_input.specification.get("characteristic_class") or "其他"),
    )
    if study_input.options.get("conditions_confirmed") is not True:
        capability.update({
            "available": False,
            "approvable": False,
            "reason_code": "MACHINE_CONDITIONS_UNCONFIRMED",
        })
    if study_input.metadata.get("source_semantics") != "patrol_min_max_observations":
        capability.update({
            "approvable": False,
            "reason_code": "SOURCE_SEMANTICS_UNAUDITABLE",
        })
    capability["evidence"] = {
        "source_semantics": study_input.metadata.get("source_semantics"),
        "operators": list(study_input.metadata.get("operators") or []),
        "record_ids": list(study_input.metadata.get("record_ids") or []),
        "detail_ids": list(study_input.metadata.get("detail_ids") or []),
        "date_span": dict(study_input.metadata.get("date_span") or {}),
        "conditions_confirmed": study_input.options.get("conditions_confirmed") is True,
        "condition_reason": study_input.options.get("condition_reason"),
    }
    return {
        "chart_result": None,
        "stability_result": {
            "evaluated": False, "stable": None, "reason_code": "MACHINE_PERFORMANCE_RESEARCH",
        },
        "distribution_result": distribution,
        "time_model_result": {
            "candidate": None, "confirmed": False, "reason_code": "MACHINE_PERFORMANCE_RESEARCH",
        },
        "capability_result": capability,
        "applicability_result": {
            "applicable": True, "reason_code": None, "research_only": True,
        },
    }


def _attribute_not_applicable(study_input: SpcStudyInput, exc: SpcChartNotApplicable) -> dict[str, Any]:
    return {
        "chart_result": None,
        "stability_result": {
            "evaluated": False, "stable": None, "violations": [],
            "rules_used": [], "residual_method": "binomial_pearson",
            "reason_code": exc.code,
        },
        "distribution_result": {"available": False, "reason": "attribute_chart"},
        "time_model_result": {"candidate": None, "confirmed": False,
                              "statistically_controlled": False, "reason_code": exc.code},
        "capability_result": {"available": False, "reason": "attribute_chart"},
        "applicability_result": {"applicable": False, "reason_code": exc.code,
                                  "message": str(exc)},
    }


def _calculate_attribute_results(study_input: SpcStudyInput) -> dict[str, Any]:
    """建立屬性基準研究；完整保存精確界限與分類證據。"""

    requested_chart = str(study_input.options["chart_type"])
    alpha = float(study_input.options["alpha"])
    try:
        chart = calculate_attribute_chart(
            tuple(study_input.subgroups), requested_chart, alpha=alpha
        )
    except SpcChartNotApplicable as exc:
        return _attribute_not_applicable(study_input, exc)
    chart["exact_alpha"] = alpha
    chart["interval"] = study_input.options.get("interval") or "day"
    chart["warnings"] = {
        "sample_size_variation": chart.get("sample_size_variation_warning", False),
        "classification_excluded_records": int(
            study_input.metadata.get("excluded_record_count", 0)
        ),
    }
    chart["eligibility_evidence"] = list(
        study_input.metadata.get("classification_evidence", [])
    )
    chart["exclusion_evidence"] = list(
        study_input.metadata.get("classification_snapshot", [])
    )
    stability = evaluate_attribute_stability(chart)
    return {
        "chart_result": chart,
        "stability_result": stability,
        "distribution_result": {"available": False, "reason": "attribute_chart"},
        "time_model_result": {
            "candidate": None, "confirmed": False,
            "statistically_controlled": stability.get("stable"),
            "reason_code": "ATTRIBUTE_BASELINE",
        },
        "capability_result": {"available": False, "reason": "attribute_chart"},
        "applicability_result": {
            "applicable": True, "reason_code": None, "chart_type": requested_chart,
            "eligibility": dict(study_input.metadata),
        },
    }


def _approved_series_limits(
    saved: Mapping[str, Any],
    baseline_sizes: list[int],
    current_sizes: tuple[int, ...],
    *,
    series_name: str,
) -> tuple[tuple[float, ...], tuple[float, ...], tuple[float, ...]]:
    """依核准時的實際子組大小，映射持續監控每一點的固定界限。"""

    series = saved.get(series_name) or {}
    arrays = {
        name: [float(value) for value in (series.get(name) or [])]
        for name in ("cl", "ucl", "lcl")
    }
    if not baseline_sizes or any(len(values) != len(baseline_sizes) for values in arrays.values()):
        raise SpcValidationError(
            "SPC_APPROVED_LIMITS_INVALID", "核准界限缺少完整逐點子組大小或界限"
        )
    by_size: dict[int, dict[str, float]] = {}
    for index, subgroup_size in enumerate(baseline_sizes):
        candidate = {name: values[index] for name, values in arrays.items()}
        existing = by_size.setdefault(int(subgroup_size), candidate)
        if any(abs(existing[name] - candidate[name]) > 1e-12 for name in arrays):
            raise SpcValidationError(
                "SPC_APPROVED_LIMITS_INCONSISTENT",
                "相同子組大小保存了不一致的核准界限",
            )
    missing = sorted(set(current_sizes) - set(by_size))
    if missing:
        raise SpcValidationError(
            "SPC_SUBGROUP_SIZE_NOT_APPROVED",
            "目前資料包含核准基準未涵蓋的子組大小",
            details={"subgroup_sizes": missing},
        )
    return tuple(
        tuple(by_size[size][name] for size in current_sizes)
        for name in ("cl", "ucl", "lcl")
    )


def _calculate_ongoing_results(
    study_input: SpcStudyInput, active_limit: SpcLimitVersion
) -> dict[str, Any]:
    """只以已核准界限評估目前觀測值，不重新置中或建立新界限。"""

    if study_input.analysis_family == "attribute":
        return _calculate_attribute_ongoing_results(study_input, active_limit)

    try:
        current = calculate_chart_observations(
            study_input.subgroups, active_limit.chart_type
        )
    except SpcChartNotApplicable as exc:
        raise SpcValidationError(exc.code, str(exc)) from exc
    if current.chart_type != active_limit.chart_type:
        raise SpcValidationError(
            "SPC_CHART_TYPE_MISMATCH",
            "目前子組結構與核准界限的管制圖類型不一致",
            details={"approved": active_limit.chart_type, "current": current.chart_type},
        )
    saved_limits = dict(active_limit.limits or {})
    baseline_sizes = [int(value) for value in (saved_limits.get("subgroup_sizes") or [])]
    x_cl, x_ucl, x_lcl = _approved_series_limits(
        saved_limits, baseline_sizes, current.subgroup_sizes, series_name="location"
    )
    r_cl, r_ucl, r_lcl = _approved_series_limits(
        saved_limits, baseline_sizes, current.subgroup_sizes, series_name="variation"
    )
    monitored = SpcChartSet(
        chart_type=current.chart_type,
        location=SpcChartSeries(
            statistic=current.location.statistic,
            values=current.location.values,
            cl=x_cl,
            ucl=x_ucl,
            lcl=x_lcl,
        ),
        variation=SpcChartSeries(
            statistic=current.variation.statistic,
            values=current.variation.values,
            cl=r_cl,
            ucl=r_ucl,
            lcl=r_lcl,
        ),
        subgroup_sizes=current.subgroup_sizes,
        sigma_within=float(
            (active_limit.study_version.chart_result or {}).get("sigma_within")
            or current.sigma_within
        ),
        variation_source_pairs=current.variation_source_pairs,
    )
    approved_stability = dict(active_limit.study_version.stability_result or {})
    approved_rules = approved_stability.get("rules_used")
    if not isinstance(approved_rules, list) or not approved_rules:
        raise SpcValidationError(
            "SPC_APPROVED_RULES_MISSING",
            "核准版本缺少正式失控規則集，不能執行持續監控",
        )
    stability = evaluate_study_stability(monitored, enabled_rules=approved_rules)
    all_values = [
        value
        for subgroup in study_input.subgroups
        for value in (subgroup.distribution_values or subgroup.values)
    ]
    return {
        "chart_result": _chart_result(monitored),
        "stability_result": stability,
        "distribution_result": assess_distribution(
            all_values, field=study_input.characteristic
        ),
        "time_model_result": {
            "candidate": None,
            "confirmed": False,
            "statistically_controlled": stability.get("stable") is True,
            "reason_code": "ONGOING_USES_APPROVED_LIMITS",
            "limit_version_id": active_limit.id,
        },
        "capability_result": {
            "available": False,
            "reason": "ongoing_monitoring",
            "capability_reason": "ONGOING_REQUIRES_SEPARATE_CAPABILITY_STUDY",
        },
        "applicability_result": {
            "applicable": True,
            "reason_code": None,
            "chart_type": monitored.chart_type,
            "active_limit_version_id": active_limit.id,
        },
    }


def _calculate_attribute_ongoing_results(
    study_input: SpcStudyInput, active_limit: SpcLimitVersion
) -> dict[str, Any]:
    """套用核准屬性基準的中心、alpha 與規則，不以近期資料重新置中。"""

    saved = dict(active_limit.limits or {})
    if active_limit.chart_type not in {"p", "np"}:
        raise SpcValidationError("SPC_CHART_TYPE_MISMATCH", "核准界限不是屬性型 p／np 圖")
    try:
        center = float(saved["center"])
        alpha = float(saved["alpha"])
    except (KeyError, TypeError, ValueError) as exc:
        raise SpcValidationError("SPC_APPROVED_LIMITS_INVALID", "核准屬性界限缺少 center 或 alpha") from exc
    requested = str(study_input.options.get("chart_type") or active_limit.chart_type).lower()
    if requested != active_limit.chart_type:
        raise SpcValidationError("SPC_CHART_TYPE_MISMATCH", "目前圖表選型與核准界限不一致")
    frozen_options = _canonical_attribute_options(saved.get("options") or {
        "interval": saved.get("interval", "day"),
        "chart_type": active_limit.chart_type,
        "alpha": alpha,
    })
    if dict(study_input.options) != frozen_options:
        raise SpcValidationError(
            "SPC_ATTRIBUTE_OPTIONS_MISMATCH",
            "目前 attribute options 必須與核准界限的受控選項一致",
        )
    frozen_interval = frozen_options["interval"]
    try:
        chart = calculate_attribute_observations(
            tuple(study_input.subgroups), requested, center=center, alpha=alpha,
            baseline_n=(int(saved["baseline_n"]) if saved.get("baseline_n") is not None else None),
        )
    except SpcChartNotApplicable as exc:
        raise SpcValidationError(exc.code, str(exc)) from exc
    chart["exact_alpha"] = alpha
    chart["interval"] = frozen_interval
    chart["warnings"] = {
        "sample_size_variation": chart.get("sample_size_variation_warning", False),
        "classification_excluded_records": int(study_input.metadata.get("excluded_record_count", 0)),
    }
    chart["eligibility_evidence"] = list(
        study_input.metadata.get("classification_evidence", [])
    )
    chart["exclusion_evidence"] = list(
        study_input.metadata.get("classification_snapshot", [])
    )
    rules = saved.get("rules_used")
    if not isinstance(rules, list) or not rules:
        rules = (active_limit.study_version.stability_result or {}).get("rules_used")
    if not isinstance(rules, list) or not rules:
        raise SpcValidationError("SPC_APPROVED_RULES_MISSING", "核准版本缺少正式失控規則集")
    stability = evaluate_attribute_stability(chart, enabled_rules=rules)
    return {
        "chart_result": chart,
        "stability_result": stability,
        "distribution_result": {"available": False, "reason": "attribute_ongoing"},
        "time_model_result": {
            "candidate": None, "confirmed": False,
            "statistically_controlled": stability.get("stable"),
            "reason_code": "ONGOING_USES_APPROVED_LIMITS",
            "limit_version_id": active_limit.id,
        },
        "capability_result": {"available": False, "reason": "ongoing_monitoring"},
        "applicability_result": {
            "applicable": True, "reason_code": None, "chart_type": requested,
            "active_limit_version_id": active_limit.id,
        },
    }


def _timestamp_text(value: date | datetime | str | None) -> str | None:
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return str(value) if value is not None else None


def _assert_source_unchanged(version: SpcStudyVersion) -> SpcStudyInput:
    current = _adapter_input(
        version.study.source,
        version.study.filters,
        analysis_family=version.study.analysis_family,
        options=version.analysis_options or {},
        input_contract_version=(
            "2026.1" if version.method_version == "2026.1"
            else SPC_INPUT_CONTRACT_VERSION
        ),
    )
    if current.data_hash != version.data_hash:
        raise SpcConflict(
            "STUDY_DATA_CHANGED",
            "來源資料、規格或排除狀態已變更，請重新分析後再送審",
            details={"saved_hash": version.data_hash, "current_hash": current.data_hash},
        )
    return current


def _assert_approvable(version: SpcStudyVersion) -> None:
    if version.audit_incomplete:
        raise SpcValidationError("AUDIT_INCOMPLETE", "稽核資料不完整，必須重新建立研究")
    if not (version.applicability_result or {}).get("applicable"):
        raise SpcValidationError("CHART_NOT_APPLICABLE", "目前資料不適用支援的管制圖")
    if version.study.analysis_family == "attribute":
        if (version.stability_result or {}).get("stable") is not True:
            raise SpcValidationError("PROCESS_UNSTABLE", "屬性位置圖必須穩定")
        return
    time_model = version.time_model_result or {}
    model = time_model.get("model") or time_model.get("candidate")
    if not time_model.get("confirmed") or model not in {"A1", "A2"}:
        raise SpcValidationError("TIME_MODEL_UNCONFIRMED", "時間模型尚未確認為 A1 或 A2")
    stability = version.stability_result or {}
    if (
        (stability.get("location") or {}).get("stable") is not True
        or (stability.get("variation") or {}).get("stable") is not True
    ):
        raise SpcValidationError("PROCESS_UNSTABLE", "位置圖與變異圖必須同時穩定")


def _assert_research_approvable(version: SpcStudyVersion) -> None:
    """核准不會建立生產界限的研究結果。"""

    if version.audit_incomplete:
        raise SpcValidationError("AUDIT_INCOMPLETE", "稽核資料不完整，必須重新建立研究")
    if version.study.analysis_family != "machine":
        time_model = version.time_model_result or {}
        model = time_model.get("model") or time_model.get("candidate")
        if time_model.get("confirmed") is not True or model not in {
            "B", "C1", "C2", "C3", "C4", "D",
        }:
            raise SpcValidationError(
                "RESEARCH_APPROVAL_NOT_APPLICABLE", "此研究必須依生產基準流程核准"
            )
        return
    capability = version.capability_result or {}
    if (capability.get("evidence") or {}).get("source_semantics") != "patrol_min_max_observations":
        raise SpcValidationError(
            "SOURCE_SEMANTICS_UNAUDITABLE", "來源觀測語意未保存，不能核准機器研究"
        )
    if (version.analysis_options or {}).get("conditions_confirmed") is not True:
        raise SpcValidationError("MACHINE_CONDITIONS_UNCONFIRMED", "尚未確認機器研究條件")
    if len([value for sample in version.samples for value in (sample.distribution_values or sample.values or [])]) < 50:
        raise SpcValidationError("MACHINE_SAMPLE_INSUFFICIENT", "機器研究至少需要 50 個有效觀測值")
    if not (version.distribution_result or {}).get("accepted"):
        raise SpcValidationError("DISTRIBUTION_UNCONFIRMED", "分布尚未確認，不能核准機器研究")
    specification = version.specification_snapshot or {}
    if not specification.get("found") or specification.get("consistent") is False:
        raise SpcValidationError(
            specification.get("reason_code") or "SPECIFICATION_UNCONFIRMED",
            "規格未確認、衝突或已漂移，不能核准機器研究",
        )
    if not capability.get("available") or not capability.get("approvable"):
        raise SpcValidationError(
            capability.get("reason_code") or "MACHINE_RESEARCH_UNAPPROVABLE",
            "機器研究尚不符合核准資格",
        )


def _recalculate_capability(
    version: SpcStudyVersion, time_model: Mapping[str, Any]
) -> dict[str, Any]:
    """時間模型確認後，以不可變樣本與已保存分布重新計算能力指標。"""

    chart = version.chart_result or {}
    if not chart:
        return {
            "available": False, "reason": "chart_not_applicable",
            "capability_reason": "CHART_NOT_APPLICABLE",
        }
    all_values = [
        float(value)
        for sample in version.samples
        for value in (sample.distribution_values or sample.values or [])
    ]
    location_values = [
        float(value) for value in (chart.get("location") or {}).get("values", [])
        if value is not None
    ]
    variation_center_values = (chart.get("variation") or {}).get("cl", [])
    variation_center = float(np.mean(variation_center_values))
    sigma_within = float(chart.get("sigma_within") or 0)
    d2 = variation_center / sigma_within if sigma_within > 0 else 1.0
    return calculate_process_capability(
        avgs=location_values,
        all_values=all_values,
        r_cl=variation_center,
        d2=d2,
        tolerance_limits=dict(version.specification_snapshot or {}),
        stability=dict(version.stability_result or {}),
        field=version.study.characteristic,
        dist=dict(version.distribution_result or {}),
        time_model=dict(time_model),
        characteristic_class=str(
            (version.specification_snapshot or {}).get("characteristic_class") or "其他"
        ),
    )


def _add_input_samples(
    version: SpcStudyVersion, source: str, study_input: SpcStudyInput
) -> None:
    for index, subgroup in enumerate(study_input.subgroups):
        if study_input.analysis_family == "attribute":
            values = [float(subgroup.nonconforming), float(subgroup.inspected)]
            distribution_values = []
            measurement_ids = []
        else:
            values = list(subgroup.values)
            distribution_values = list(subgroup.distribution_values or subgroup.values)
            measurement_ids = list(subgroup.measurement_ids)
        db.session.add(SpcStudySample(
            version_id=version.id,
            source_record_type=(
                "ShippingMeasurement" if source == "shipping" else "PatrolDetail"
            ),
            source_record_id=subgroup.record_ids[0],
            source_measurement_id=measurement_ids[0] if measurement_ids else None,
            source_record_ids=list(subgroup.record_ids),
            source_measurement_ids=measurement_ids,
            sample_timestamp=_timestamp_text(subgroup.timestamp),
            subgroup_key=subgroup.key,
            subgroup_order=index,
            values=values,
            distribution_values=distribution_values,
            excluded=False,
            exclusion_snapshot=(
                [] if study_input.analysis_family == "attribute"
                else list(subgroup.exclusion_snapshot)
            ),
        ))


def _copy_saved_samples(
    source_version: SpcStudyVersion, target_version: SpcStudyVersion
) -> None:
    for sample in source_version.samples:
        db.session.add(SpcStudySample(
            version_id=target_version.id,
            source_record_type=sample.source_record_type,
            source_record_id=sample.source_record_id,
            source_measurement_id=sample.source_measurement_id,
            source_record_ids=list(sample.source_record_ids or []),
            source_measurement_ids=list(sample.source_measurement_ids or []),
            sample_timestamp=sample.sample_timestamp,
            subgroup_key=sample.subgroup_key,
            subgroup_order=sample.subgroup_order,
            values=list(sample.values or []),
            distribution_values=list(sample.distribution_values or []),
            excluded=sample.excluded,
            exclusion_reason=sample.exclusion_reason,
            exclusion_snapshot=list(sample.exclusion_snapshot or []),
        ))


class SpcStudyService:
    """SPC 研究與核准界限的應用服務。"""

    @staticmethod
    def analyze(
        source: str,
        filters: Mapping[str, Any],
        actor_id: int,
        study_type: str = "retrospective",
        analysis_family: str = "variable",
        options: Mapping[str, Any] | None = None,
    ) -> SpcStudyVersion:
        if not isinstance(analysis_family, str) or analysis_family not in ANALYSIS_FAMILIES:
            raise SpcValidationError(
                "SPC_ANALYSIS_FAMILY_INVALID",
                "分析族別僅支援 variable、attribute 或 machine",
            )
        if analysis_family == "machine":
            # 先只確認資料來源，再檢查管理權限，避免未授權者透過
            # 篩選條件或 options 的驗證訊息探測機器研究的請求契約。
            if source != "patrol":
                raise SpcValidationError(
                    "MACHINE_SOURCE_UNSUPPORTED", "機器績效研究只接受巡檢資料"
                )
            _require_permission(actor_id, "spc.manage")
            if study_type != "retrospective":
                raise SpcValidationError("MACHINE_STREAM_NOT_FIXED", "機器研究不支援持續監控")
            filters = _canonical_machine_filters(source, filters)
            canonical_options = _canonical_machine_options(options)
        else:
            if study_type not in {"retrospective", "ongoing"}:
                raise SpcValidationError("SPC_STUDY_TYPE_INVALID", "研究類型不受支援")
            if options is not None and not isinstance(options, Mapping):
                raise SpcValidationError(
                    "SPC_ANALYSIS_OPTIONS_INVALID", "分析選項必須是物件",
                )
            _require_permission(actor_id, "spc.view")
            canonical_options = (
                _canonical_attribute_options(options)
                if analysis_family == "attribute" else options
            )
        study_input = _adapter_input(
            source,
            filters,
            analysis_family=analysis_family,
            options=canonical_options,
        )
        active_limit = None
        if study_type == "ongoing":
            active_limit = SpcLimitVersion.query.filter_by(
                analysis_family=analysis_family,
                process_stream_key=study_input.process_stream_key,
                characteristic=study_input.characteristic,
                status="active",
            ).first()
            if active_limit is None:
                raise SpcValidationError(
                    "SPC_ACTIVE_LIMIT_REQUIRED",
                    "持續 SPC 必須先有同一製程流與特性的生效核准界限",
                )
            if analysis_family == "attribute":
                saved = dict(active_limit.limits or {})
                frozen_options = _canonical_attribute_options(saved.get("options") or {
                    "interval": saved.get("interval", "day"),
                    "chart_type": active_limit.chart_type,
                    "alpha": saved.get("alpha", 0.0027),
                })
                if options is None:
                    canonical_options = frozen_options
                    study_input = _adapter_input(
                        source, filters, analysis_family="attribute",
                        options=canonical_options,
                    )
                elif canonical_options != frozen_options:
                    raise SpcValidationError(
                        "SPC_ATTRIBUTE_OPTIONS_MISMATCH",
                        "目前 attribute options 必須與核准界限的受控選項一致",
                    )
        results = (
            _calculate_ongoing_results(study_input, active_limit)
            if active_limit is not None
            else _calculate_results(study_input)
        )
        identity = {
            "source": source,
            "study_type": study_type,
            "analysis_family": analysis_family,
            "process_stream_key": study_input.process_stream_key,
            "characteristic": study_input.characteristic,
        }
        study = SpcStudy.query.filter_by(**identity).first()
        if study is None:
            study = SpcStudy(
                **identity,
                filters=dict(study_input.filters),
                status="active" if study_type == "ongoing" else "draft",
                created_by=actor_id,
            )
            if db.session.get_bind().dialect.name == "postgresql":
                try:
                    with db.session.begin_nested():
                        db.session.add(study)
                        db.session.flush()
                except IntegrityError:
                    study = SpcStudy.query.filter_by(**identity).one()
            else:
                db.session.add(study)
                db.session.flush()
        elif study_type == "ongoing":
            study.status = "active"

        study = (
            SpcStudy.query.filter_by(id=study.id)
            .with_for_update()
            .one()
        )
        latest = db.session.query(func.max(SpcStudyVersion.version_no)).filter_by(
            study_id=study.id
        ).scalar()
        version = SpcStudyVersion(
            study_id=study.id,
            version_no=int(latest or 0) + 1,
            method_version=SPC_METHOD_VERSION,
            code_version=SPC_CODE_VERSION,
            data_hash=study_input.data_hash,
            analysis_options=dict(study_input.options),
            specification_snapshot=dict(study_input.specification),
            status="active" if study_type == "ongoing" else "draft",
            created_by=actor_id,
            **results,
        )
        db.session.add(version)
        db.session.flush()

        _add_input_samples(version, source, study_input)
        db.session.flush()

        if active_limit is not None:
            chart = results["chart_result"] or {}
            violations = []
            for violation in (results["stability_result"] or {}).get("violations", []):
                index = int(violation["index"])
                chart_kind = violation["chart_kind"]
                if analysis_family == "attribute":
                    observed_values = chart.get("values", [])
                else:
                    observed_values = (chart.get(chart_kind) or {}).get("values", [])
                violations.append({
                    "chart_kind": chart_kind,
                    "rule_code": violation["rule"],
                    "point_index": index,
                    "observed_value": (
                        observed_values[index] if index < len(observed_values) else None
                    ),
                    "sample_id": (
                        version.samples[index].id if index < len(version.samples) else None
                    ),
                    "source_point_key": (
                        (
                            f"{version.samples[index].source_record_type}:"
                            f"{version.samples[index].subgroup_key}:"
                            f"{hashlib.sha256(json.dumps(sorted(version.samples[index].source_record_ids or [])).encode('utf-8')).hexdigest()[:24]}"
                        ) if analysis_family == "attribute" else (
                            f"{version.samples[index].source_record_type}:"
                            f"{version.samples[index].subgroup_key}"
                        )
                        if index < len(version.samples) else None
                    ),
                })
            from .spc_ocap_service import SpcOcapService

            SpcOcapService.sync_events(active_limit.id, version.id, violations)

        log_audit(
            actor_id, "analyze", "spc_study", version.id,
            new_val={
                "study_id": study.id, "version_no": version.version_no,
                "data_hash": version.data_hash,
            },
        )
        try:
            db.session.commit()
        except IntegrityError as exc:
            db.session.rollback()
            raise SpcConflict(
                "SPC_ANALYSIS_WRITE_CONFLICT",
                "同一製程流正在建立其他研究版本，請重新執行分析",
            ) from exc
        return version

    @staticmethod
    def list_studies() -> list[SpcStudy]:
        return SpcStudy.query.options(
            selectinload(SpcStudy.versions).selectinload(SpcStudyVersion.limit_versions)
            .selectinload(SpcLimitVersion.events),
        ).order_by(SpcStudy.created_at.desc(), SpcStudy.id.desc()).all()

    @staticmethod
    def get_study(study_id: int) -> SpcStudy:
        study = (
            SpcStudy.query
            .options(
                selectinload(SpcStudy.versions).selectinload(
                    SpcStudyVersion.samples
                ),
                selectinload(SpcStudy.versions)
                .selectinload(SpcStudyVersion.limit_versions)
                .selectinload(SpcLimitVersion.events)
                .selectinload(SpcEvent.ocap),
            )
            .filter_by(id=study_id)
            .first()
        )
        if study is None:
            raise SpcNotFound("SPC_STUDY_NOT_FOUND", "找不到 SPC 研究")
        return study

    @staticmethod
    def get_study_history(
        study_id: int, *, page: int = 1, per_page: int = 20
    ):
        """以新到舊順序分頁讀取研究版本摘要。"""

        if db.session.get(SpcStudy, study_id) is None:
            raise SpcNotFound("SPC_STUDY_NOT_FOUND", "找不到 SPC 研究")
        return (
            SpcStudyVersion.query
            .filter_by(study_id=study_id)
            .order_by(SpcStudyVersion.version_no.desc())
            .paginate(page=page, per_page=per_page, error_out=False)
        )

    @staticmethod
    def preview(source: str, filters: Mapping[str, Any]) -> dict[str, Any]:
        """以共用引擎產生即時預覽，並由同一結果映射過渡期舊欄位。"""

        study_input = _adapter_input(source, filters)
        cache_key = (
            f"spc2026|{source}|{study_input.process_stream_key}|{study_input.data_hash}"
        )
        cached = SPCCache.query.filter_by(cache_key=cache_key).first()
        if cached is not None:
            expires_at = cached.expires_at
            now = datetime.now(timezone.utc)
            if expires_at.tzinfo is None:
                # SQLite 會移除時區資訊；欄位內容仍是 UTC，不可改用本地時間比較。
                now = now.replace(tzinfo=None)
            if expires_at > now:
                return cached.result
        results = _calculate_results(study_input)
        chart = results["chart_result"] or {}
        location = chart.get("location") or {}
        variation = chart.get("variation") or {}
        subgroups = list(study_input.subgroups)
        all_values = [
            float(value)
            for subgroup in subgroups
            for value in (subgroup.distribution_values or subgroup.values)
        ]

        def series_values(series: Mapping[str, Any], name: str) -> list[Any]:
            return list(series.get(name) or [])

        def first(values: list[Any]):
            return values[0] if values else None

        x_values = series_values(location, "values")
        x_cls = series_values(location, "cl")
        x_ucls = series_values(location, "ucl")
        x_lcls = series_values(location, "lcl")
        r_values = series_values(variation, "values")
        r_cls = series_values(variation, "cl")
        r_ucls = series_values(variation, "ucl")
        r_lcls = series_values(variation, "lcl")
        if not chart and subgroups:
            # 不適用管制圖時仍提供描述性子組統計，但絕不補造管制界限。
            x_values = [float(np.mean(group.values)) for group in subgroups]
            r_values = [float(np.ptp(group.values)) for group in subgroups]
        subgroup_sizes = list(chart.get("subgroup_sizes") or [group.n for group in subgroups])
        reasons = [asdict(reason) for reason in study_input.reasons]
        applicability = dict(results["applicability_result"] or {})
        if not applicability.get("applicable") and applicability.get("reason_code"):
            reasons.append({
                "code": applicability["reason_code"],
                "message": applicability.get("message") or "目前資料不可計算",
                "details": None,
            })
        applicability["reasons"] = reasons
        stability = results["stability_result"]
        distribution = results["distribution_result"]
        capability = results["capability_result"]
        labels = [group.key for group in subgroups]
        dates = [_timestamp_text(group.timestamp) or "" for group in subgroups]
        ids = [str(group.record_ids[0]) if group.record_ids else "" for group in subgroups]
        preview = {
            "schema_version": SPC_METHOD_VERSION,
            "source": source,
            "filters": dict(study_input.filters),
            "process_stream_key": study_input.process_stream_key,
            "characteristic": study_input.characteristic,
            "data_hash": study_input.data_hash,
            "charts": chart or None,
            "stability": stability,
            "distribution": distribution,
            "capability": capability,
            "applicability": applicability,
            "time_model": results["time_model_result"],
            "specification": dict(study_input.specification),
            "study_version": None,
            "study": {
                "stability": stability,
                "distribution": distribution,
                "capability": capability,
                "applicability": applicability,
                "time_model": results["time_model_result"],
            },
            # 過渡期舊欄位：全部直接映射自上方同一份結果。
            "labels": labels,
            "ids": ids,
            "dates": dates,
            "avgs": x_values,
            "ranges": r_values,
            "all_values": all_values,
            "subgroup_sizes": subgroup_sizes,
            "x_cl": first(x_cls),
            "x_ucl": first(x_ucls),
            "x_lcl": first(x_lcls),
            "r_cl": first(r_cls),
            "r_ucl": first(r_ucls),
            "r_lcl": first(r_lcls),
            "x_cls": x_cls,
            "x_ucls": x_ucls,
            "x_lcls": x_lcls,
            "r_cls": r_cls,
            "r_ucls": r_ucls,
            "r_lcls": r_lcls,
            "avg_subgroup_size": (
                int(round(float(np.mean(subgroup_sizes)))) if subgroup_sizes else None
            ),
            "variable_subgroup_size": len(set(subgroup_sizes)) > 1,
            "sigma_within": chart.get("sigma_within"),
            "process_capability": capability,
            "tolerance": dict(study_input.specification),
            "characteristic_class": (
                study_input.specification.get("characteristic_class") or "其他"
            ),
            "excluded_count": int(study_input.metadata.get("excluded_count", 0)),
            "insufficient_data": [],
            "cpk_trend": [],
            "limits_frozen": False,
        }
        # 統一轉為 JSON 原生型別，確保首次計算與快取讀回的契約完全一致。
        preview = json.loads(json.dumps(preview, ensure_ascii=False))
        _upsert_preview_cache(
            cache_key,
            preview,
            datetime.now(timezone.utc) + timedelta(hours=1),
        )
        db.session.commit()
        return preview

    @staticmethod
    def submit(version_id: int, actor_id: int, *, reason: str) -> SpcStudyVersion:
        _require_permission(actor_id, "spc.manage")
        reason = _require_reason(reason)
        version = _get_version(version_id)
        if version.status != "draft":
            raise SpcConflict("INVALID_STUDY_STATE", "只有草稿研究可以送審")
        _assert_source_unchanged(version)
        version.status = "submitted"
        version.study.status = "submitted"
        log_audit(
            actor_id, "submit", "spc_study", version.id,
            old_val={"status": "draft"},
            new_val={"status": "submitted", "reason": reason},
        )
        db.session.commit()
        return version

    @staticmethod
    def confirm_time_model(
        version_id: int, actor_id: int, *, model: str, reason: str
    ) -> SpcStudyVersion:
        _require_permission(actor_id, "spc.manage")
        reason = _require_reason(reason)
        version = _get_version(version_id)
        if version.status != "draft":
            raise SpcConflict("INVALID_STUDY_STATE", "目前狀態不可確認時間模型")
        candidate = (version.time_model_result or {}).get("candidate")
        if model not in {"A1", "A2"} or model != candidate:
            raise SpcValidationError("TIME_MODEL_MISMATCH", "只能確認系統證據支持的 A1/A2 候選")
        confirmed_time_model = {
            **(version.time_model_result or {}),
            "model": model,
            "confirmed": True,
            "confirmed_by": actor_id,
            "confirmed_at": utc_now().isoformat(),
            "confirmation_reason": reason,
        }
        latest = db.session.query(func.max(SpcStudyVersion.version_no)).filter_by(
            study_id=version.study_id
        ).scalar()
        confirmed_capability = _recalculate_capability(version, confirmed_time_model)
        confirmed = SpcStudyVersion(
            study_id=version.study_id,
            version_no=int(latest or 0) + 1,
            method_version=version.method_version,
            code_version=version.code_version,
            data_hash=version.data_hash,
            analysis_options=dict(version.analysis_options or {}),
            specification_snapshot=dict(version.specification_snapshot or {}),
            chart_result=dict(version.chart_result or {}),
            stability_result=dict(version.stability_result or {}),
            distribution_result=dict(version.distribution_result or {}),
            time_model_result=confirmed_time_model,
            capability_result=confirmed_capability,
            applicability_result=dict(version.applicability_result or {}),
            status="draft",
            audit_incomplete=version.audit_incomplete,
            created_by=actor_id,
        )
        db.session.add(confirmed)
        db.session.flush()
        _copy_saved_samples(version, confirmed)
        version.status = "superseded"
        log_audit(
            actor_id, "confirm_time_model", "spc_study", confirmed.id,
            old_val={"version_id": version.id, "status": "draft"},
            new_val={
                "version_id": confirmed.id,
                "model": model,
                "reason": reason,
            },
        )
        db.session.commit()
        return confirmed

    @staticmethod
    def approve_and_activate(
        version_id: int, actor_id: int, *, reason: str
    ) -> SpcLimitVersion:
        _require_permission(actor_id, "spc.approve")
        reason = _require_reason(reason)
        version = _get_version(version_id)
        if version.study.analysis_family == "machine":
            raise SpcValidationError("RESEARCH_APPROVAL_REQUIRED", "機器研究只能使用研究核准流程")
        if version.status != "submitted":
            raise SpcConflict("INVALID_STUDY_STATE", "只有已送審研究可以核准")
        _assert_source_unchanged(version)
        _assert_approvable(version)

        now = utc_now()
        active = (
            SpcLimitVersion.query
            .filter_by(
                analysis_family=version.study.analysis_family,
                process_stream_key=version.study.process_stream_key,
                characteristic=version.study.characteristic,
                status="active",
            )
            .with_for_update()
            .first()
        )
        if active is not None:
            active.status = "retired"
            active.retired_by = actor_id
            active.retired_at = now

        revision = db.session.query(func.max(SpcLimitVersion.revision)).filter_by(
            analysis_family=version.study.analysis_family,
            process_stream_key=version.study.process_stream_key,
            characteristic=version.study.characteristic,
        ).scalar()
        chart = version.chart_result or {}
        if version.study.analysis_family == "attribute":
            limits = {
                "center": chart["center"],
                "alpha": chart["exact_alpha"],
                "interval": chart.get("interval"),
                "options": dict(version.analysis_options or {}),
                "baseline_n": (
                    chart.get("n", [None])[0] if chart.get("chart_type") == "np" else None
                ),
                "rules_used": list((version.stability_result or {}).get("rules_used") or []),
                "lower_counts": list(chart.get("lower_counts") or []),
                "upper_counts": list(chart.get("upper_counts") or []),
            }
        else:
            limits = {
                "location": {
                    key: chart["location"][key] for key in ("cl", "ucl", "lcl")
                },
                "variation": {
                    key: chart["variation"][key] for key in ("cl", "ucl", "lcl")
                },
                "subgroup_sizes": chart.get("subgroup_sizes", []),
            }
        limit = SpcLimitVersion(
            study_version_id=version.id,
            analysis_family=version.study.analysis_family,
            process_stream_key=version.study.process_stream_key,
            characteristic=version.study.characteristic,
            revision=int(revision or 0) + 1,
            chart_type=chart["chart_type"],
            limits=limits,
            status="active",
            reason=reason,
            created_by=version.created_by,
            approved_by=actor_id,
            approved_at=now,
            effective_at=now,
        )
        db.session.add(limit)
        version.status = "active"
        version.study.status = "active"
        log_audit(
            actor_id, "approve_activate", "spc_study", version.id,
            old_val={"status": "submitted"},
            new_val={"status": "active", "revision": limit.revision, "reason": reason},
        )
        try:
            db.session.commit()
        except IntegrityError as exc:
            db.session.rollback()
            raise SpcConflict(
                "ACTIVE_LIMIT_CONFLICT", "同一製程流已有其他啟用界限，請重新整理"
            ) from exc
        return limit

    @staticmethod
    def approve_research(
        version_id: int, actor_id: int, *, reason: str
    ) -> SpcStudyVersion:
        """核准固定機台研究，不建立 SPC 生產界限。"""

        _require_permission(actor_id, "spc.approve")
        reason = _require_reason(reason)
        version = _get_version(version_id)
        if version.status == "approved":
            return version
        if version.status != "submitted":
            raise SpcConflict("INVALID_STUDY_STATE", "只有已送審研究可以核准")
        _assert_source_unchanged(version)
        _assert_research_approvable(version)
        transitioned = db.session.execute(
            update(SpcStudyVersion)
            .where(
                SpcStudyVersion.id == version.id,
                SpcStudyVersion.status == "submitted",
            )
            .values(status="approved")
            .execution_options(synchronize_session=False)
        )
        if transitioned.rowcount != 1:
            db.session.rollback()
            current = _get_version(version_id)
            if current.status == "approved":
                return current
            raise SpcConflict("INVALID_STUDY_STATE", "研究狀態已變更，請重新整理")
        study_transitioned = db.session.execute(
            update(SpcStudy)
            .where(SpcStudy.id == version.study_id, SpcStudy.status == "submitted")
            .values(status="approved")
        )
        if study_transitioned.rowcount != 1:
            db.session.rollback()
            raise SpcConflict("INVALID_STUDY_STATE", "研究主檔狀態已變更，請重新整理")
        log_audit(
            actor_id, "approve_research", "spc_study", version.id,
            old_val={"status": "submitted"},
            new_val={"status": "approved", "reason": reason},
        )
        db.session.commit()
        db.session.expire(version)
        return version

    @staticmethod
    def reject(version_id: int, actor_id: int, *, reason: str) -> SpcStudyVersion:
        _require_permission(actor_id, "spc.approve")
        reason = _require_reason(reason)
        version = _get_version(version_id)
        if version.status != "submitted":
            raise SpcConflict("INVALID_STUDY_STATE", "只有已送審研究可以退回")
        version.status = "rejected"
        version.study.status = "rejected"
        log_audit(
            actor_id, "reject", "spc_study", version.id,
            old_val={"status": "submitted"},
            new_val={"status": "rejected", "reason": reason},
        )
        db.session.commit()
        return version

    @staticmethod
    def retire(limit_id: int, actor_id: int, *, reason: str) -> SpcLimitVersion:
        _require_permission(actor_id, "spc.approve")
        reason = _require_reason(reason)
        limit = db.session.get(SpcLimitVersion, limit_id)
        if limit is None:
            raise SpcNotFound("SPC_LIMIT_NOT_FOUND", "找不到 SPC 界限版本")
        if limit.status != "active":
            raise SpcConflict("INVALID_LIMIT_STATE", "只有啟用界限可以停用")
        limit.status = "retired"
        limit.retired_by = actor_id
        limit.retired_at = utc_now()
        if limit.study_version.status == "active":
            limit.study_version.status = "retired"
            limit.study_version.study.status = "retired"
        log_audit(
            actor_id, "retire", "spc_study", limit.study_version_id,
            old_val={"status": "active"},
            new_val={"status": "retired", "reason": reason},
        )
        db.session.commit()
        return limit
