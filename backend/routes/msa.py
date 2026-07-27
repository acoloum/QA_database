"""MSA 判定準則與研究生命週期 API。"""

from flask import Blueprint, jsonify, request

from ..services.msa_criteria_service import MsaCriteriaService
from ..services.msa_design_service import MsaDesignService
from ..services.msa_study_service import MsaStudyService
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


# ---------------------------------------------------------------------------
# 研究
# ---------------------------------------------------------------------------


@msa_bp.get("/api/msa/studies")
@_msa_auth_required
@_require_msa_permission("msa.view")
@_handle_msa_errors
def list_msa_studies(current_user):
    """以有界分頁列出 MSA 研究。"""
    return jsonify({"data": MsaStudyService.list(request.args)})


@msa_bp.post("/api/msa/studies")
@_msa_auth_required
@_require_msa_permission("msa.execute")
@_handle_msa_errors
def create_msa_study(current_user):
    """建立 draft 研究並取得受控研究編號。"""
    study = MsaStudyService.create(
        request.get_json(silent=True),
        actor_id=current_user.id,
    )
    return jsonify({"data": MsaStudyService.serialize(study)}), 201


@msa_bp.get("/api/msa/studies/<int:study_id>")
@_msa_auth_required
@_require_msa_permission("msa.view")
@_handle_msa_errors
def get_msa_study(current_user, study_id: int):
    """取得單一研究的識別資料與目前狀態。"""
    study = MsaStudyService.get(study_id)
    return jsonify({"data": MsaStudyService.serialize(study)})


@msa_bp.patch("/api/msa/studies/<int:study_id>")
@_msa_auth_required
@_require_msa_permission("msa.execute")
@_handle_msa_errors
def update_msa_study(current_user, study_id: int):
    """以畫面帶回的 expected_updated_at 樂觀鎖更新研究。"""
    payload = dict(request.get_json(silent=True) or {})
    expected_updated_at = payload.pop("expected_updated_at", None)
    study = MsaStudyService.update(
        study_id,
        payload,
        actor_id=current_user.id,
        expected_updated_at=expected_updated_at,
    )
    return jsonify({"data": MsaStudyService.serialize(study)})


# ---------------------------------------------------------------------------
# 研究設計與凍結
# ---------------------------------------------------------------------------


def _serialize_plan(plan) -> dict:
    """計畫序列化不包含真實零件識別與參考值，避免經 API 洩漏盲測資訊。"""
    return {
        "id": plan.id,
        "study_id": plan.study_id,
        "plan_version_no": plan.plan_version_no,
        "method_code": plan.method_code,
        "method_version": plan.method_version,
        "design_type": plan.design_type,
        "part_count": plan.part_count,
        "appraiser_count": plan.appraiser_count,
        "trial_count": plan.trial_count,
        "random_seed": plan.random_seed,
        "category_set": plan.category_set,
        "sampling_notes": plan.sampling_notes,
        "environment_notes": plan.environment_notes,
        "equipment_snapshot": plan.equipment_snapshot,
        "criteria_snapshot": plan.criteria_snapshot,
        "plan_hash": plan.plan_hash,
        "frozen_by_id": plan.frozen_by_id,
        "frozen_at": plan.frozen_at.isoformat() if plan.frozen_at else None,
        "part_blind_codes": [part.blind_code for part in plan.parts],
        "appraiser_blind_codes": [
            appraiser.blind_code for appraiser in plan.appraisers
        ],
    }


@msa_bp.post("/api/msa/studies/<int:study_id>/plans")
@_msa_auth_required
@_require_msa_permission("msa.manage")
@_handle_msa_errors
def create_msa_plan(current_user, study_id: int):
    """為草稿研究建立設計版本。"""
    plan = MsaDesignService.create_plan(
        study_id,
        request.get_json(silent=True),
        actor_id=current_user.id,
    )
    return jsonify({"data": _serialize_plan(plan)}), 201


@msa_bp.post("/api/msa/plans/<int:plan_id>/freeze")
@_msa_auth_required
@_require_msa_permission("msa.manage")
@_handle_msa_errors
def freeze_msa_plan(current_user, plan_id: int):
    """重新驗證設備資格後凍結設計，並固定準則與隨機順序快照。"""
    payload = request.get_json(silent=True) or {}
    plan = MsaDesignService.freeze(
        plan_id,
        actor_id=current_user.id,
        expected_plan_hash=payload.get("expected_plan_hash"),
    )
    return jsonify({"data": _serialize_plan(plan)})


@msa_bp.get("/api/msa/plans/<int:plan_id>/tasks")
@_msa_auth_required
@_require_msa_permission("msa.execute")
@_handle_msa_errors
def list_msa_plan_tasks(current_user, plan_id: int):
    """取得只含盲碼的量測任務順序。"""
    return jsonify({"data": {"items": MsaDesignService.tasks(plan_id)}})
