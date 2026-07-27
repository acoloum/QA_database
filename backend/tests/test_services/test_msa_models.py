"""MSA 設備、準則與研究資料模型的約束及不可變性測試。"""

from datetime import date, datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from backend.models import (
    EquipmentCalibrationRecord,
    EquipmentImportBatch,
    MeasurementEquipment,
    MeasurementEquipmentLink,
    MsaAppraiser,
    MsaCriteriaProfile,
    MsaCriteriaVersion,
    MsaObservation,
    MsaPart,
    MsaPlanVersion,
    MsaResultVersion,
    MsaStudy,
    MsaStudyEquipment,
    MsaValidationRun,
    MsaWorkflowDecision,
    User,
)


def _equipment(db_session, equipment_no):
    equipment = MeasurementEquipment(
        equipment_no=equipment_no,
        name="測試量具",
    )
    db_session.add(equipment)
    db_session.flush()
    return equipment


def _approved_calibration(db_session, equipment_no):
    equipment = _equipment(db_session, equipment_no)
    record = EquipmentCalibrationRecord(
        equipment_id=equipment.id,
        calibration_type="external",
        calibration_date=date(2026, 7, 1),
        result="pass",
        status="approved",
    )
    db_session.add(record)
    db_session.commit()
    return record


def _approved_criteria_version(db_session, profile_name):
    profile = MsaCriteriaProfile(name=profile_name)
    db_session.add(profile)
    db_session.flush()
    version = MsaCriteriaVersion(
        profile_id=profile.id,
        version_no=1,
        method_version="MSA4-1.0",
        effective_date=date(2026, 7, 27),
        thresholds={
            "grr_accept_max": 10,
            "grr_conditional_max": 30,
            "ndc_min": 5,
        },
        status="approved",
    )
    db_session.add(version)
    db_session.commit()
    return version


def test_equipment_number_is_unique(db_session):
    db_session.add(
        MeasurementEquipment(equipment_no="EQ-001", name="游標卡尺")
    )
    db_session.commit()
    db_session.add(
        MeasurementEquipment(equipment_no="EQ-001", name="重複設備")
    )

    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_equipment_range_order_is_enforced_by_database(db_session):
    """service 以外的寫入也不得保存量程下限大於上限的設備。"""
    db_session.add(
        MeasurementEquipment(
            equipment_no="EQ-RANGE-DB",
            name="錯誤量程設備",
            range_min=11,
            range_max=10,
        )
    )

    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_only_one_current_link_exists_for_each_source_entity(db_session):
    first = _equipment(db_session, "EQ-LINK-1")
    second = _equipment(db_session, "EQ-LINK-2")
    db_session.add(
        MeasurementEquipmentLink(
            equipment_id=first.id,
            source_module="pyrometry",
            source_entity_type="Recorder",
            source_entity_id=8,
            is_current=True,
        )
    )
    db_session.commit()
    db_session.add(
        MeasurementEquipmentLink(
            equipment_id=second.id,
            source_module="pyrometry",
            source_entity_type="Recorder",
            source_entity_id=8,
            is_current=True,
        )
    )

    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_equipment_import_file_hash_is_unique(db_session):
    first = EquipmentImportBatch(
        original_filename="equipment.xlsx",
        file_sha256="a" * 64,
        file_size=128,
        status="pending",
        parser_version="msa-equipment-v1",
    )
    db_session.add(first)
    db_session.commit()
    db_session.add(
        EquipmentImportBatch(
            original_filename="equipment-copy.xlsx",
            file_sha256="a" * 64,
            file_size=128,
            status="pending",
            parser_version="msa-equipment-v1",
        )
    )

    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_approved_calibration_cannot_be_changed(db_session):
    record = _approved_calibration(db_session, "EQ-002")
    record.certificate_no = "CERT-CHANGED"

    with pytest.raises(ValueError, match="核准後的校驗紀錄不可修改"):
        db_session.commit()
    db_session.rollback()


def test_approved_calibration_cannot_be_changed_after_status_downgrade(
    db_session,
):
    record = _approved_calibration(db_session, "EQ-003")
    record.status = "draft"
    record.certificate_no = "CERT-BYPASS"

    with pytest.raises(ValueError, match="核准後的校驗紀錄不可修改"):
        db_session.commit()
    db_session.rollback()


def test_approved_calibration_cannot_be_deleted(db_session):
    record = _approved_calibration(db_session, "EQ-004")
    db_session.delete(record)

    with pytest.raises(ValueError, match="核准後的校驗紀錄不可刪除"):
        db_session.commit()
    db_session.rollback()


def test_approved_criteria_version_cannot_be_changed(db_session):
    version = _approved_criteria_version(db_session, "一般計量型")
    version.thresholds = {"grr_accept_max": 9}

    with pytest.raises(ValueError, match="核准後的 MSA 準則版本不可修改"):
        db_session.commit()
    db_session.rollback()


def test_approved_criteria_version_cannot_be_changed_after_status_downgrade(
    db_session,
):
    version = _approved_criteria_version(db_session, "重要特性計量型")
    version.status = "draft"
    version.thresholds = {"grr_accept_max": 9}

    with pytest.raises(ValueError, match="核准後的 MSA 準則版本不可修改"):
        db_session.commit()
    db_session.rollback()


def test_approved_criteria_version_cannot_be_deleted(db_session):
    version = _approved_criteria_version(db_session, "刪除保護準則")
    db_session.delete(version)

    with pytest.raises(ValueError, match="核准後的 MSA 準則版本不可刪除"):
        db_session.commit()
    db_session.rollback()


def test_criteria_version_number_is_unique_within_profile(db_session):
    profile = MsaCriteriaProfile(name="唯一版次準則")
    db_session.add(profile)
    db_session.flush()
    db_session.add_all(
        [
            MsaCriteriaVersion(
                profile_id=profile.id,
                version_no=1,
                method_version="MSA4-1.0",
                effective_date=date(2026, 7, 27),
                thresholds={"ndc_min": 5},
            ),
            MsaCriteriaVersion(
                profile_id=profile.id,
                version_no=1,
                method_version="MSA4-1.1",
                effective_date=date(2026, 8, 1),
                thresholds={"ndc_min": 5},
            ),
        ]
    )

    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_current_criteria_version_must_belong_to_same_profile(db_session):
    db_session.execute(text("PRAGMA foreign_keys = ON"))
    assert db_session.execute(text("PRAGMA foreign_keys")).scalar_one() == 1

    try:
        profile_a = MsaCriteriaProfile(name="準則設定 A")
        profile_b = MsaCriteriaProfile(name="準則設定 B")
        db_session.add_all([profile_a, profile_b])
        db_session.commit()

        version_b = MsaCriteriaVersion(
            profile_id=profile_b.id,
            version_no=1,
            method_version="MSA4-1.0",
            effective_date=date(2026, 7, 27),
            thresholds={"ndc_min": 5},
        )
        db_session.add(version_b)
        db_session.commit()

        profile_a.current_version_id = version_b.id
        with pytest.raises(IntegrityError):
            db_session.commit()
    finally:
        db_session.rollback()
        db_session.execute(text("PRAGMA foreign_keys = OFF"))


def test_exempt_equipment_requires_a_non_blank_exemption_reason(db_session):
    """防止豁免設備未保存理由仍被當成正式研究證據。"""
    db_session.add(
        MeasurementEquipment(
            equipment_no="EQ-EXEMPT-NO-REASON",
            name="未載明理由的豁免量具",
            calibration_type="exempt",
            calibration_exemption_reason="  ",
        )
    )

    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_limited_use_calibration_persists_applicable_modes(db_session):
    """防止受限校驗缺少可供服務精確比對的結構化量測模式。"""
    equipment = _equipment(db_session, "EQ-LIMITED-MODES")
    record = EquipmentCalibrationRecord(
        equipment_id=equipment.id,
        calibration_type="external",
        calibration_date=date(2026, 7, 27),
        result="limited_use",
        applicable_modes=["內徑量測"],
        restriction_conditions="僅限既定量程",
        status="approved",
    )
    db_session.add(record)
    db_session.commit()

    assert record.applicable_modes == ["內徑量測"]


def test_limited_use_calibration_requires_a_non_blank_restriction(db_session):
    """防止模式吻合但沒有可追溯限制理由的校驗被正式採用。"""
    equipment = _equipment(db_session, "EQ-LIMITED-NO-RESTRICTION")
    db_session.add(
        EquipmentCalibrationRecord(
            equipment_id=equipment.id,
            calibration_type="external",
            calibration_date=date(2026, 7, 27),
            result="limited_use",
            applicable_modes=["內徑量測"],
            restriction_conditions="  ",
            status="approved",
        )
    )

    with pytest.raises(ValueError, match="受限校驗"):
        db_session.commit()
    db_session.rollback()


def test_limited_use_calibration_rejects_blank_mode_element(db_session):
    """防止非空陣列以空白量測模式繞過受限校驗資料不變量。"""
    equipment = _equipment(db_session, "EQ-LIMITED-BLANK-MODE")
    db_session.add(
        EquipmentCalibrationRecord(
            equipment_id=equipment.id,
            calibration_type="external",
            calibration_date=date(2026, 7, 27),
            result="limited_use",
            applicable_modes=["  "],
            restriction_conditions="僅限既定量程",
            status="approved",
        )
    )

    with pytest.raises(ValueError, match="受限校驗"):
        db_session.commit()
    db_session.rollback()


def test_limited_use_calibration_rejects_empty_applicable_modes(db_session):
    """防止資料庫接受沒有任何適用模式的受限校驗證據。"""
    equipment = _equipment(db_session, "EQ-LIMITED-NO-MODES")
    db_session.add(
        EquipmentCalibrationRecord(
            equipment_id=equipment.id,
            calibration_type="external",
            calibration_date=date(2026, 7, 27),
            result="limited_use",
            applicable_modes=[],
            restriction_conditions="僅限既定量程",
            status="approved",
        )
    )

    with pytest.raises(ValueError, match="受限校驗"):
        db_session.commit()
    db_session.rollback()


# ---------------------------------------------------------------------------
# MSA 研究、觀測、結果與工作流證據
# ---------------------------------------------------------------------------


def _msa_actor(db_session, username="msa_model_actor"):
    user = User.query.filter_by(username=username).first()
    if user is None:
        user = User(username=username, password="x")
        db_session.add(user)
        db_session.flush()
    return user


def _build_study(study_no="MSA-2026-0001", **overrides):
    payload = {
        "study_no": study_no,
        "study_type": "grr_xbar_r",
        "measurement_purpose": "product_control",
        "characteristic": "外徑",
        "unit": "mm",
        "status": "draft",
    }
    payload.update(overrides)
    return MsaStudy(**payload)


def _study(db_session, study_no="MSA-2026-0001", **overrides):
    study = _build_study(study_no, **overrides)
    db_session.add(study)
    db_session.flush()
    return study


def _frozen_plan(db_session, study_no="MSA-2026-0100"):
    """建立一個已凍結、含 2 零件與 2 評價人的計畫版本。"""
    actor = _msa_actor(db_session)
    study = _study(db_session, study_no, status="collecting")
    plan = MsaPlanVersion(
        study_id=study.id,
        plan_version_no=1,
        method_code="MSA4_GRR_XBAR_R_1_0",
        method_version="1.0",
        design_type="crossed",
        part_count=2,
        appraiser_count=2,
        trial_count=2,
        random_seed=20260727,
        randomized_order=[],
        equipment_snapshot={"primary_gauge": {"equipment_id": 1}},
        criteria_snapshot={"version_id": 1, "thresholds": {}},
        plan_hash="a" * 64,
        frozen_by_id=actor.id,
        frozen_at=datetime(2026, 7, 27, 1, 0, tzinfo=timezone.utc),
    )
    db_session.add(plan)
    db_session.flush()
    for index in (1, 2):
        db_session.add(MsaPart(
            plan_version_id=plan.id,
            part_no=index,
            blind_code=f"P{index}",
            part_identifier=f"零件-{index}",
        ))
        db_session.add(MsaAppraiser(
            plan_version_id=plan.id,
            appraiser_no=index,
            blind_code=f"A{index}",
            user_id=actor.id,
            name=f"評價人{index}",
        ))
    db_session.commit()
    return plan


@pytest.fixture
def frozen_msa_plan(db_session):
    return _frozen_plan(db_session)


def _observation(db_session, plan, **overrides):
    payload = {
        "plan_version_id": plan.id,
        "part_id": plan.parts[0].id,
        "appraiser_id": plan.appraisers[0].id,
        "trial_no": 1,
        "requested_order": 1,
        "actual_entry_order": 1,
        "numeric_value": Decimal("10.001"),
        "source": "page_single",
        "entered_by_id": _msa_actor(db_session).id,
        "is_effective": True,
    }
    payload.update(overrides)
    observation = MsaObservation(**payload)
    db_session.add(observation)
    db_session.commit()
    return observation


def test_study_requires_unique_number(db_session):
    _study(db_session, "MSA-2026-0001")
    db_session.commit()
    db_session.add(_build_study("MSA-2026-0001", study_type="bias"))

    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_study_equipment_role_and_mode_are_unique(db_session):
    study = _study(db_session, "MSA-2026-0002")
    equipment = _equipment(db_session, "EQ-STUDY-1")
    common = {
        "study_id": study.id,
        "equipment_id": equipment.id,
        "role": "primary_gauge",
        "measurement_mode": "contact",
    }
    db_session.add(MsaStudyEquipment(**common))
    db_session.commit()
    db_session.add(MsaStudyEquipment(**common))

    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_frozen_plan_cannot_be_changed(frozen_msa_plan, db_session):
    frozen_msa_plan.part_count = 5

    with pytest.raises(ValueError, match="凍結後的 MSA 計畫版本不可修改"):
        db_session.commit()
    db_session.rollback()


def test_observation_correction_is_append_only(db_session, frozen_msa_plan):
    original = _observation(db_session, frozen_msa_plan)
    original.numeric_value = Decimal("11")

    with pytest.raises(ValueError, match="MSA 觀測不可直接修改"):
        db_session.commit()
    db_session.rollback()


def test_observation_may_only_be_retired_by_setting_is_effective_false(
    db_session, frozen_msa_plan,
):
    """作廢是 append-only 規則唯一允許的狀態變更。"""
    original = _observation(db_session, frozen_msa_plan)

    original.is_effective = False
    db_session.commit()

    db_session.refresh(original)
    assert original.is_effective is False


def test_observation_cannot_be_deleted(db_session, frozen_msa_plan):
    original = _observation(db_session, frozen_msa_plan)
    db_session.delete(original)

    with pytest.raises(ValueError, match="MSA 觀測不可刪除"):
        db_session.commit()
    db_session.rollback()


def test_only_one_effective_observation_per_task(db_session, frozen_msa_plan):
    _observation(db_session, frozen_msa_plan)
    db_session.add(MsaObservation(
        plan_version_id=frozen_msa_plan.id,
        part_id=frozen_msa_plan.parts[0].id,
        appraiser_id=frozen_msa_plan.appraisers[0].id,
        trial_no=1,
        requested_order=1,
        actual_entry_order=2,
        numeric_value=Decimal("10.002"),
        source="page_single",
        entered_by_id=_msa_actor(db_session).id,
        is_effective=True,
    ))

    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_observation_must_carry_exactly_one_kind_of_value(
    db_session, frozen_msa_plan,
):
    db_session.add(MsaObservation(
        plan_version_id=frozen_msa_plan.id,
        part_id=frozen_msa_plan.parts[0].id,
        appraiser_id=frozen_msa_plan.appraisers[0].id,
        trial_no=1,
        requested_order=1,
        actual_entry_order=1,
        numeric_value=Decimal("10.001"),
        attribute_value="pass",
        source="page_single",
        entered_by_id=_msa_actor(db_session).id,
        is_effective=True,
    ))

    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def _build_result_version(db_session, plan, **overrides):
    payload = {
        "study_id": plan.study_id,
        "plan_version_id": plan.id,
        "result_version_no": 1,
        "method_code": "MSA4_GRR_XBAR_R_1_0",
        "method_version": "1.0",
        "code_version": "msa-engine-1",
        "data_hash": "b" * 64,
        "raw_data_summary": {"observations": 8},
        "applicability_result": {"applicable": True},
        "statistics": {"grr_percent_tolerance": 12.5},
        "chart_data": {"series": []},
        "criteria_snapshot": {"grr_accept_max": 10},
        "conclusion": {"verdict": "conditional"},
        "warnings": [],
        "blockers": [],
        "status": "analyzed",
        "created_by_id": _msa_actor(db_session).id,
    }
    payload.update(overrides)
    return MsaResultVersion(**payload)


def _result_version(db_session, plan, **overrides):
    result = _build_result_version(db_session, plan, **overrides)
    db_session.add(result)
    db_session.commit()
    return result


def test_result_version_number_is_unique_within_study(
    db_session, frozen_msa_plan,
):
    _result_version(db_session, frozen_msa_plan)
    db_session.add(_build_result_version(db_session, frozen_msa_plan))

    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_result_statistics_cannot_be_rewritten(db_session, frozen_msa_plan):
    result = _result_version(db_session, frozen_msa_plan)
    result.statistics = {"grr_percent_tolerance": 1.0}

    with pytest.raises(ValueError, match="MSA 結果版本的統計證據不可修改"):
        db_session.commit()
    db_session.rollback()


def test_result_status_may_advance_through_workflow(db_session, frozen_msa_plan):
    """狀態是結果版本唯一可由工作流變更的欄位。"""
    result = _result_version(db_session, frozen_msa_plan)

    result.status = "submitted"
    db_session.commit()

    db_session.refresh(result)
    assert result.status == "submitted"


def test_result_version_cannot_be_deleted(db_session, frozen_msa_plan):
    result = _result_version(db_session, frozen_msa_plan)
    db_session.delete(result)

    with pytest.raises(ValueError, match="MSA 結果版本不可刪除"):
        db_session.commit()
    db_session.rollback()


def test_only_one_submitted_result_exists_per_study(
    db_session, frozen_msa_plan,
):
    _result_version(db_session, frozen_msa_plan, status="submitted")
    db_session.add(_build_result_version(
        db_session, frozen_msa_plan, result_version_no=2, status="submitted",
    ))

    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_workflow_decision_is_append_only(db_session, frozen_msa_plan):
    decision = MsaWorkflowDecision(
        study_id=frozen_msa_plan.study_id,
        action="submit",
        from_status="analyzed",
        to_status="submitted",
        reason="統計完成",
        actor_id=_msa_actor(db_session).id,
        separation_check={"passed": True},
    )
    db_session.add(decision)
    db_session.commit()
    decision.reason = "改寫理由"

    with pytest.raises(ValueError, match="MSA 工作流決策不可修改"):
        db_session.commit()
    db_session.rollback()


def test_validation_run_is_append_only(db_session):
    run = MsaValidationRun(
        case_code="grr_xbar_r_reference",
        fixture_hash="c" * 64,
        method_versions={"MSA4_GRR_XBAR_R_1_0": "1.0"},
        code_version="msa-engine-1",
        tolerances={"grr": 1e-9},
        observed={"grr": 1.0},
        expected={"grr": 1.0},
        differences=[],
        result="PASS",
        executed_by_id=_msa_actor(db_session).id,
    )
    db_session.add(run)
    db_session.commit()
    run.result = "FAIL"

    with pytest.raises(ValueError, match="MSA 軟體確效執行不可修改"):
        db_session.commit()
    db_session.rollback()


def test_validation_run_rejects_unknown_result(db_session):
    db_session.add(MsaValidationRun(
        case_code="grr_xbar_r_reference",
        fixture_hash="d" * 64,
        method_versions={},
        code_version="msa-engine-1",
        tolerances={},
        observed={},
        expected={},
        differences=[],
        result="UNKNOWN",
        executed_by_id=_msa_actor(db_session).id,
    ))

    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()
