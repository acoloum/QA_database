"""MSA 判定準則與研究生命週期 API。"""

from flask import Blueprint, jsonify, request, send_file

from ..services.msa_analysis_service import MsaAnalysisService
from ..services.msa_criteria_service import MsaCriteriaService
from ..services.msa_design_service import MsaDesignService
from ..services.msa_observation_import_service import (
    MsaObservationImportService,
)
from ..services.msa_observation_service import MsaObservationService
from ..services.msa_report import MsaReportService
from ..services.msa_restudy_service import MsaRestudyService
from ..services.msa_study_service import MsaStudyService
from ..services.msa_workflow_service import MsaWorkflowService
from .msa_adapters import (
    handle_msa_errors as _handle_msa_errors,
    has_msa_permission as _has_msa_permission,
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


# ---------------------------------------------------------------------------
# 觀測收集與匯入
# ---------------------------------------------------------------------------


def _serialize_observation(observation) -> dict:
    return {
        "id": observation.id,
        "plan_version_id": observation.plan_version_id,
        "requested_order": observation.requested_order,
        "actual_entry_order": observation.actual_entry_order,
        "trial_no": observation.trial_no,
        "numeric_value": (
            str(observation.numeric_value)
            if observation.numeric_value is not None else None
        ),
        "attribute_value": observation.attribute_value,
        "measured_at": (
            observation.measured_at.isoformat()
            if observation.measured_at else None
        ),
        "source": observation.source,
        "entered_by_id": observation.entered_by_id,
        "is_effective": observation.is_effective,
        "supersedes_id": observation.supersedes_id,
        "correction_reason": observation.correction_reason,
    }


def _serialize_import_batch(batch) -> dict:
    stats = dict(batch.stats or {})
    # 逐列解析結果只在服務內部使用，不對外暴露以免洩漏盲測對應
    stats.pop("rows", None)
    return {
        "id": batch.id,
        "plan_version_id": batch.plan_version_id,
        "file_name": batch.file_name,
        "file_sha256": batch.file_sha256,
        "plan_hash": batch.plan_hash,
        "status": batch.status,
        "issues": batch.issues,
        "stats": stats,
    }


@msa_bp.post("/api/msa/plans/<int:plan_id>/observations")
@_msa_auth_required
@_require_msa_permission("msa.execute")
@_handle_msa_errors
def record_msa_observation(current_user, plan_id: int):
    """記錄一筆盲測讀值；代輸入需要 msa.manage。"""
    observation = MsaObservationService.record(
        plan_id,
        request.get_json(silent=True),
        actor_id=current_user.id,
        can_manage=_has_msa_permission(current_user, "msa.manage"),
    )
    return jsonify({"data": _serialize_observation(observation)}), 201


@msa_bp.post("/api/msa/observations/<int:observation_id>/corrections")
@_msa_auth_required
@_require_msa_permission("msa.manage")
@_handle_msa_errors
def correct_msa_observation(current_user, observation_id: int):
    """以後繼紀錄修正觀測；原紀錄只作廢不改值。"""
    successor = MsaObservationService.correct(
        observation_id,
        request.get_json(silent=True),
        actor_id=current_user.id,
    )
    return jsonify({"data": _serialize_observation(successor)}), 201


@msa_bp.post("/api/msa/plans/<int:plan_id>/imports/preview")
@_msa_auth_required
@_require_msa_permission("msa.manage")
@_handle_msa_errors
def preview_msa_observation_import(current_user, plan_id: int):
    """解析 Excel 並逐格回報問題，不寫入任何觀測。"""
    batch = MsaObservationImportService.preview(
        plan_id,
        request.files.get("file"),
        actor_id=current_user.id,
    )
    return jsonify({"data": _serialize_import_batch(batch)}), 201


@msa_bp.post(
    "/api/msa/plans/<int:plan_id>/imports/<int:batch_id>/confirm"
)
@_msa_auth_required
@_require_msa_permission("msa.manage")
@_handle_msa_errors
def confirm_msa_observation_import(current_user, plan_id: int, batch_id: int):
    """在單一交易內寫入批次中無問題的列。"""
    batch = MsaObservationImportService.confirm(
        batch_id, actor_id=current_user.id,
    )
    return jsonify({"data": _serialize_import_batch(batch)})


@msa_bp.post("/api/msa/plans/<int:plan_id>/validate")
@_msa_auth_required
@_require_msa_permission("msa.execute")
@_handle_msa_errors
def validate_msa_plan_data(current_user, plan_id: int):
    """比對盲測矩陣與有效讀值，完整時將研究推進到可分析。"""
    return jsonify({
        "data": MsaObservationService.validate(
            plan_id, actor_id=current_user.id,
        )
    })


# ---------------------------------------------------------------------------
# 分析與結果
# ---------------------------------------------------------------------------


def _serialize_result(result) -> dict:
    return {
        "id": result.id,
        "study_id": result.study_id,
        "plan_version_id": result.plan_version_id,
        "result_version_no": result.result_version_no,
        "method_code": result.method_code,
        "method_version": result.method_version,
        "code_version": result.code_version,
        "data_hash": result.data_hash,
        "applicability_result": result.applicability_result,
        "statistics": result.statistics,
        "chart_data": result.chart_data,
        "criteria_snapshot": result.criteria_snapshot,
        "conclusion": result.conclusion,
        "warnings": result.warnings,
        "blockers": result.blockers,
        "status": result.status,
        "created_by_id": result.created_by_id,
        "created_at": (
            result.created_at.isoformat() if result.created_at else None
        ),
    }


@msa_bp.post("/api/msa/plans/<int:plan_id>/analyze")
@_msa_auth_required
@_require_msa_permission("msa.execute")
@_handle_msa_errors
def analyze_msa_plan(current_user, plan_id: int):
    """以受控方法與凍結準則產生不可變結果版本。"""
    payload = request.get_json(silent=True) or {}
    result = MsaAnalysisService.analyze(
        plan_id,
        actor_id=current_user.id,
        expected_plan_hash=payload.get("expected_plan_hash"),
    )
    return jsonify({"data": _serialize_result(result)}), 201


# ---------------------------------------------------------------------------
# 送審與核准
# ---------------------------------------------------------------------------


@msa_bp.post("/api/msa/results/<int:result_id>/submit")
@_msa_auth_required
@_require_msa_permission("msa.manage")
@_handle_msa_errors
def submit_msa_result(current_user, result_id: int):
    """送審結果版本；條件接受必須附處置措施與期限。"""
    result = MsaWorkflowService.submit(
        result_id, request.get_json(silent=True), actor_id=current_user.id,
    )
    return jsonify({"data": _serialize_result(result)})


@msa_bp.post("/api/msa/results/<int:result_id>/approve")
@_msa_auth_required
@_require_msa_permission("msa.approve")
@_handle_msa_errors
def approve_msa_result(current_user, result_id: int):
    """核准結果版本；參與過本研究者一律不得核准。"""
    result = MsaWorkflowService.approve(
        result_id, request.get_json(silent=True), actor_id=current_user.id,
    )
    return jsonify({"data": _serialize_result(result)})


@msa_bp.post("/api/msa/results/<int:result_id>/reject")
@_msa_auth_required
@_require_msa_permission("msa.approve")
@_handle_msa_errors
def reject_msa_result(current_user, result_id: int):
    """退回結果版本；需重新分析才能再次送審。"""
    result = MsaWorkflowService.reject(
        result_id, request.get_json(silent=True), actor_id=current_user.id,
    )
    return jsonify({"data": _serialize_result(result)})


@msa_bp.post("/api/msa/results/<int:result_id>/void")
@_msa_auth_required
@_require_msa_permission("msa.approve")
@_handle_msa_errors
def void_msa_result(current_user, result_id: int):
    """作廢已核准的結果版本；統計證據本身仍不可修改。"""
    result = MsaWorkflowService.void(
        result_id, request.get_json(silent=True), actor_id=current_user.id,
    )
    return jsonify({"data": _serialize_result(result)})


# ---------------------------------------------------------------------------
# 再研究要求
# ---------------------------------------------------------------------------


@msa_bp.get("/api/msa/restudy-requests")
@_msa_auth_required
@_require_msa_permission("msa.view")
@_handle_msa_errors
def list_msa_restudy_requests(current_user):
    """列出待處理與進行中的再研究要求。"""
    return jsonify({"data": MsaRestudyService.list(request.args)})


@msa_bp.post("/api/msa/restudy-requests")
@_msa_auth_required
@_require_msa_permission("msa.manage")
@_handle_msa_errors
def create_msa_restudy_request(current_user):
    """人工登錄方法、夾治具、軟體、人員或規格改變等觸發。"""
    created = MsaRestudyService.create_manual(
        request.get_json(silent=True), actor_id=current_user.id,
    )
    return jsonify({"data": MsaRestudyService.serialize(created)}), 201


@msa_bp.post("/api/msa/restudy-requests/<int:request_id>/start")
@_msa_auth_required
@_require_msa_permission("msa.manage")
@_handle_msa_errors
def start_msa_restudy_request(current_user, request_id: int):
    """由再研究要求建立新的 draft 研究；不複製任何舊觀測。"""
    started = MsaRestudyService.start(request_id, actor_id=current_user.id)
    return jsonify({"data": MsaRestudyService.serialize(started)})


# ---------------------------------------------------------------------------
# 正式報告
# ---------------------------------------------------------------------------


@msa_bp.get("/api/msa/results/<int:version_id>/report.xlsx")
@_msa_auth_required
@_require_msa_permission("msa.view")
@_handle_msa_errors
def download_msa_excel(current_user, version_id: int):
    """由已保存的結果版本重建 Excel 報告；不重新分析。"""
    output = MsaReportService.generate_excel(version_id)
    return send_file(
        output,
        as_attachment=True,
        download_name=f"MSA_{version_id}.xlsx",
        mimetype=(
            "application/vnd.openxmlformats-officedocument"
            ".spreadsheetml.sheet"
        ),
    )
