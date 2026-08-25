"""受控校正模板與版本工作流 API。"""

from flask import Blueprint, jsonify, request

from ..services.calibration_template_service import (
    CalibrationTemplateService,
)
from .calibration_adapters import (
    calibration_auth_required,
    handle_calibration_errors,
    require_calibration_permission,
)


calibration_template_bp = Blueprint("calibration_templates", __name__)


@calibration_template_bp.get("/api/calibration-templates")
@calibration_auth_required
@require_calibration_permission("calibration.view")
@handle_calibration_errors
def list_calibration_templates(current_user):
    """以受限分頁列出校正模板及受控版本。"""
    return jsonify({"data": CalibrationTemplateService.get_list(request.args)})


@calibration_template_bp.post("/api/calibration-templates")
@calibration_auth_required
@require_calibration_permission("calibration.manage")
@handle_calibration_errors
def create_calibration_template(current_user):
    """建立校正模板的穩定識別。"""
    template = CalibrationTemplateService.create(
        request.get_json(),
        actor_id=current_user.id,
    )
    return jsonify({"data": template}), 201


@calibration_template_bp.get(
    "/api/calibration-templates/<int:template_id>"
)
@calibration_auth_required
@require_calibration_permission("calibration.view")
@handle_calibration_errors
def get_calibration_template(current_user, template_id: int):
    """取得模板、歷史版本及逐點受控規則。"""
    return jsonify({"data": CalibrationTemplateService.get(template_id)})


@calibration_template_bp.post(
    "/api/calibration-templates/<int:template_id>/versions"
)
@calibration_auth_required
@require_calibration_permission("calibration.manage")
@handle_calibration_errors
def create_calibration_template_version(current_user, template_id: int):
    """建立模板的下一個 draft 版本。"""
    version = CalibrationTemplateService.create_version(
        template_id,
        request.get_json(),
        actor_id=current_user.id,
    )
    return jsonify({"data": version}), 201


@calibration_template_bp.patch(
    "/api/calibration-template-versions/<int:version_id>"
)
@calibration_auth_required
@require_calibration_permission("calibration.manage")
@handle_calibration_errors
def update_calibration_template_version(current_user, version_id: int):
    """以 expected_version 更新仍為 draft 的完整版本證據。"""
    version = CalibrationTemplateService.update_version(
        version_id,
        request.get_json(),
        actor_id=current_user.id,
    )
    return jsonify({"data": version})


@calibration_template_bp.post(
    "/api/calibration-template-versions/<int:version_id>/submit"
)
@calibration_auth_required
@require_calibration_permission("calibration.manage")
@handle_calibration_errors
def submit_calibration_template_version(current_user, version_id: int):
    """送審完整且至少含一個必要校正點的 draft 版本。"""
    version = CalibrationTemplateService.submit_version(
        version_id,
        request.get_json(),
        actor_id=current_user.id,
    )
    return jsonify({"data": version})


@calibration_template_bp.post(
    "/api/calibration-template-versions/<int:version_id>/approve"
)
@calibration_auth_required
@require_calibration_permission("calibration.approve")
@handle_calibration_errors
def approve_calibration_template_version(current_user, version_id: int):
    """由非建立者、非送審者核准 submitted 版本。"""
    version = CalibrationTemplateService.approve_version(
        version_id,
        request.get_json(),
        actor_id=current_user.id,
    )
    return jsonify({"data": version})


@calibration_template_bp.post(
    "/api/calibration-template-versions/<int:version_id>/reject"
)
@calibration_auth_required
@require_calibration_permission("calibration.approve")
@handle_calibration_errors
def reject_calibration_template_version(current_user, version_id: int):
    """保存退回理由並結束 submitted 版本。"""
    version = CalibrationTemplateService.reject_version(
        version_id,
        request.get_json(),
        actor_id=current_user.id,
    )
    return jsonify({"data": version})
