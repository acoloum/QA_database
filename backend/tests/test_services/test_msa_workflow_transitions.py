"""MSA 送審、職責分離核准、退回與作廢測試。"""

from datetime import date, timedelta

import pytest

from backend.models import (
    EquipmentCalibrationRecord,
    MeasurementEquipment,
    MsaCriteriaProfile,
    MsaCriteriaVersion,
    MsaWorkflowDecision,
    User,
)
from backend.services.msa_analysis_service import MsaAnalysisService
from backend.services.msa_design_service import MsaDesignService
from backend.services.msa_errors import (
    MsaConflict,
    MsaForbidden,
    MsaValidationError,
)
from backend.services.msa_observation_service import MsaObservationService
from backend.services.msa_study_service import MsaStudyService
from backend.services.msa_workflow_service import MsaWorkflowService


@pytest.fixture
def people(db_session):
    users = {
        name: User(username=f"msa_wf_{name}", password="x")
        for name in ("creator", "executor", "entry", "approver", "admin")
    }
    users["admin"].role = "admin"
    db_session.add_all(users.values())
    db_session.commit()
    return users


_READINGS = {
    ("P01", "A01"): [10.001, 10.002, 10.001],
    ("P01", "A02"): [10.003, 10.002, 10.003],
    ("P02", "A01"): [10.301, 10.302, 10.301],
    ("P02", "A02"): [10.303, 10.302, 10.303],
    ("P03", "A01"): [10.601, 10.602, 10.601],
    ("P03", "A02"): [10.603, 10.602, 10.603],
}


def _analyzed_result(db_session, people, *, thresholds=None, entry_user=None):
    profile = MsaCriteriaProfile(name=f"工作流準則-{id(people)}")
    db_session.add(profile)
    db_session.flush()
    version = MsaCriteriaVersion(
        profile_id=profile.id, version_no=1, method_version="MSA4-1.0",
        effective_date=date(2026, 1, 1),
        thresholds=thresholds or {
            "grr_accept_max": 10.0, "grr_conditional_max": 30.0,
            "ndc_min": 5, "alpha": 0.05,
        },
        status="approved",
    )
    db_session.add(version)
    db_session.flush()
    profile.current_version_id = version.id
    db_session.commit()

    equipment = MeasurementEquipment(
        equipment_no=f"EQ-WF-{version.id}", name="量具", status="active",
        calibration_type="external", resolution="0.001", unit="mm",
    )
    db_session.add(equipment)
    db_session.flush()
    db_session.add(EquipmentCalibrationRecord(
        equipment_id=equipment.id, calibration_type="external",
        calibration_date=date.today() - timedelta(days=10),
        next_due_date=date.today() + timedelta(days=300),
        result="pass", status="approved",
    ))
    db_session.commit()

    study = MsaStudyService.create(
        {
            "study_type": "grr_anova",
            "measurement_purpose": "product_control",
            "characteristic": "外徑", "unit": "mm",
            "lsl": 9.5, "usl": 11.5,
            "criteria_profile_id": profile.id,
            "primary_executor_id": people["executor"].id,
        },
        actor_id=people["creator"].id,
    )
    plan = MsaDesignService.create_plan(
        study.id,
        {
            "method_code": "MSA4_GRR_ANOVA_1_0",
            "part_count": 3, "appraiser_count": 2, "trial_count": 3,
            "random_seed": 7, "percent_basis": "tolerance",
            "equipment": [
                {"equipment_id": equipment.id, "role": "primary_gauge"}
            ],
            "parts": [{"part_identifier": f"件-{i}"} for i in range(1, 4)],
            "appraisers": [{"name": "甲"}, {"name": "乙"}],
        },
        actor_id=people["creator"].id,
    )
    frozen = MsaDesignService.freeze(plan.id, actor_id=people["creator"].id)

    part_codes = {part.id: part.blind_code for part in frozen.parts}
    appraiser_codes = {r.id: r.blind_code for r in frozen.appraisers}
    recorder = entry_user or people["entry"]
    for item in frozen.randomized_order:
        key = (
            part_codes[item["part_id"]], appraiser_codes[item["appraiser_id"]],
        )
        MsaObservationService.record(
            frozen.id,
            {
                "task_order": item["requested_order"],
                "numeric_value": str(_READINGS[key][item["trial_no"] - 1]),
            },
            actor_id=recorder.id, can_manage=True,
        )
    MsaObservationService.validate(frozen.id, actor_id=recorder.id)
    return MsaAnalysisService.analyze(
        frozen.id, actor_id=people["executor"].id,
    )


@pytest.fixture
def analyzed_result(db_session, people):
    return _analyzed_result(db_session, people)


@pytest.fixture
def submitted_result(db_session, people, analyzed_result):
    return MsaWorkflowService.submit(
        analyzed_result.id,
        {"expected_status": "analyzed", "reason": "統計完成，送請核准"},
        actor_id=people["executor"].id,
    )


# ---------------------------------------------------------------------------
# 狀態轉移
# ---------------------------------------------------------------------------


def test_submit_moves_result_and_study_to_submitted(
    db_session, people, analyzed_result,
):
    result = MsaWorkflowService.submit(
        analyzed_result.id,
        {"expected_status": "analyzed", "reason": "統計完成"},
        actor_id=people["executor"].id,
    )

    db_session.refresh(result.study)
    assert result.status == "submitted"
    assert result.study.status == "submitted"
    decision = MsaWorkflowDecision.query.filter_by(
        result_version_id=result.id, action="submit",
    ).one()
    assert decision.reason == "統計完成"


def test_approve_requires_expected_status(
    db_session, people, submitted_result,
):
    with pytest.raises(MsaConflict) as error:
        MsaWorkflowService.approve(
            submitted_result.id,
            {"expected_status": "analyzed", "reason": "核准"},
            actor_id=people["approver"].id,
        )

    assert error.value.code == "MSA_VERSION_CONFLICT"


def test_concurrent_approval_uses_expected_status(
    db_session, people, submitted_result,
):
    MsaWorkflowService.approve(
        submitted_result.id,
        {"expected_status": "submitted", "reason": "核准"},
        actor_id=people["approver"].id,
    )

    with pytest.raises(MsaConflict) as error:
        MsaWorkflowService.approve(
            submitted_result.id,
            {"expected_status": "submitted", "reason": "重複核准"},
            actor_id=people["approver"].id,
        )

    assert error.value.code == "MSA_VERSION_CONFLICT"


def test_reject_returns_result_to_rejected(
    db_session, people, submitted_result,
):
    result = MsaWorkflowService.reject(
        submitted_result.id,
        {"expected_status": "submitted", "reason": "抽樣代表性不足"},
        actor_id=people["approver"].id,
    )

    db_session.refresh(result.study)
    assert result.status == "rejected"
    assert result.study.status == "rejected"


def test_rejected_result_cannot_be_moved_back_to_analyzed(
    db_session, people, submitted_result,
):
    MsaWorkflowService.reject(
        submitted_result.id,
        {"expected_status": "submitted", "reason": "退回"},
        actor_id=people["approver"].id,
    )

    with pytest.raises(MsaConflict) as error:
        MsaWorkflowService.submit(
            submitted_result.id,
            {"expected_status": "rejected", "reason": "再送一次"},
            actor_id=people["executor"].id,
        )

    assert error.value.code == "MSA_VERSION_CONFLICT"


def test_only_approved_result_can_be_voided(
    db_session, people, submitted_result,
):
    with pytest.raises(MsaConflict):
        MsaWorkflowService.void(
            submitted_result.id,
            {"expected_status": "submitted", "reason": "作廢"},
            actor_id=people["approver"].id,
        )

    approved = MsaWorkflowService.approve(
        submitted_result.id,
        {"expected_status": "submitted", "reason": "核准"},
        actor_id=people["approver"].id,
    )
    voided = MsaWorkflowService.void(
        approved.id,
        {"expected_status": "approved", "reason": "設備重大調整，結論失效"},
        actor_id=people["approver"].id,
    )

    assert voided.status == "voided"


def test_every_action_requires_a_reason(
    db_session, people, analyzed_result,
):
    with pytest.raises(MsaValidationError) as error:
        MsaWorkflowService.submit(
            analyzed_result.id,
            {"expected_status": "analyzed", "reason": "   "},
            actor_id=people["executor"].id,
        )

    assert error.value.code == "MSA_WORKFLOW_REASON_REQUIRED"


# ---------------------------------------------------------------------------
# 職責分離
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "role", ["creator", "executor", "entry"],
)
def test_participants_cannot_approve_their_own_study(
    db_session, people, submitted_result, role,
):
    with pytest.raises(MsaForbidden) as error:
        MsaWorkflowService.approve(
            submitted_result.id,
            {"expected_status": "submitted", "reason": "核准"},
            actor_id=people[role].id,
        )

    assert error.value.code == "MSA_SELF_APPROVAL_FORBIDDEN"


def test_admin_cannot_bypass_separation_of_duties(db_session, people):
    """admin 若參與過研究，同樣不得核准。"""
    result = _analyzed_result(
        db_session, people, entry_user=people["admin"],
    )
    submitted = MsaWorkflowService.submit(
        result.id,
        {"expected_status": "analyzed", "reason": "送審"},
        actor_id=people["executor"].id,
    )

    with pytest.raises(MsaForbidden) as error:
        MsaWorkflowService.approve(
            submitted.id,
            {"expected_status": "submitted", "reason": "管理員核准"},
            actor_id=people["admin"].id,
        )

    assert error.value.code == "MSA_SELF_APPROVAL_FORBIDDEN"
    assert "data_entry" in error.value.details["conflicting_roles"]


def test_independent_approver_passes_and_records_the_check(
    db_session, people, submitted_result,
):
    result = MsaWorkflowService.approve(
        submitted_result.id,
        {"expected_status": "submitted", "reason": "證據充分"},
        actor_id=people["approver"].id,
    )

    decision = MsaWorkflowDecision.query.filter_by(
        result_version_id=result.id, action="approve",
    ).one()
    assert decision.separation_check["passed"] is True
    assert decision.separation_check["checked_actor_id"] == (
        people["approver"].id
    )
    assert set(decision.separation_check["disallowed_roles_checked"]) == {
        "creator", "primary_executor", "result_author", "data_entry",
    }


def test_disallowed_approvers_include_every_participating_role(
    db_session, people, submitted_result,
):
    disallowed = MsaWorkflowService.disallowed_approver_ids(submitted_result)

    assert "creator" in disallowed[people["creator"].id]
    assert "primary_executor" in disallowed[people["executor"].id]
    assert "data_entry" in disallowed[people["entry"].id]
    assert people["approver"].id not in disallowed


# ---------------------------------------------------------------------------
# 條件接受
# ---------------------------------------------------------------------------


def test_conditional_result_requires_actions_and_due_date(
    db_session, people,
):
    result = _analyzed_result(
        db_session, people,
        thresholds={
            "grr_accept_max": 0.001, "grr_conditional_max": 50.0,
            "ndc_min": 5, "alpha": 0.05,
        },
    )
    assert result.conclusion["system_disposition"] == (
        "conditionally_acceptable"
    )

    with pytest.raises(MsaValidationError) as missing_actions:
        MsaWorkflowService.submit(
            result.id,
            {"expected_status": "analyzed", "reason": "條件接受"},
            actor_id=people["executor"].id,
        )
    assert missing_actions.value.code == "MSA_CONDITIONAL_ACTIONS_REQUIRED"

    with pytest.raises(MsaValidationError) as missing_due:
        MsaWorkflowService.submit(
            result.id,
            {
                "expected_status": "analyzed", "reason": "條件接受",
                "actions": ["加嚴抽樣"],
            },
            actor_id=people["executor"].id,
        )
    assert missing_due.value.code == "MSA_CONDITIONAL_DUE_DATE_REQUIRED"


def test_conditional_submission_records_actions_and_due_date(
    db_session, people,
):
    result = _analyzed_result(
        db_session, people,
        thresholds={
            "grr_accept_max": 0.001, "grr_conditional_max": 50.0,
            "ndc_min": 5, "alpha": 0.05,
        },
    )

    submitted = MsaWorkflowService.submit(
        result.id,
        {
            "expected_status": "analyzed",
            "reason": "條件接受，已排定改善",
            "actions": ["加嚴抽樣", "三個月內更換量具"],
            "due_date": "2026-10-31",
        },
        actor_id=people["executor"].id,
    )

    decision = MsaWorkflowDecision.query.filter_by(
        result_version_id=submitted.id, action="submit",
    ).one()
    assert decision.extra_data["actions"] == ["加嚴抽樣", "三個月內更換量具"]
    assert decision.extra_data["due_date"] == "2026-10-31"


def test_acceptable_result_does_not_require_conditional_fields(
    db_session, people, analyzed_result,
):
    submitted = MsaWorkflowService.submit(
        analyzed_result.id,
        {"expected_status": "analyzed", "reason": "合格，送審"},
        actor_id=people["executor"].id,
    )

    assert submitted.status == "submitted"


def test_unknown_payload_fields_are_rejected(
    db_session, people, analyzed_result,
):
    with pytest.raises(MsaValidationError) as error:
        MsaWorkflowService.submit(
            analyzed_result.id,
            {
                "expected_status": "analyzed", "reason": "送審",
                "status": "approved",
            },
            actor_id=people["executor"].id,
        )

    assert error.value.code == "MSA_UNKNOWN_FIELDS"
