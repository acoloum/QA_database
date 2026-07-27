"""MSA 判定準則 profile、版本與核准 API。"""

from flask import Blueprint, jsonify, request

from ..services.msa_criteria_service import MsaCriteriaService
from .msa_adapters import (
    handle_msa_errors as _handle_msa_errors,
    msa_auth_required as _msa_auth_required,
    require_msa_permission as _require_msa_permission,
)


msa_bp = Blueprint("msa", __name__)


@msa_bp.get("/api/msa/criteria")
@_msa_auth_required
@_require_msa_permission("msa.view")
@_handle_msa_errors
def list_criteria(current_user):
    """列出目前身分可檢視的準則 profile 與歷史版本。"""
    return jsonify({"data": MsaCriteriaService.list(request.args)})


@msa_bp.post("/api/msa/criteria")
@_msa_auth_required
@_require_msa_permission("msa.manage")
@_handle_msa_errors
def create_criteria_profile(current_user):
    """建立受控判定準則 profile。"""
    profile = MsaCriteriaService.create_profile(
        request.get_json(silent=True),
        actor_id=current_user.id,
    )
    return jsonify(
        {
            "data": MsaCriteriaService.serialize_profile(
                profile,
                include_versions=False,
            )
        }
    ), 201


@msa_bp.post("/api/msa/criteria/<int:profile_id>/versions")
@_msa_auth_required
@_require_msa_permission("msa.manage")
@_handle_msa_errors
def create_criteria_version(current_user, profile_id: int):
    """建立具完整預設補值與驗證的 draft 版本。"""
    version = MsaCriteriaService.create_version(
        profile_id,
        request.get_json(silent=True),
        actor_id=current_user.id,
    )
    return jsonify(
        {"data": MsaCriteriaService.serialize_version(version)}
    ), 201


@msa_bp.post("/api/msa/criteria/versions/<int:version_id>/approve")
@_msa_auth_required
@_require_msa_permission("msa.approve")
@_handle_msa_errors
def approve_criteria_version(current_user, version_id: int):
    """核准畫面確認仍為 draft 的完整準則版本。"""
    version = MsaCriteriaService.approve_version(
        version_id,
        current_user.id,
        payload=request.get_json(silent=True),
    )
    return jsonify(
        {"data": MsaCriteriaService.serialize_version(version)}
    )
