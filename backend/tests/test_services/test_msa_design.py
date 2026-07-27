"""MSA 研究設計、設備快照、盲碼與凍結流程測試。"""

from datetime import date, timedelta

import pytest

from backend.extensions import db
from backend.models import (
    EquipmentCalibrationRecord,
    MeasurementEquipment,
    MsaCriteriaProfile,
    MsaCriteriaVersion,
    MsaPlanVersion,
    MsaWorkflowDecision,
    User,
)
from backend.services.msa_design_service import MsaDesignService
from backend.services.msa_errors import MsaConflict, MsaValidationError
from backend.services.msa_study_service import MsaStudyService


@pytest.fixture
def msa_manager(db_session):
    user = User(username="msa_design_manager", password="x")
    db_session.add(user)
    db_session.commit()
    return user


def _usable_equipment(db_session, equipment_no, *, resolution="0.001"):
    equipment = MeasurementEquipment(
        equipment_no=equipment_no,
        name="測試量具",
        status="active",
        calibration_type="external",
        resolution=resolution,
        unit="mm",
    )
    db_session.add(equipment)
    db_session.flush()
    db_session.add(EquipmentCalibrationRecord(
        equipment_id=equipment.id,
        calibration_type="external",
        calibration_date=date.today() - timedelta(days=30),
        next_due_date=date.today() + timedelta(days=300),
        result="pass",
        status="approved",
    ))
    db_session.commit()
    return equipment


def _approved_criteria(db_session, name="設計測試準則"):
    profile = MsaCriteriaProfile(name=name)
    db_session.add(profile)
    db_session.flush()
    version = MsaCriteriaVersion(
        profile_id=profile.id,
        version_no=1,
        method_version="MSA4-1.0",
        effective_date=date(2026, 1, 1),
        thresholds={
            "grr_accept_max": 10,
            "grr_conditional_max": 30,
            "ndc_min": 5,
            "alpha": 0.05,
        },
        stability_rules={"rule_set": "WECO", "enabled_rules": [1, 2, 3, 4]},
        conditional_actions=["記錄理由"],
        basis="MSA 第四版",
        status="approved",
    )
    db_session.add(version)
    db_session.flush()
    profile.current_version_id = version.id
    db_session.commit()
    return profile


@pytest.fixture
def draft_msa_study(db_session, msa_manager):
    profile = _approved_criteria(db_session)
    return MsaStudyService.create(
        {
            "study_type": "grr_xbar_r",
            "measurement_purpose": "product_control",
            "characteristic": "外徑",
            "unit": "mm",
            "lsl": 9.5,
            "usl": 10.5,
            "criteria_profile_id": profile.id,
            "primary_executor_id": msa_manager.id,
        },
        actor_id=msa_manager.id,
    )


def _plan_payload(db_session, **overrides):
    gauge = overrides.pop(
        "gauge", None
    ) or _usable_equipment(db_session, f"EQ-DESIGN-{id(db_session) % 10000}")
    payload = {
        "method_code": "MSA4_GRR_XBAR_R_1_0",
        "part_count": 10,
        "appraiser_count": 3,
        "trial_count": 3,
        "random_seed": 20260727,
        "equipment": [
            {
                "equipment_id": gauge.id,
                "role": "primary_gauge",
                "measurement_mode": "default",
            }
        ],
        "parts": [
            {"part_identifier": f"件-{index}"} for index in range(1, 11)
        ],
        "appraisers": [
            {"name": f"評價人{index}"} for index in range(1, 4)
        ],
        "sampling_notes": "自三班次產出隨機抽樣",
        "environment_notes": "恆溫 23±2°C",
    }
    payload.update(overrides)
    return payload


@pytest.fixture
def complete_draft_plan(db_session, draft_msa_study, msa_manager):
    return MsaDesignService.create_plan(
        draft_msa_study.id,
        _plan_payload(db_session),
        actor_id=msa_manager.id,
    )


# ---------------------------------------------------------------------------
# 設計完整性
# ---------------------------------------------------------------------------


def test_grr_plan_requires_primary_gauge_parts_appraisers_and_trials(
    db_session, draft_msa_study, msa_manager,
):
    with pytest.raises(MsaValidationError) as error:
        MsaDesignService.create_plan(
            draft_msa_study.id,
            {
                "method_code": "MSA4_GRR_XBAR_R_1_0",
                "part_count": 3,
                "appraiser_count": 1,
                "trial_count": 1,
                "random_seed": 1,
                "equipment": [],
                "parts": [{"part_identifier": "件-1"}] * 3,
                "appraisers": [{"name": "評價人1"}],
            },
            actor_id=msa_manager.id,
        )

    assert error.value.code == "MSA_DESIGN_INCOMPLETE"
    details = error.value.details
    assert any(
        item["dimension"] == "appraisers" for item in details["shortfalls"]
    )
    assert "MSA_DESIGN_PRIMARY_GAUGE_MISSING" in details["issues"]


def test_plan_requires_declared_counts_to_match_supplied_rows(
    db_session, draft_msa_study, msa_manager,
):
    with pytest.raises(MsaValidationError) as error:
        MsaDesignService.create_plan(
            draft_msa_study.id,
            _plan_payload(db_session, appraisers=[{"name": "只有一位"}]),
            actor_id=msa_manager.id,
        )

    assert error.value.code == "MSA_DESIGN_COUNT_MISMATCH"


def test_bias_study_requires_reference_evidence(
    db_session, msa_manager,
):
    profile = _approved_criteria(db_session, "偏倚準則")
    study = MsaStudyService.create(
        {
            "study_type": "bias",
            "measurement_purpose": "product_control",
            "characteristic": "外徑",
            "unit": "mm",
            "lsl": 9.5,
            "usl": 10.5,
            "criteria_profile_id": profile.id,
        },
        actor_id=msa_manager.id,
    )
    gauge = _usable_equipment(db_session, "EQ-BIAS-1")

    with pytest.raises(MsaValidationError) as error:
        MsaDesignService.create_plan(
            study.id,
            {
                "method_code": "MSA4_BIAS_1_0",
                "part_count": 1,
                "appraiser_count": 1,
                "trial_count": 10,
                "random_seed": 7,
                "equipment": [
                    {"equipment_id": gauge.id, "role": "primary_gauge"}
                ],
                "parts": [{"part_identifier": "標準件"}],
                "appraisers": [{"name": "評價人1"}],
            },
            actor_id=msa_manager.id,
        )

    assert error.value.code == "MSA_DESIGN_REFERENCE_REQUIRED"


def test_bias_study_accepts_reference_value_with_traceable_source(
    db_session, msa_manager,
):
    profile = _approved_criteria(db_session, "偏倚準則2")
    study = MsaStudyService.create(
        {
            "study_type": "bias",
            "measurement_purpose": "product_control",
            "characteristic": "外徑",
            "unit": "mm",
            "lsl": 9.5,
            "usl": 10.5,
            "criteria_profile_id": profile.id,
        },
        actor_id=msa_manager.id,
    )
    gauge = _usable_equipment(db_session, "EQ-BIAS-2")

    plan = MsaDesignService.create_plan(
        study.id,
        {
            "method_code": "MSA4_BIAS_1_0",
            "part_count": 1,
            "appraiser_count": 1,
            "trial_count": 10,
            "random_seed": 7,
            "equipment": [
                {"equipment_id": gauge.id, "role": "primary_gauge"}
            ],
            "parts": [
                {
                    "part_identifier": "標準件",
                    "reference_value": "10.0000",
                    "reference_uncertainty": "0.0002",
                }
            ],
            "appraisers": [{"name": "評價人1"}],
        },
        actor_id=msa_manager.id,
    )

    assert plan.parts[0].reference_value is not None


def test_plan_rejects_method_that_does_not_match_study_type(
    db_session, draft_msa_study, msa_manager,
):
    with pytest.raises(MsaValidationError) as error:
        MsaDesignService.create_plan(
            draft_msa_study.id,
            _plan_payload(db_session, method_code="MSA4_BIAS_1_0"),
            actor_id=msa_manager.id,
        )

    assert error.value.code == "MSA_METHOD_STUDY_TYPE_MISMATCH"


def test_plan_can_only_be_created_while_study_is_draft(
    db_session, draft_msa_study, msa_manager,
):
    draft_msa_study.status = "approved"
    db_session.commit()

    with pytest.raises(MsaConflict) as error:
        MsaDesignService.create_plan(
            draft_msa_study.id,
            _plan_payload(db_session),
            actor_id=msa_manager.id,
        )

    assert error.value.code == "MSA_VERSION_CONFLICT"


# ---------------------------------------------------------------------------
# 盲碼與隨機順序
# ---------------------------------------------------------------------------


def test_blind_codes_are_positional_and_do_not_carry_real_identity(
    complete_draft_plan,
):
    """盲碼只表示序位；真實件號與參考值不得出現在盲碼中。"""
    codes = [part.blind_code for part in complete_draft_plan.parts]

    assert codes == [f"P{index:02d}" for index in range(1, 11)]
    assert len(set(codes)) == len(codes)
    for part in complete_draft_plan.parts:
        assert part.part_identifier not in part.blind_code
        assert part.blind_code != part.part_identifier


def test_same_seed_reproduces_identical_order(
    db_session, draft_msa_study, msa_manager,
):
    first = MsaDesignService.build_randomized_order(
        parts=[1, 2, 3], appraisers=[10, 11], trial_count=2, random_seed=42,
    )
    second = MsaDesignService.build_randomized_order(
        parts=[1, 2, 3], appraisers=[10, 11], trial_count=2, random_seed=42,
    )
    different = MsaDesignService.build_randomized_order(
        parts=[1, 2, 3], appraisers=[10, 11], trial_count=2, random_seed=43,
    )

    assert first == second
    assert first != different
    assert len(first) == 3 * 2 * 2
    assert [item["requested_order"] for item in first] == list(
        range(1, len(first) + 1)
    )


# ---------------------------------------------------------------------------
# 凍結
# ---------------------------------------------------------------------------


def test_freeze_saves_calibration_criteria_and_random_order_snapshots(
    db_session, complete_draft_plan, msa_manager,
):
    frozen = MsaDesignService.freeze(
        complete_draft_plan.id,
        actor_id=msa_manager.id,
        expected_plan_hash=None,
    )

    assert frozen.frozen_at is not None
    assert frozen.frozen_by_id == msa_manager.id
    assert frozen.plan_hash
    assert frozen.equipment_snapshot["items"]
    assert frozen.criteria_snapshot["version_id"]
    assert len(frozen.randomized_order) == (
        frozen.part_count * frozen.appraiser_count * frozen.trial_count
    )


def test_freeze_moves_study_to_ready_and_records_decision(
    db_session, complete_draft_plan, msa_manager,
):
    frozen = MsaDesignService.freeze(
        complete_draft_plan.id, actor_id=msa_manager.id,
    )

    db_session.refresh(frozen.study)
    assert frozen.study.status == "ready"
    assert frozen.study.current_plan_version_id == frozen.id
    decision = MsaWorkflowDecision.query.filter_by(
        study_id=frozen.study_id, action="freeze_plan",
    ).one()
    assert decision.to_status == "ready"


def test_frozen_plan_cannot_be_frozen_again(
    db_session, complete_draft_plan, msa_manager,
):
    MsaDesignService.freeze(complete_draft_plan.id, actor_id=msa_manager.id)

    with pytest.raises(MsaConflict) as error:
        MsaDesignService.freeze(
            complete_draft_plan.id, actor_id=msa_manager.id,
        )

    assert error.value.code == "MSA_PLAN_ALREADY_FROZEN"


def test_freeze_rejects_stale_expected_plan_hash(
    db_session, complete_draft_plan, msa_manager,
):
    with pytest.raises(MsaConflict) as error:
        MsaDesignService.freeze(
            complete_draft_plan.id,
            actor_id=msa_manager.id,
            expected_plan_hash="0" * 64,
        )

    assert error.value.code == "MSA_VERSION_CONFLICT"


def test_freeze_is_blocked_when_equipment_becomes_ineligible(
    db_session, complete_draft_plan, msa_manager,
):
    equipment_id = complete_draft_plan.study.equipment_links[0].equipment_id
    equipment = db_session.get(MeasurementEquipment, equipment_id)
    equipment.status = "maintenance"
    db_session.commit()

    with pytest.raises(MsaValidationError) as error:
        MsaDesignService.freeze(
            complete_draft_plan.id, actor_id=msa_manager.id,
        )

    assert error.value.code == "MSA_EQUIPMENT_STATUS_BLOCKED"
    db.session.rollback()
    db_session.refresh(complete_draft_plan)
    assert complete_draft_plan.frozen_at is None
    assert complete_draft_plan.study.status == "draft"


def test_freeze_warns_when_resolution_cannot_discriminate_tolerance(
    db_session, draft_msa_study, msa_manager,
):
    """公差 1.0 mm 搭配 0.5 mm 解析度違反十分之一法則。"""
    coarse = _usable_equipment(db_session, "EQ-COARSE-1", resolution="0.5")
    plan = MsaDesignService.create_plan(
        draft_msa_study.id,
        _plan_payload(db_session, gauge=coarse),
        actor_id=msa_manager.id,
    )

    frozen = MsaDesignService.freeze(plan.id, actor_id=msa_manager.id)

    assessment = frozen.equipment_snapshot["resolution_assessment"]
    assert assessment["level"] == "insufficient"
    assert assessment["discrimination_ratio"] > 0.1


def test_freeze_accepts_resolution_meeting_rule_of_tens(
    db_session, complete_draft_plan, msa_manager,
):
    frozen = MsaDesignService.freeze(
        complete_draft_plan.id, actor_id=msa_manager.id,
    )

    assessment = frozen.equipment_snapshot["resolution_assessment"]
    assert assessment["level"] == "ok"


# ---------------------------------------------------------------------------
# 盲測任務
# ---------------------------------------------------------------------------


def test_tasks_hide_real_identity_reference_values_and_other_readings(
    db_session, complete_draft_plan, msa_manager,
):
    frozen = MsaDesignService.freeze(
        complete_draft_plan.id, actor_id=msa_manager.id,
    )

    tasks = MsaDesignService.tasks(frozen.id)

    assert len(tasks) == frozen.part_count * frozen.appraiser_count * frozen.trial_count
    sample = tasks[0]
    assert set(sample) == {
        "requested_order",
        "part_blind_code",
        "appraiser_blind_code",
        "trial_no",
        "recorded",
    }
    serialized = str(tasks)
    for part in frozen.parts:
        assert part.part_identifier not in serialized


def test_tasks_are_not_available_before_freeze(complete_draft_plan):
    with pytest.raises(MsaConflict) as error:
        MsaDesignService.tasks(complete_draft_plan.id)

    assert error.value.code == "MSA_PLAN_NOT_FROZEN"


def test_plan_hash_is_stable_for_identical_design(
    db_session, complete_draft_plan, msa_manager,
):
    first = MsaDesignService.compute_plan_hash(complete_draft_plan)
    second = MsaDesignService.compute_plan_hash(complete_draft_plan)

    assert first == second
    assert len(first) == 64


def test_plan_hash_changes_when_design_changes(
    db_session, complete_draft_plan,
):
    before = MsaDesignService.compute_plan_hash(complete_draft_plan)
    complete_draft_plan.sampling_notes = "改為單一班次抽樣"
    db_session.flush()

    assert MsaDesignService.compute_plan_hash(complete_draft_plan) != before


def test_plan_requires_approved_criteria_version(
    db_session, msa_manager,
):
    study = MsaStudyService.create(
        {
            "study_type": "grr_xbar_r",
            "measurement_purpose": "product_control",
            "characteristic": "外徑",
            "unit": "mm",
            "lsl": 9.5,
            "usl": 10.5,
        },
        actor_id=msa_manager.id,
    )
    plan = MsaDesignService.create_plan(
        study.id, _plan_payload(db_session), actor_id=msa_manager.id,
    )

    with pytest.raises(MsaValidationError) as error:
        MsaDesignService.freeze(plan.id, actor_id=msa_manager.id)

    assert error.value.code == "MSA_CRITERIA_VERSION_REQUIRED"
    assert db.session.get(MsaPlanVersion, plan.id).frozen_at is None
