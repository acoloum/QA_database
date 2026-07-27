"""量測設備、校驗證據、狀態事件與來源連結 API。"""

from datetime import date

from flask import Blueprint, jsonify, request

from ..services.msa_equipment_service import MsaEquipmentService
from ..services.msa_errors import MsaValidationError
from ..services.msa_import_service import (
    MsaImportService,
    serialize_import_batch,
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
@_msa_auth_required
@_require_msa_permission("msa.view")
@_handle_msa_errors
def list_import_batches(current_user):
    """列出可追溯的設備匯入批次。"""
    return jsonify({"data": MsaImportService.list_batches(request.args)})


@measurement_equipment_bp.get(
    "/api/measurement-equipment/imports/<int:batch_id>"
)
@_msa_auth_required
@_require_msa_permission("msa.view")
@_handle_msa_errors
def get_import_batch(current_user, batch_id: int):
    """取得指定匯入批次的逐列檢閱證據。"""
    return jsonify({"data": MsaImportService.get_batch(batch_id)})


@measurement_equipment_bp.post(
    "/api/measurement-equipment/imports/preview"
)
@_msa_auth_required
@_require_msa_permission("msa.manage")
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
    return jsonify(
        {"data": serialize_import_batch(batch, include_rows=True)}
    ), 201


@measurement_equipment_bp.post(
    "/api/measurement-equipment/imports/<int:batch_id>/confirm"
)
@_msa_auth_required
@_require_msa_permission("msa.manage")
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
    return jsonify(
        {"data": serialize_import_batch(batch, include_rows=True)}
    )


@measurement_equipment_bp.get("/api/measurement-equipment")
@_msa_auth_required
@_require_msa_permission("msa.view")
@_handle_msa_errors
def list_equipment(current_user):
    """列出目前身分可檢視的量測設備。"""
    return jsonify({"data": MsaEquipmentService.list(request.args)})


@measurement_equipment_bp.post("/api/measurement-equipment")
@_msa_auth_required
@_require_msa_permission("msa.manage")
@_handle_msa_errors
def create_equipment(current_user):
    """建立量測設備主檔。"""
    data = MsaEquipmentService.create(
        request.get_json(silent=True),
        current_user.id,
    )
    return jsonify({"data": data}), 201


@measurement_equipment_bp.get("/api/measurement-equipment/<int:equipment_id>")
@_msa_auth_required
@_require_msa_permission("msa.view")
@_handle_msa_errors
def get_equipment(current_user, equipment_id: int):
    """取得設備主檔與受控證據明細。"""
    return jsonify({"data": MsaEquipmentService.get(equipment_id)})


@measurement_equipment_bp.patch(
    "/api/measurement-equipment/<int:equipment_id>"
)
@_msa_auth_required
@_require_msa_permission("msa.manage")
@_handle_msa_errors
def update_equipment(current_user, equipment_id: int):
    """修改設備可變欄位。"""
    data = MsaEquipmentService.update(
        equipment_id,
        request.get_json(silent=True),
        current_user.id,
    )
    return jsonify({"data": data})


@measurement_equipment_bp.post(
    "/api/measurement-equipment/<int:equipment_id>/calibrations"
)
@_msa_auth_required
@_require_msa_permission("msa.manage")
@_handle_msa_errors
def create_calibration(current_user, equipment_id: int):
    """在單一交易建立 draft 校驗紀錄與補正點。"""
    data = MsaEquipmentService.create_calibration(
        equipment_id,
        request.get_json(silent=True),
        current_user.id,
    )
    return jsonify({"data": data}), 201


@measurement_equipment_bp.post(
    "/api/measurement-equipment/calibrations/"
    "<int:calibration_id>/approve"
)
@_msa_auth_required
@_require_msa_permission("msa.approve")
@_handle_msa_errors
def approve_calibration(current_user, calibration_id: int):
    """核准畫面已確認仍為 draft 的校驗證據。"""
    data = MsaEquipmentService.approve_calibration(
        calibration_id,
        request.get_json(silent=True),
        current_user.id,
    )
    return jsonify({"data": data})


@measurement_equipment_bp.post(
    "/api/measurement-equipment/<int:equipment_id>/status-events"
)
@_msa_auth_required
@_require_msa_permission("msa.manage")
@_handle_msa_errors
def create_status_event(current_user, equipment_id: int):
    """建立設備狀態事件。"""
    data = MsaEquipmentService.create_status_event(
        equipment_id,
        request.get_json(silent=True),
        current_user.id,
    )
    return jsonify({"data": data}), 201


@measurement_equipment_bp.post(
    "/api/measurement-equipment/<int:equipment_id>/links"
)
@_msa_auth_required
@_require_msa_permission("msa.manage")
@_handle_msa_errors
def create_equipment_link(current_user, equipment_id: int):
    """建立或切換 CQI-9 專用設備的正式連結。"""
    data = MsaEquipmentService.create_link(
        equipment_id,
        request.get_json(silent=True),
        current_user.id,
    )
    return jsonify({"data": data}), 201


@measurement_equipment_bp.post(
    "/api/measurement-equipment/<int:equipment_id>/links/"
    "<int:link_id>/retire"
)
@_msa_auth_required
@_require_msa_permission("msa.manage")
@_handle_msa_errors
def retire_equipment_link(current_user, equipment_id: int, link_id: int):
    """退役畫面已確認仍為目前正式狀態的來源連結。"""
    data = MsaEquipmentService.retire_link(
        equipment_id,
        link_id,
        request.get_json(silent=True),
        current_user.id,
    )
    return jsonify({"data": data})
