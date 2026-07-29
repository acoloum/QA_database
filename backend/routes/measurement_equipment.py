"""量測設備、校驗證據、狀態事件與來源連結 API。"""

from datetime import date

from flask import Blueprint, jsonify, request

from ..services.measurement_equipment_service import MeasurementEquipmentService
from ..services.msa_errors import MsaValidationError
from ..services.msa_import_service import (
    MsaImportService,
)
from .calibration_adapters import (
    calibration_auth_required as _calibration_auth_required,
    require_calibration_any_permission as _require_calibration_any_permission,
    require_calibration_permission as _require_calibration_permission,
)
from .msa_adapters import (
    handle_msa_errors as _handle_msa_errors,
    msa_auth_required as _msa_auth_required,
    require_msa_permission as _require_msa_permission,
)


measurement_equipment_bp = Blueprint("measurement_equipment", __name__)


def _optional_iso_date(value, *, field: str) -> date | None:
    """解析匯入盤點日；空值由 service 採用目前日期。"""
    if value in (None, ""):
        return None
    try:
        return date.fromisoformat(str(value))
    except ValueError as error:
        raise MsaValidationError(
            "MSA_IMPORT_DATE_INVALID",
            f"{field} 必須是 ISO 日期",
            details={"field": field, "value": value},
        ) from error


@measurement_equipment_bp.get(
    "/api/measurement-equipment/imports"
)
@_calibration_auth_required
@_require_calibration_permission("calibration.view")
@_handle_msa_errors
def list_import_batches(current_user):
    """列出可追溯的設備匯入批次。"""
    return jsonify({"data": MsaImportService.list_batches(request.args)})


@measurement_equipment_bp.get(
    "/api/measurement-equipment/imports/<int:batch_id>"
)
@_calibration_auth_required
@_require_calibration_permission("calibration.view")
@_handle_msa_errors
def get_import_batch(current_user, batch_id: int):
    """取得指定匯入批次的逐列檢閱證據。"""
    return jsonify({
        "data": MsaImportService.get_batch(batch_id, request.args)
    })


@measurement_equipment_bp.post(
    "/api/measurement-equipment/imports/preview"
)
@_calibration_auth_required
@_require_calibration_permission("calibration.manage")
@_handle_msa_errors
def preview_import(current_user):
    """只建立匯入批次與逐列預覽，不建立正式設備。"""
    uploaded_file = request.files.get("file")
    batch = MsaImportService.preview(
        uploaded_file,
        actor_id=current_user.id,
        as_of=_optional_iso_date(
            request.args.get("as_of"),
            field="as_of",
        ),
    )
    return jsonify({"data": MsaImportService.get_batch(batch.id)}), 201


@measurement_equipment_bp.post(
    "/api/measurement-equipment/imports/<int:batch_id>/confirm"
)
@_calibration_auth_required
@_require_calibration_permission("calibration.manage")
@_handle_msa_errors
def confirm_import(current_user, batch_id: int):
    """以列鎖與整批交易確認預覽結果。"""
    payload = request.get_json(silent=True) or {}
    if not isinstance(payload, dict):
        raise MsaValidationError(
            "MSA_PAYLOAD_INVALID", "請求內容必須是 JSON 物件"
        )
    batch = MsaImportService.confirm(
        batch_id,
        current_user.id,
        resolutions=payload.get("resolutions", {}),
        confirmation_date=_optional_iso_date(
            payload.get("confirmation_date"),
            field="confirmation_date",
        ),
    )
    return jsonify({"data": MsaImportService.get_batch(batch.id)})


@measurement_equipment_bp.get("/api/measurement-equipment")
@_calibration_auth_required
@_require_calibration_any_permission("calibration.view", "msa.view")
@_handle_msa_errors
def list_equipment(current_user):
    """列出目前身分可檢視的量測設備。"""
    return jsonify({"data": MeasurementEquipmentService.list(request.args)})


@measurement_equipment_bp.post("/api/measurement-equipment")
@_calibration_auth_required
@_require_calibration_permission("calibration.manage")
@_handle_msa_errors
def create_equipment(current_user):
    """建立量測設備主檔。"""
    data = MeasurementEquipmentService.create(
        request.get_json(silent=True),
        current_user.id,
    )
    return jsonify({"data": data}), 201


@measurement_equipment_bp.get("/api/measurement-equipment/<int:equipment_id>")
@_calibration_auth_required
@_require_calibration_permission("calibration.view")
@_handle_msa_errors
def get_equipment(current_user, equipment_id: int):
    """取得設備主檔與受控證據明細。"""
    return jsonify({"data": MeasurementEquipmentService.get(equipment_id)})


@measurement_equipment_bp.patch(
    "/api/measurement-equipment/<int:equipment_id>"
)
@_calibration_auth_required
@_require_calibration_permission("calibration.manage")
@_handle_msa_errors
def update_equipment(current_user, equipment_id: int):
    """修改設備可變欄位。"""
    data = MeasurementEquipmentService.update(
        equipment_id,
        request.get_json(silent=True),
        current_user.id,
    )
    return jsonify({"data": data})


@measurement_equipment_bp.post(
    "/api/measurement-equipment/<int:equipment_id>/calibrations"
)
@_msa_auth_required
def create_calibration(current_user, equipment_id: int):
    """拒絕已退役的簡易校正建立介面。"""
    return _legacy_calibration_retired()


@measurement_equipment_bp.post(
    "/api/measurement-equipment/calibrations/"
    "<int:calibration_id>/approve"
)
@_msa_auth_required
def approve_calibration(current_user, calibration_id: int):
    """拒絕已退役的簡易校正核准介面。"""
    return _legacy_calibration_retired()


@measurement_equipment_bp.post(
    "/api/measurement-equipment/<int:equipment_id>/status-events"
)
@_calibration_auth_required
@_require_calibration_permission("calibration.manage")
@_handle_msa_errors
def create_status_event(current_user, equipment_id: int):
    """建立設備狀態事件。"""
    data = MeasurementEquipmentService.create_status_event(
        equipment_id,
        request.get_json(silent=True),
        current_user.id,
    )
    return jsonify({"data": data}), 201


@measurement_equipment_bp.post(
    "/api/measurement-equipment/<int:equipment_id>/links"
)
@_calibration_auth_required
@_require_calibration_permission("calibration.manage")
@_handle_msa_errors
def create_equipment_link(current_user, equipment_id: int):
    """建立或切換 CQI-9 專用設備的正式連結。"""
    data = MeasurementEquipmentService.create_link(
        equipment_id,
        request.get_json(silent=True),
        current_user.id,
    )
    return jsonify({"data": data}), 201


@measurement_equipment_bp.post(
    "/api/measurement-equipment/<int:equipment_id>/links/"
    "<int:link_id>/retire"
)
@_calibration_auth_required
@_require_calibration_permission("calibration.manage")
@_handle_msa_errors
def retire_equipment_link(current_user, equipment_id: int, link_id: int):
    """退役畫面已確認仍為目前正式狀態的來源連結。"""
    data = MeasurementEquipmentService.retire_link(
        equipment_id,
        link_id,
        request.get_json(silent=True),
        current_user.id,
    )
    return jsonify({"data": data})


def _legacy_calibration_retired():
    """提供舊 MSA 簡易校正端點的固定退役錯誤契約。"""
    return jsonify({
        "error": {
            "code": "CALIBRATION_LEGACY_ENDPOINT_RETIRED",
            "message": "舊版簡易校正介面已退役，請使用校正登錄流程",
            "details": {},
        }
    }), 410
