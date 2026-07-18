"""SPC 不可變研究版本與正式基準的生命週期服務。"""

from dataclasses import asdict
from datetime import date, datetime, timedelta, timezone
import json
from typing import Any, Callable, Mapping

import numpy as np
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError

from ..extensions import db
from ..models import (
    Role,
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
from .spc_analysis_service import calculate_process_capability
from .spc_chart_engine import SpcChartNotApplicable, calculate_chart_set
from .spc_contracts import SpcChartSet, SpcStudyInput, SpcSubgroup
from .spc_distribution import assess_distribution
from .spc_errors import (
    SpcConflict,
    SpcForbidden,
    SpcNotFound,
    SpcValidationError,
)
from .spc_stability import evaluate_study_stability
from .spc_time_model import classify_time_model


SPC_METHOD_VERSION = "2026.1"
ADAPTERS: dict[str, Callable[[Mapping[str, Any]], SpcStudyInput]] = {
    "shipping": build_shipping_study_input,
    "patrol": build_patrol_study_input,
}


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


def _adapter_input(source: str, filters: Mapping[str, Any]) -> SpcStudyInput:
    adapter = ADAPTERS.get(source)
    if adapter is None:
        raise SpcValidationError("SPC_SOURCE_UNSUPPORTED", f"不支援的 SPC 資料來源：{source}")
    return adapter(filters)


def _chart_result(chart_set: SpcChartSet) -> dict[str, Any]:
    def plain(value):
        if isinstance(value, dict):
            return {key: plain(item) for key, item in value.items()}
        if isinstance(value, (list, tuple)):
            return [plain(item) for item in value]
        return value

    return plain(asdict(chart_set))


def _calculate_results(study_input: SpcStudyInput) -> dict[str, Any]:
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


def _timestamp_text(value: date | datetime | str | None) -> str | None:
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return str(value) if value is not None else None


def _assert_source_unchanged(version: SpcStudyVersion) -> SpcStudyInput:
    current = _adapter_input(version.study.source, version.study.filters)
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


class SpcStudyService:
    """SPC 研究與核准界限的應用服務。"""

    @staticmethod
    def analyze(source: str, filters: Mapping[str, Any], actor_id: int) -> SpcStudyVersion:
        _require_permission(actor_id, "spc.view")
        study_input = _adapter_input(source, filters)
        study = SpcStudy.query.filter_by(
            source=source,
            process_stream_key=study_input.process_stream_key,
            characteristic=study_input.characteristic,
        ).first()
        if study is None:
            study = SpcStudy(
                source=source,
                study_type="retrospective",
                process_stream_key=study_input.process_stream_key,
                characteristic=study_input.characteristic,
                filters=dict(study_input.filters),
                status="draft",
                created_by=actor_id,
            )
            db.session.add(study)
            db.session.flush()

        latest = db.session.query(func.max(SpcStudyVersion.version_no)).filter_by(
            study_id=study.id
        ).scalar()
        results = _calculate_results(study_input)
        version = SpcStudyVersion(
            study_id=study.id,
            version_no=int(latest or 0) + 1,
            method_version=SPC_METHOD_VERSION,
            data_hash=study_input.data_hash,
            specification_snapshot=dict(study_input.specification),
            status="draft",
            created_by=actor_id,
            **results,
        )
        db.session.add(version)
        db.session.flush()

        for index, subgroup in enumerate(study_input.subgroups):
            db.session.add(SpcStudySample(
                version_id=version.id,
                source_record_type=(
                    "ShippingMeasurement" if source == "shipping" else "PatrolDetail"
                ),
                source_record_id=subgroup.record_ids[0],
                source_measurement_id=(
                    subgroup.measurement_ids[0] if subgroup.measurement_ids else None
                ),
                source_record_ids=list(subgroup.record_ids),
                source_measurement_ids=list(subgroup.measurement_ids),
                sample_timestamp=_timestamp_text(subgroup.timestamp),
                subgroup_key=subgroup.key,
                subgroup_order=index,
                values=list(subgroup.values),
                distribution_values=list(
                    subgroup.distribution_values or subgroup.values
                ),
                excluded=False,
                exclusion_snapshot=list(subgroup.exclusion_snapshot),
            ))

        log_audit(
            actor_id, "analyze", "spc_study", version.id,
            new_val={
                "study_id": study.id, "version_no": version.version_no,
                "data_hash": version.data_hash,
            },
        )
        db.session.commit()
        return version

    @staticmethod
    def list_studies() -> list[SpcStudy]:
        return SpcStudy.query.order_by(SpcStudy.created_at.desc(), SpcStudy.id.desc()).all()

    @staticmethod
    def get_study(study_id: int) -> SpcStudy:
        study = db.session.get(SpcStudy, study_id)
        if study is None:
            raise SpcNotFound("SPC_STUDY_NOT_FOUND", "找不到 SPC 研究")
        return study

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
            db.session.delete(cached)
            db.session.flush()
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
        db.session.add(SPCCache(
            cache_key=cache_key,
            result=preview,
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        ))
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
        if version.status not in {"draft", "submitted"}:
            raise SpcConflict("INVALID_STUDY_STATE", "目前狀態不可確認時間模型")
        candidate = (version.time_model_result or {}).get("candidate")
        if model not in {"A1", "A2"} or model != candidate:
            raise SpcValidationError("TIME_MODEL_MISMATCH", "只能確認系統證據支持的 A1/A2 候選")
        version.time_model_result = {
            **(version.time_model_result or {}),
            "model": model,
            "confirmed": True,
            "confirmed_by": actor_id,
            "confirmed_at": utc_now().isoformat(),
            "confirmation_reason": reason,
        }
        version.capability_result = _recalculate_capability(
            version, version.time_model_result
        )
        log_audit(
            actor_id, "confirm_time_model", "spc_study", version.id,
            new_val={"model": model, "reason": reason},
        )
        db.session.commit()
        return version

    @staticmethod
    def approve_and_activate(
        version_id: int, actor_id: int, *, reason: str
    ) -> SpcLimitVersion:
        _require_permission(actor_id, "spc.approve")
        reason = _require_reason(reason)
        version = _get_version(version_id)
        if version.status != "submitted":
            raise SpcConflict("INVALID_STUDY_STATE", "只有已送審研究可以核准")
        _assert_source_unchanged(version)
        _assert_approvable(version)

        now = utc_now()
        active = (
            SpcLimitVersion.query
            .filter_by(
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
            process_stream_key=version.study.process_stream_key,
            characteristic=version.study.characteristic,
        ).scalar()
        chart = version.chart_result or {}
        limit = SpcLimitVersion(
            study_version_id=version.id,
            process_stream_key=version.study.process_stream_key,
            characteristic=version.study.characteristic,
            revision=int(revision or 0) + 1,
            chart_type=chart["chart_type"],
            limits={
                "location": {
                    key: chart["location"][key] for key in ("cl", "ucl", "lcl")
                },
                "variation": {
                    key: chart["variation"][key] for key in ("cl", "ucl", "lcl")
                },
                "subgroup_sizes": chart.get("subgroup_sizes", []),
            },
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
