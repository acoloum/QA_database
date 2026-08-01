"""SPC 共用研究、核准界限與 OCAP API。"""

from datetime import date, datetime
from decimal import Decimal
from functools import wraps

from flask import Blueprint, jsonify, request
from sqlalchemy.orm import selectinload

from ..extensions import db
from ..models import (
    SpcLimitVersion, SpcOcap, SpcStudySample, SpcStudyVersion,
    SpcValidationRun,
)
from ..services.spc_errors import SpcServiceError, SpcValidationError
from ..services.spc_ocap_service import SpcOcapService
from ..services.spc_study_service import SpcStudyService, _validate_monitoring_limit_ownership
from ..utils import auth_required, require_permission


spc_studies_bp = Blueprint("spc_studies", __name__)


def _json_value(value):
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: _json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    return value


def _applicability(version):
    result = dict(version.applicability_result or {})
    result.setdefault("applicable", False)
    if not result["applicable"] and "reasons" not in result:
        reason_code = result.get("reason_code")
        result["reasons"] = ([{
            "code": reason_code,
            "message": result.get("message") or "目前資料不可計算",
        }] if reason_code else [])
    return result


def serialize_ocap(ocap):
    if ocap is None:
        return None
    return _json_value({
        "id": ocap.id,
        "event_id": ocap.event_id,
        "investigation_6m": ocap.investigation_6m,
        "remeasurement": ocap.remeasurement,
        "process_adjustment": ocap.process_adjustment,
        "product_disposition": ocap.product_disposition,
        "owner_id": ocap.owner_id,
        "effectiveness": ocap.effectiveness,
        "status": ocap.status,
        "created_by": ocap.created_by,
        "updated_by": ocap.updated_by,
        "created_at": ocap.created_at,
        "updated_at": ocap.updated_at,
    })


def serialize_event(event, *, versions_by_id=None, samples_by_id=None):
    attribute_evidence = None
    version = (versions_by_id or {}).get(event.study_version_id)
    sample = (samples_by_id or {}).get(event.sample_id) if event.sample_id else None
    if version is not None and version.study.analysis_family == "attribute":
        values = list(sample.values or []) if sample is not None else []
        residuals = (version.chart_result or {}).get("pearson_residuals") or []
        attribute_evidence = {
            "x": values[0] if values else None,
            "n": values[1] if len(values) > 1 else None,
            "display_value": event.observed_value,
            "pearson_residual": (
                residuals[event.point_index]
                if event.point_index < len(residuals) else None
            ),
            "subgroup_key": sample.subgroup_key if sample is not None else None,
        }
    chart = dict(version.chart_result or {}) if version is not None else {}
    scale = chart.get("scale", "original")
    transformation_decision = (
        chart.get("transformation_decision") if scale == "transformed" else None
    )
    return _json_value({
        "id": event.id,
        "limit_version_id": event.limit_version_id,
        "study_version_id": event.study_version_id,
        "sample_id": event.sample_id,
        "chart_kind": event.chart_kind,
        "rule_code": event.rule_code,
        "point_index": event.point_index,
        "source_point_key": event.source_point_key,
        "observed_value": event.observed_value,
        "scale": scale,
        "transformation_decision": transformation_decision,
        "original_sample_values": (
            list(sample.values or [])
            if scale == "transformed" and sample is not None else None
        ),
        "attribute_evidence": attribute_evidence,
        "status": event.status,
        "created_at": event.created_at,
        "ocap": serialize_ocap(event.ocap),
    })


def serialize_limit_version(limit, *, versions_by_id=None, samples_by_id=None):
    return _json_value({
        "id": limit.id,
        "study_version_id": limit.study_version_id,
        "analysis_family": limit.analysis_family,
        "revision": limit.revision,
        "chart_type": limit.chart_type,
        "limits": limit.limits,
        "status": limit.status,
        "reason": limit.reason,
        "audit_incomplete": limit.audit_incomplete,
        "approved_by": limit.approved_by,
        "approved_at": limit.approved_at,
        "effective_at": limit.effective_at,
        "retired_by": limit.retired_by,
        "retired_at": limit.retired_at,
        "events": [serialize_event(event, versions_by_id=versions_by_id, samples_by_id=samples_by_id) for event in limit.events],
    })


def serialize_validation_run(run: SpcValidationRun) -> dict:
    """序列化不可變軟體確效證據，包含精確差異與執行者追溯。"""

    return _json_value({
        "id": run.id,
        "dataset_version": run.dataset_version,
        "method_version": run.method_version,
        "code_version": run.code_version,
        "expected": run.expected,
        "actual": run.actual,
        "tolerances": run.tolerances,
        "result": run.result,
        "details": run.details,
        "executed_by": run.executed_by,
        "executed_at": run.executed_at,
    })


def _prefetch_monitoring_limits(versions):
    """批次取得 ongoing 版本引用的 immutable limits，避免 serializer N+1。"""

    ids = {
        (version.time_model_result or {}).get("limit_version_id")
        for version in versions
    }
    ids.discard(None)
    if not ids:
        return {}
    limits = SpcLimitVersion.query.options(
        selectinload(SpcLimitVersion.events),
        selectinload(SpcLimitVersion.study_version).selectinload(SpcStudyVersion.study),
    ).filter(SpcLimitVersion.id.in_(ids)).all()
    result = {limit.id: limit for limit in limits}
    for version in versions:
        limit_id = (version.time_model_result or {}).get("limit_version_id")
        if limit_id:
            limit = result.get(limit_id)
            if limit is None:
                raise SpcValidationError("SPC_MONITORING_LIMIT_NOT_FOUND", "監控版本引用的界限不存在")
            _validate_monitoring_limit_ownership(version, limit)
    return result


def _serialization_context(versions, monitoring_limits):
    """批次建立 event serialization maps，避免每個 event 再查 version/sample。"""

    event_versions = {version.id: version for version in versions}
    events = [event for limit in monitoring_limits.values() for event in limit.events]
    missing_version_ids = {event.study_version_id for event in events} - set(event_versions)
    if missing_version_ids:
        loaded = SpcStudyVersion.query.options(selectinload(SpcStudyVersion.study)).filter(
            SpcStudyVersion.id.in_(missing_version_ids)
        ).all()
        event_versions.update({version.id: version for version in loaded})
    sample_ids = {event.sample_id for event in events if event.sample_id is not None}
    samples = SpcStudySample.query.filter(SpcStudySample.id.in_(sample_ids)).all() if sample_ids else []
    return event_versions, {sample.id: sample for sample in samples}


def serialize_version(
    version, *, include_samples=False, include_relations=True, monitoring_limits=None,
    event_versions=None, event_samples=None,
):
    monitoring_limit = None
    if include_relations:
        monitoring_limit_id = (version.time_model_result or {}).get("limit_version_id")
        monitoring_limit = (
            (monitoring_limits or {}).get(monitoring_limit_id)
            if monitoring_limit_id else None
        )
        if monitoring_limit_id and monitoring_limit is None and monitoring_limits is None:
            monitoring_limit = db.session.get(SpcLimitVersion, monitoring_limit_id)
    result = {
        "id": version.id,
        "study_id": version.study_id,
        "source": version.study.source,
        "study_type": version.study.study_type,
        "analysis_family": version.study.analysis_family,
        "process_stream_key": version.study.process_stream_key,
        "filters": version.study.filters or {},
        "version_no": version.version_no,
        "method_version": version.method_version,
        "code_version": version.code_version,
        "data_hash": version.data_hash,
        "options": version.analysis_options or {},
        "specification": version.specification_snapshot or {},
        "charts": version.chart_result,
        "stability": version.stability_result or {},
        "distribution": version.distribution_result or {},
        "time_model": version.time_model_result or {},
        "capability": version.capability_result or {},
        "applicability": _applicability(version),
        "status": version.status,
        "audit_incomplete": version.audit_incomplete,
        "created_by": version.created_by,
        "created_at": version.created_at,
    }
    if include_relations:
        result["limit_versions"] = [
            serialize_limit_version(limit, versions_by_id=event_versions, samples_by_id=event_samples) for limit in version.limit_versions
        ]
        result["monitoring_limit"] = (
            serialize_limit_version(monitoring_limit, versions_by_id=event_versions, samples_by_id=event_samples) if monitoring_limit else None
        )
    if include_samples:
        result["samples"] = [{
            "id": sample.id,
            "key": sample.subgroup_key,
            "order": sample.subgroup_order,
            "timestamp": sample.sample_timestamp,
            "values": sample.values,
            "distribution_values": sample.distribution_values,
            "record_ids": sample.source_record_ids,
            "measurement_ids": sample.source_measurement_ids,
            "exclusion_snapshot": sample.exclusion_snapshot,
        } for sample in version.samples]
    return _json_value(result)


def serialize_study(study, *, include_versions=False, monitoring_limits=None, event_versions=None, event_samples=None):
    result = {
        "id": study.id,
        "source": study.source,
        "study_type": study.study_type,
        "analysis_family": study.analysis_family,
        "process_stream_key": study.process_stream_key,
        "characteristic": study.characteristic,
        "filters": study.filters,
        "msa_status": study.msa_status,
        "sampling_note": study.sampling_note,
        "status": study.status,
        "legacy_limit_id": study.legacy_limit_id,
        "created_by": study.created_by,
        "created_at": study.created_at,
        "latest_version": (
            serialize_version(study.versions[-1], monitoring_limits=monitoring_limits, event_versions=event_versions, event_samples=event_samples) if study.versions else None
        ),
    }
    if include_versions:
        result["versions"] = [
            serialize_version(version, include_samples=True, monitoring_limits=monitoring_limits, event_versions=event_versions, event_samples=event_samples)
            for version in study.versions
        ]
    return _json_value(result)


def _success(data, status=200):
    return jsonify({"success": True, "data": data}), status


def _handle_spc_errors(function):
    @wraps(function)
    def wrapped(*args, **kwargs):
        try:
            return function(*args, **kwargs)
        except SpcServiceError as error:
            payload = {
                "success": False,
                "code": error.code,
                "message": error.message,
            }
            if error.details is not None:
                payload["details"] = _json_value(error.details)
            status_code = (
                400 if error.code in {
                    "SPC_ANALYSIS_FAMILY_INVALID", "MACHINE_STREAM_NOT_FIXED",
                }
                else error.status_code
            )
            return jsonify(payload), status_code
        except ValueError as error:
            return jsonify({
                "success": False, "code": "VALIDATION_ERROR", "message": str(error),
            }), 400
    return wrapped


@spc_studies_bp.post("/api/spc/studies/analyze")
@auth_required
@require_permission("spc.view")
@_handle_spc_errors
def analyze_study(current_user):
    body = request.get_json(silent=True) or {}
    source = body.get("source")
    filters = body.get("filters") or {}
    if not source:
        raise SpcValidationError("SPC_SOURCE_REQUIRED", "必須指定 SPC 資料來源")
    analysis_family = (
        body["analysis_family"] if "analysis_family" in body else "variable"
    )
    version = SpcStudyService.analyze(
        source,
        filters,
        current_user.id,
        study_type=body.get("study_type") or "retrospective",
        analysis_family=analysis_family,
        options=body.get("options"),
    )
    return _success(serialize_version(version, include_samples=True))


@spc_studies_bp.get("/api/spc/studies")
@auth_required
@require_permission("spc.view")
@_handle_spc_errors
def list_studies(current_user):
    studies = SpcStudyService.list_studies()
    limits = _prefetch_monitoring_limits([
        version for study in studies for version in study.versions
    ])
    versions = [version for study in studies for version in study.versions]
    event_versions, event_samples = _serialization_context(versions, limits)
    return _success([serialize_study(study, monitoring_limits=limits, event_versions=event_versions, event_samples=event_samples) for study in studies])


@spc_studies_bp.get("/api/spc/studies/<int:study_id>")
@auth_required
@require_permission("spc.view")
@_handle_spc_errors
def get_study(current_user, study_id):
    study = SpcStudyService.get_study(study_id)
    limits = _prefetch_monitoring_limits(study.versions)
    event_versions, event_samples = _serialization_context(study.versions, limits)
    return _success(serialize_study(study, include_versions=True, monitoring_limits=limits, event_versions=event_versions, event_samples=event_samples))


@spc_studies_bp.get("/api/spc/studies/<int:study_id>/history")
@auth_required
@require_permission("spc.view")
@_handle_spc_errors
def get_study_history(current_user, study_id):
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 20, type=int)
    if page < 1 or per_page < 1 or per_page > 100:
        raise SpcValidationError(
            "SPC_HISTORY_PAGINATION_INVALID",
            "頁碼必須大於 0，且每頁筆數必須介於 1 到 100",
        )
    pagination = SpcStudyService.get_study_history(
        study_id, page=page, per_page=per_page
    )
    return _success({
        "items": [
            serialize_version(version, include_relations=False)
            for version in pagination.items
        ],
        "total": pagination.total,
        "page": pagination.page,
        "per_page": pagination.per_page,
        "pages": pagination.pages,
    })


@spc_studies_bp.post("/api/spc/study-versions/<int:version_id>/submit")
@auth_required
@require_permission("spc.manage")
@_handle_spc_errors
def submit_study(current_user, version_id):
    body = request.get_json(silent=True) or {}
    version = SpcStudyService.submit(
        version_id, current_user.id, reason=body.get("reason")
    )
    return _success(serialize_version(version))


@spc_studies_bp.post("/api/spc/study-versions/<int:version_id>/time-model")
@auth_required
@require_permission("spc.approve")
@_handle_spc_errors
def confirm_time_model(current_user, version_id):
    body = request.get_json(silent=True) or {}
    version = SpcStudyService.confirm_time_model(
        version_id, current_user.id, model=body.get("model"), reason=body.get("reason")
    )
    return _success(serialize_version(version))


@spc_studies_bp.post("/api/spc/study-versions/<int:version_id>/approve")
@auth_required
@require_permission("spc.approve")
@_handle_spc_errors
def approve_study(current_user, version_id):
    body = request.get_json(silent=True) or {}
    limit = SpcStudyService.approve_and_activate(
        version_id, current_user.id, reason=body.get("reason")
    )
    return _success(serialize_limit_version(limit))


@spc_studies_bp.post("/api/spc/study-versions/<int:version_id>/approve-research")
@auth_required
@require_permission("spc.approve")
@_handle_spc_errors
def approve_research(current_user, version_id):
    """核准機器等研究結論，不建立生產管制界限。"""

    body = request.get_json(silent=True) or {}
    version = SpcStudyService.approve_research(
        version_id, current_user.id, reason=body.get("reason")
    )
    return _success(serialize_version(version))


@spc_studies_bp.post("/api/spc/study-versions/<int:version_id>/transformation")
@auth_required
@require_permission("spc.approve")
@_handle_spc_errors
def confirm_transformation(current_user, version_id):
    body = request.get_json(silent=True) or {}
    version = SpcStudyService.confirm_transformation(
        version_id,
        current_user.id,
        model=body.get("model"),
        reason=body.get("reason"),
    )
    return _success(serialize_version(version))


@spc_studies_bp.post("/api/spc/study-versions/<int:version_id>/reject")
@auth_required
@require_permission("spc.approve")
@_handle_spc_errors
def reject_study(current_user, version_id):
    body = request.get_json(silent=True) or {}
    version = SpcStudyService.reject(
        version_id, current_user.id, reason=body.get("reason")
    )
    return _success(serialize_version(version))


@spc_studies_bp.post("/api/spc/limit-versions/<int:limit_id>/retire")
@auth_required
@require_permission("spc.approve")
@_handle_spc_errors
def retire_limit(current_user, limit_id):
    body = request.get_json(silent=True) or {}
    limit = SpcStudyService.retire(limit_id, current_user.id, reason=body.get("reason"))
    return _success({"id": limit.id, "status": limit.status})


@spc_studies_bp.get("/api/spc/assignees")
@auth_required
@require_permission("spc.manage")
@_handle_spc_errors
def list_ocap_assignees(current_user):
    return _success(SpcOcapService.list_assignable_users())


@spc_studies_bp.get("/api/spc/events/<int:event_id>")
@auth_required
@require_permission("spc.view")
@_handle_spc_errors
def get_spc_event(current_user, event_id):
    event = SpcOcapService.get_event(event_id)
    version = SpcStudyVersion.query.options(
        selectinload(SpcStudyVersion.study)
    ).filter_by(id=event.study_version_id).first()
    sample = db.session.get(SpcStudySample, event.sample_id) if event.sample_id else None
    return _success(serialize_event(
        event,
        versions_by_id={version.id: version} if version is not None else {},
        samples_by_id={sample.id: sample} if sample is not None else {},
    ))


@spc_studies_bp.post("/api/spc/events/<int:event_id>/ocap")
@auth_required
@require_permission("spc.manage")
@_handle_spc_errors
def create_ocap(current_user, event_id):
    payload = request.get_json(silent=True)
    if payload is None:
        payload = {}
    ocap = SpcOcapService.save_ocap(
        event_id, current_user.id, payload
    )
    return _success(serialize_ocap(ocap))


@spc_studies_bp.patch("/api/spc/ocap/<int:ocap_id>")
@auth_required
@require_permission("spc.manage")
@_handle_spc_errors
def update_ocap(current_user, ocap_id):
    ocap = db.session.get(SpcOcap, ocap_id)
    if ocap is None:
        raise SpcValidationError("SPC_OCAP_NOT_FOUND", "找不到 OCAP")
    payload = request.get_json(silent=True)
    if payload is None:
        payload = {}
    updated = SpcOcapService.save_ocap(
        ocap.event_id, current_user.id, payload
    )
    return _success(serialize_ocap(updated))
