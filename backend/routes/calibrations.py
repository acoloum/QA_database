"""校正紀錄完整生命週期 API。"""

from flask import Blueprint, jsonify, request

from ..services.calibration_service import CalibrationService
from .calibration_adapters import (
    calibration_auth_required,
    handle_calibration_errors,
    require_calibration_permission,
)

calibration_bp = Blueprint("calibrations", __name__)


@calibration_bp.get("/api/calibrations")
@calibration_auth_required
@require_calibration_permission("calibration.view")
@handle_calibration_errors
def list_calibrations(current_user):
    """以受限分頁列出校正紀錄。"""
    return jsonify({"data": CalibrationService.get_list(request.args, actor_id=current_user.id)})


@calibration_bp.post("/api/calibrations")
@calibration_auth_required
@require_calibration_permission("calibration.execute")
@handle_calibration_errors
def create_calibration(current_user):
    """建立詳細校正草稿（需核准模板版本）。"""
    calibration = CalibrationService.create(
        request.get_json(),
        actor_id=current_user.id,
    )
    return jsonify({"data": calibration}), 201


@calibration_bp.get("/api/calibrations/<int:calibration_id>")
@calibration_auth_required
@require_calibration_permission("calibration.view")
@handle_calibration_errors
def get_calibration(current_user, calibration_id: int):
    """取得校正紀錄完整細節（含點位、讀值、快照）。"""
    return jsonify({"data": CalibrationService.get(calibration_id)})


@calibration_bp.patch("/api/calibrations/<int:calibration_id>")
@calibration_auth_required
@require_calibration_permission("calibration.manage")
@handle_calibration_errors
def update_calibration(current_user, calibration_id: int):
    """更新草稿一般欄位（環境條件、外校資訊等）。"""
    calibration = CalibrationService.update(
        calibration_id,
        request.get_json(),
        actor_id=current_user.id,
    )
    return jsonify({"data": calibration})


@calibration_bp.put("/api/calibrations/<int:calibration_id>/readings")
@calibration_auth_required
@require_calibration_permission("calibration.execute")
@handle_calibration_errors
def save_calibration_readings(current_user, calibration_id: int):
    """批次保存原始讀值並由後端重算正式證據。"""
    calibration = CalibrationService.save_readings(
        calibration_id,
        request.get_json(),
        actor_id=current_user.id,
    )
    return jsonify({"data": calibration})


@calibration_bp.post("/api/calibrations/<int:calibration_id>/validate")
@calibration_auth_required
@require_calibration_permission("calibration.manage")
@handle_calibration_errors
def validate_calibration(current_user, calibration_id: int):
    """驗證校正紀錄是否可送審，回傳 blockers。"""
    result = CalibrationService.validate(
        calibration_id,
        request.get_json(),
        actor_id=current_user.id,
    )
    return jsonify({"data": result})


@calibration_bp.post("/api/calibrations/<int:calibration_id>/submit")
@calibration_auth_required
@require_calibration_permission("calibration.manage")
@handle_calibration_errors
def submit_calibration(current_user, calibration_id: int):
    """送審校正紀錄（內校重驗標準器、外校檢查附件、重算比對）。"""
    calibration = CalibrationService.submit(
        calibration_id,
        request.get_json(),
        actor_id=current_user.id,
    )
    return jsonify({"data": calibration})


@calibration_bp.post("/api/calibrations/<int:calibration_id>/approve")
@calibration_auth_required
@require_calibration_permission("calibration.approve")
@handle_calibration_errors
def approve_calibration(current_user, calibration_id: int):
    """核准校正紀錄（職責分離、建立核准快照）。"""
    calibration = CalibrationService.approve(
        calibration_id,
        request.get_json(),
        actor_id=current_user.id,
    )
    return jsonify({"data": calibration})


@calibration_bp.post("/api/calibrations/<int:calibration_id>/reject")
@calibration_auth_required
@require_calibration_permission("calibration.approve")
@handle_calibration_errors
def reject_calibration(current_user, calibration_id: int):
    """退回校正紀錄（保存送審證據、建立後繼草稿）。"""
    calibration = CalibrationService.reject(
        calibration_id,
        request.get_json(),
        actor_id=current_user.id,
    )
    return jsonify({"data": calibration})


@calibration_bp.post("/api/calibrations/<int:calibration_id>/void")
@calibration_auth_required
@require_calibration_permission("calibration.manage")
@handle_calibration_errors
def void_calibration(current_user, calibration_id: int):
    """作廢校正紀錄（需填寫理由）。"""
    calibration = CalibrationService.void(
        calibration_id,
        request.get_json(),
        actor_id=current_user.id,
    )
    return jsonify({"data": calibration})
