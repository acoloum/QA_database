"""SPC 共用研究、核准界限與 OCAP API。"""

from datetime import date, datetime
from decimal import Decimal
from functools import wraps

from flask import Blueprint, jsonify, request

from ..extensions import db
from ..models import SpcLimitVersion, SpcOcap
from ..services.spc_errors import SpcServiceError, SpcValidationError
from ..services.spc_ocap_service import SpcOcapService
from ..services.spc_study_service import SpcStudyService
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


def serialize_event(event):
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
        "status": event.status,
        "created_at": event.created_at,
        "ocap": serialize_ocap(event.ocap),
    })


def serialize_limit_version(limit):
    return _json_value({
        "id": limit.id,
        "study_version_id": limit.study_version_id,
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
        "events": [serialize_event(event) for event in limit.events],
    })


def serialize_version(version, *, include_samples=False):
    monitoring_limit_id = (version.time_model_result or {}).get("limit_version_id")
    monitoring_limit = (
        db.session.get(SpcLimitVersion, monitoring_limit_id)
        if monitoring_limit_id else None
    )
    result = {
        "id": version.id,
        "study_id": version.study_id,
        "source": version.study.source,
        "study_type": version.study.study_type,
        "process_stream_key": version.study.process_stream_key,
        "filters": version.study.filters or {},
        "version_no": version.version_no,
        "method_version": version.method_version,
        "code_version": version.code_version,
        "data_hash": version.data_hash,
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
        "limit_versions": [
            serialize_limit_version(limit) for limit in version.limit_versions
        ],
        "monitoring_limit": (
            serialize_limit_version(monitoring_limit) if monitoring_limit else None
        ),
    }
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


def serialize_study(study, *, include_versions=False):
    result = {
        "id": study.id,
        "source": study.source,
        "study_type": study.study_type,
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
            serialize_version(study.versions[-1]) if study.versions else None
        ),
    }
    if include_versions:
        result["versions"] = [
            serialize_version(version, include_samples=True)
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
            return jsonify(payload), error.status_code
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
    version = SpcStudyService.analyze(
        source,
        filters,
        current_user.id,
        study_type=body.get("study_type") or "retrospective",
    )
    return _success(serialize_version(version, include_samples=True))


@spc_studies_bp.get("/api/spc/studies")
@auth_required
@require_permission("spc.view")
@_handle_spc_errors
def list_studies(current_user):
    return _success([serialize_study(study) for study in SpcStudyService.list_studies()])


@spc_studies_bp.get("/api/spc/studies/<int:study_id>")
@auth_required
@require_permission("spc.view")
@_handle_spc_errors
def get_study(current_user, study_id):
    return _success(serialize_study(SpcStudyService.get_study(study_id), include_versions=True))


@spc_studies_bp.get("/api/spc/studies/<int:study_id>/history")
@auth_required
@require_permission("spc.view")
@_handle_spc_errors
def get_study_history(current_user, study_id):
    study = SpcStudyService.get_study(study_id)
    return _success([serialize_version(version) for version in study.versions])


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
@require_permission("spc.manage")
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
    return _success({
        "id": limit.id, "study_version_id": limit.study_version_id,
        "revision": limit.revision, "status": limit.status,
        "limits": limit.limits, "approved_by": limit.approved_by,
        "approved_at": _json_value(limit.approved_at),
    })


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


@spc_studies_bp.post("/api/spc/events/<int:event_id>/ocap")
@auth_required
@require_permission("spc.manage")
@_handle_spc_errors
def create_ocap(current_user, event_id):
    ocap = SpcOcapService.save_ocap(
        event_id, current_user.id, request.get_json(silent=True) or {}
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
    updated = SpcOcapService.save_ocap(
        ocap.event_id, current_user.id, request.get_json(silent=True) or {}
    )
    return _success(serialize_ocap(updated))
