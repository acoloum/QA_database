"""量測設備、校驗證據、狀態事件與來源連結 API。"""

from datetime import date
from functools import wraps

from flask import Blueprint, jsonify, request

from ..services.msa_equipment_service import MsaEquipmentService
from ..services.msa_errors import MsaServiceError, MsaValidationError
from ..services.msa_import_service import (
    MsaImportService,
    serialize_import_batch,
)
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


def _msa_import_auth_required(function):
    """只將設備匯入端點的 auth 401 轉成穩定 MSA envelope。"""
    guarded = auth_required(function)

    @wraps(function)
    def wrapped(*args, **kwargs):
        result = guarded(*args, **kwargs)
        if (
            isinstance(result, tuple)
            and len(result) == 2
            and result[1] == 401
        ):
            response = result[0]
            body = (
                response.get_json(silent=True)
                if hasattr(response, "get_json")
                else None
            )
            legacy_message = (
                body.get("error") if isinstance(body, dict) else None
            )
            auth_code_by_message = {
                "缺少認證 Token": "MSA_AUTH_REQUIRED",
                "無效或過期的 Token": "MSA_AUTH_INVALID_TOKEN",
            }
            if (
                not isinstance(legacy_message, str)
                or legacy_message not in auth_code_by_message
            ):
                return result
            return (
                jsonify(
                    {
                        "error": {
                            "code": auth_code_by_message[legacy_message],
                            "message": legacy_message,
                            "details": {},
                        }
                    }
                ),
                401,
            )
        return result

    return wrapped


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


@measurement_equipment_bp.post(
    "/api/measurement-equipment/imports/preview"
)
@_msa_import_auth_required
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
@_msa_import_auth_required
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
