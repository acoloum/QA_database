"""量測設備、校驗證據、狀態事件與來源連結 API。"""

from functools import wraps

from flask import Blueprint, jsonify, request

from ..services.msa_equipment_service import MsaEquipmentService
from ..services.msa_errors import MsaServiceError
from ..utils import auth_required, require_permission


measurement_equipment_bp = Blueprint("measurement_equipment", __name__)


def _handle_msa_errors(function):
    """將 MSA service 例外轉為穩定且可程式判定的錯誤 envelope。"""

    @wraps(function)
    def wrapped(*args, **kwargs):
        try:
            return function(*args, **kwargs)
        except MsaServiceError as error:
            return (
                jsonify(
                    {
                        "error": {
                            "code": error.code,
                            "message": error.message,
                            "details": error.details,
                        }
                    }
                ),
                error.status_code,
            )

    return wrapped


def _require_msa_permission(permission: str):
    """沿用共用權限判定，並統一 MSA API 的錯誤 envelope。"""

    def decorator(function):
        guarded = require_permission(permission)(function)

        @wraps(function)
        def wrapped(current_user, *args, **kwargs):
            result = guarded(current_user, *args, **kwargs)
            if isinstance(result, tuple) and len(result) == 2:
                _response, status_code = result
                if status_code == 403:
                    return (
                        jsonify(
                            {
                                "error": {
                                    "code": "MSA_PERMISSION_DENIED",
                                    "message": "權限不足",
                                    "details": {"permission": permission},
                                }
                            }
                        ),
                        403,
                    )
                if status_code == 401:
                    return (
                        jsonify(
                            {
                                "error": {
                                    "code": "MSA_USER_NOT_FOUND",
                                    "message": "使用者不存在",
                                    "details": {},
                                }
                            }
                        ),
                        401,
                    )
            return result

        return wrapped

    return decorator


@measurement_equipment_bp.get("/api/measurement-equipment")
@auth_required
@_require_msa_permission("msa.view")
@_handle_msa_errors
def list_equipment(current_user):
    """列出目前身分可檢視的量測設備。"""
    return jsonify({"data": MsaEquipmentService.list(request.args)})


@measurement_equipment_bp.post("/api/measurement-equipment")
@auth_required
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
@auth_required
@_require_msa_permission("msa.view")
@_handle_msa_errors
def get_equipment(current_user, equipment_id: int):
    """取得設備主檔與受控證據明細。"""
    return jsonify({"data": MsaEquipmentService.get(equipment_id)})


@measurement_equipment_bp.patch(
    "/api/measurement-equipment/<int:equipment_id>"
)
@auth_required
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
@auth_required
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
@auth_required
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
@auth_required
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
@auth_required
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
@auth_required
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
