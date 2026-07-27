"""MSA 盲測觀測收集、append-only 修正與完整性驗證測試。"""

from datetime import date, timedelta
from decimal import Decimal

import pytest

from backend.extensions import db
from backend.models import (
    EquipmentCalibrationRecord,
    MeasurementEquipment,
    MsaCriteriaProfile,
    MsaCriteriaVersion,
    MsaObservation,
    User,
)
from backend.services.msa_design_service import MsaDesignService
from backend.services.msa_errors import (
    MsaConflict,
    MsaForbidden,
    MsaValidationError,
)
from backend.services.msa_observation_import_service import (
    MsaObservationImportService,
)
from backend.services.msa_observation_service import MsaObservationService
from backend.services.msa_study_service import MsaStudyService


@pytest.fixture
def msa_manager(db_session):
    user = User(username="msa_obs_manager", password="x")
    db_session.add(user)
    db_session.commit()
    return user


@pytest.fixture
def appraiser_users(db_session):
    users = [
        User(username=f"msa_obs_appraiser_{index}", password="x")
        for index in range(1, 3)
    ]
    db_session.add_all(users)
    db_session.commit()
    return users


def _usable_equipment(db_session, equipment_no="EQ-OBS-1"):
    equipment = MeasurementEquipment(
        equipment_no=equipment_no,
        name="測試量具",
        status="active",
        calibration_type="external",
        resolution="0.001",
        unit="mm",
    )
    db_session.add(equipment)
    db_session.flush()
    db_session.add(EquipmentCalibrationRecord(
        equipment_id=equipment.id,
        calibration_type="external",
        calibration_date=date.today() - timedelta(days=10),
        next_due_date=date.today() + timedelta(days=300),
        result="pass",
        status="approved",
    ))
    db_session.commit()
    return equipment


def _approved_criteria(db_session, name="觀測測試準則"):
    profile = MsaCriteriaProfile(name=name)
    db_session.add(profile)
    db_session.flush()
    version = MsaCriteriaVersion(
        profile_id=profile.id,
        version_no=1,
        method_version="MSA4-1.0",
        effective_date=date(2026, 1, 1),
        thresholds={"grr_accept_max": 10, "grr_conditional_max": 30},
        status="approved",
    )
    db_session.add(version)
    db_session.flush()
    profile.current_version_id = version.id
    db_session.commit()
    return profile


def _collecting_plan(db_session, msa_manager, appraiser_users, **study_over):
    profile = _approved_criteria(db_session)
    payload = {
        "study_type": "grr_xbar_r",
        "measurement_purpose": "product_control",
        "characteristic": "外徑",
        "unit": "mm",
        "lsl": 9.5,
        "usl": 10.5,
        "criteria_profile_id": profile.id,
    }
    payload.update(study_over)
    study = MsaStudyService.create(payload, actor_id=msa_manager.id)
    gauge = _usable_equipment(db_session, f"EQ-OBS-{study.id}")
    plan = MsaDesignService.create_plan(
        study.id,
        {
            "method_code": "MSA4_GRR_XBAR_R_1_0",
            "part_count": 2,
            "appraiser_count": 2,
            "trial_count": 2,
            "random_seed": 20260727,
            "equipment": [
                {"equipment_id": gauge.id, "role": "primary_gauge"}
            ],
            "parts": [
                {"part_identifier": "件-1"}, {"part_identifier": "件-2"},
            ],
            "appraisers": [
                {"name": "評價人1", "user_id": appraiser_users[0].id},
                {"name": "評價人2", "user_id": appraiser_users[1].id},
            ],
        },
        actor_id=msa_manager.id,
    )
    return MsaDesignService.freeze(plan.id, actor_id=msa_manager.id)


@pytest.fixture
def collecting_plan(db_session, msa_manager, appraiser_users):
    return _collecting_plan(db_session, msa_manager, appraiser_users)


def _first_task_for(plan, appraiser_user):
    """取得指定評價人在隨機順序中的第一個任務。"""
    appraiser = next(
        row for row in plan.appraisers if row.user_id == appraiser_user.id
    )
    return next(
        item for item in plan.randomized_order
        if item["appraiser_id"] == appraiser.id
    )


# ---------------------------------------------------------------------------
# 逐筆收集
# ---------------------------------------------------------------------------


def test_appraiser_can_enter_own_blind_task(
    db_session, collecting_plan, appraiser_users,
):
    task = _first_task_for(collecting_plan, appraiser_users[0])

    observation = MsaObservationService.record(
        collecting_plan.id,
        {
            "task_order": task["requested_order"],
            "numeric_value": "10.004",
            "measured_at": "2026-07-27T09:30:00+08:00",
        },
        actor_id=appraiser_users[0].id,
    )

    assert observation.source == "page_single"
    assert observation.actual_entry_order == 1
    assert observation.numeric_value == Decimal("10.004")
    assert observation.is_effective is True


def test_appraiser_cannot_enter_another_appraisers_task(
    db_session, collecting_plan, appraiser_users,
):
    task = _first_task_for(collecting_plan, appraiser_users[1])

    with pytest.raises(MsaForbidden) as error:
        MsaObservationService.record(
            collecting_plan.id,
            {"task_order": task["requested_order"], "numeric_value": "10.0"},
            actor_id=appraiser_users[0].id,
        )

    assert error.value.code == "MSA_OBSERVATION_TASK_NOT_ASSIGNED"


def test_manager_matrix_entry_keeps_real_actor_and_marks_source(
    db_session, collecting_plan, appraiser_users, msa_manager,
):
    task = _first_task_for(collecting_plan, appraiser_users[0])

    observation = MsaObservationService.record(
        collecting_plan.id,
        {"task_order": task["requested_order"], "numeric_value": "10.004"},
        actor_id=msa_manager.id,
        can_manage=True,
    )

    assert observation.source == "page_matrix"
    assert observation.entered_by_id == msa_manager.id


def test_actual_entry_order_increments_per_plan(
    db_session, collecting_plan, appraiser_users, msa_manager,
):
    orders = []
    for item in collecting_plan.randomized_order[:3]:
        observation = MsaObservationService.record(
            collecting_plan.id,
            {"task_order": item["requested_order"], "numeric_value": "10.0"},
            actor_id=msa_manager.id,
            can_manage=True,
        )
        orders.append(observation.actual_entry_order)

    assert orders == [1, 2, 3]


def test_duplicate_entry_for_same_task_is_a_conflict(
    db_session, collecting_plan, msa_manager,
):
    task = collecting_plan.randomized_order[0]
    payload = {"task_order": task["requested_order"], "numeric_value": "10.0"}
    MsaObservationService.record(
        collecting_plan.id, payload, actor_id=msa_manager.id, can_manage=True,
    )

    with pytest.raises(MsaConflict) as error:
        MsaObservationService.record(
            collecting_plan.id, dict(payload),
            actor_id=msa_manager.id, can_manage=True,
        )

    assert error.value.code == "MSA_OBSERVATION_ALREADY_RECORDED"


@pytest.mark.parametrize(
    "value", ["", "  ", "10,004", "1e400", "abc", None],
)
def test_numeric_value_must_be_unambiguous_decimal(
    db_session, collecting_plan, msa_manager, value,
):
    task = collecting_plan.randomized_order[0]

    with pytest.raises(MsaValidationError) as error:
        MsaObservationService.record(
            collecting_plan.id,
            {"task_order": task["requested_order"], "numeric_value": value},
            actor_id=msa_manager.id,
            can_manage=True,
        )

    assert error.value.code == "MSA_OBSERVATION_INVALID"
    db.session.rollback()


def test_unknown_task_order_is_rejected(
    db_session, collecting_plan, msa_manager,
):
    with pytest.raises(MsaValidationError) as error:
        MsaObservationService.record(
            collecting_plan.id,
            {"task_order": 9999, "numeric_value": "10.0"},
            actor_id=msa_manager.id,
            can_manage=True,
        )

    assert error.value.code == "MSA_OBSERVATION_TASK_UNKNOWN"


def test_collecting_requires_a_frozen_plan(
    db_session, msa_manager, appraiser_users,
):
    profile = _approved_criteria(db_session, "未凍結準則")
    study = MsaStudyService.create(
        {
            "study_type": "grr_xbar_r",
            "measurement_purpose": "product_control",
            "characteristic": "外徑",
            "unit": "mm",
            "lsl": 9.5,
            "usl": 10.5,
            "criteria_profile_id": profile.id,
        },
        actor_id=msa_manager.id,
    )
    gauge = _usable_equipment(db_session, "EQ-OBS-DRAFT")
    plan = MsaDesignService.create_plan(
        study.id,
        {
            "method_code": "MSA4_GRR_XBAR_R_1_0",
            "part_count": 2,
            "appraiser_count": 2,
            "trial_count": 2,
            "random_seed": 1,
            "equipment": [
                {"equipment_id": gauge.id, "role": "primary_gauge"}
            ],
            "parts": [{"part_identifier": "A"}, {"part_identifier": "B"}],
            "appraisers": [{"name": "甲"}, {"name": "乙"}],
        },
        actor_id=msa_manager.id,
    )

    with pytest.raises(MsaConflict) as error:
        MsaObservationService.record(
            plan.id,
            {"task_order": 1, "numeric_value": "10.0"},
            actor_id=msa_manager.id,
            can_manage=True,
        )

    assert error.value.code == "MSA_PLAN_NOT_FROZEN"


def test_first_observation_moves_study_to_collecting(
    db_session, collecting_plan, msa_manager,
):
    MsaObservationService.record(
        collecting_plan.id,
        {"task_order": 1, "numeric_value": "10.0"},
        actor_id=msa_manager.id,
        can_manage=True,
    )

    db_session.refresh(collecting_plan.study)
    assert collecting_plan.study.status == "collecting"


# ---------------------------------------------------------------------------
# 計數型
# ---------------------------------------------------------------------------


def test_attribute_category_must_belong_to_frozen_category_set(
    db_session, msa_manager, appraiser_users,
):
    profile = _approved_criteria(db_session, "計數型準則")
    study = MsaStudyService.create(
        {
            "study_type": "attribute",
            "measurement_purpose": "product_control",
            "characteristic": "外觀",
            "unit": "judgement",
            "no_tolerance_reason": "計數型判定無數值公差",
            "criteria_profile_id": profile.id,
        },
        actor_id=msa_manager.id,
    )
    gauge = _usable_equipment(db_session, "EQ-OBS-ATTR")
    plan = MsaDesignService.create_plan(
        study.id,
        {
            "method_code": "MSA4_ATTRIBUTE_1_0",
            "part_count": 20,
            "appraiser_count": 2,
            "trial_count": 2,
            "random_seed": 5,
            "category_set": ["pass", "fail"],
            "equipment": [
                {"equipment_id": gauge.id, "role": "primary_gauge"}
            ],
            "parts": [
                {"part_identifier": f"件-{index}"} for index in range(1, 21)
            ],
            "appraisers": [{"name": "甲"}, {"name": "乙"}],
        },
        actor_id=msa_manager.id,
    )
    frozen = MsaDesignService.freeze(plan.id, actor_id=msa_manager.id)

    accepted = MsaObservationService.record(
        frozen.id,
        {"task_order": 1, "attribute_value": "pass"},
        actor_id=msa_manager.id,
        can_manage=True,
    )
    with pytest.raises(MsaValidationError) as error:
        MsaObservationService.record(
            frozen.id,
            {"task_order": 2, "attribute_value": "maybe"},
            actor_id=msa_manager.id,
            can_manage=True,
        )

    assert accepted.attribute_value == "pass"
    assert error.value.code == "MSA_OBSERVATION_CATEGORY_UNKNOWN"


def test_observation_must_carry_exactly_one_value_kind(
    db_session, collecting_plan, msa_manager,
):
    with pytest.raises(MsaValidationError) as error:
        MsaObservationService.record(
            collecting_plan.id,
            {
                "task_order": 1,
                "numeric_value": "10.0",
                "attribute_value": "pass",
            },
            actor_id=msa_manager.id,
            can_manage=True,
        )

    assert error.value.code == "MSA_OBSERVATION_INVALID"


# ---------------------------------------------------------------------------
# append-only 修正
# ---------------------------------------------------------------------------


@pytest.fixture
def existing_observation(db_session, collecting_plan, msa_manager):
    return MsaObservationService.record(
        collecting_plan.id,
        {"task_order": 1, "numeric_value": "10.001"},
        actor_id=msa_manager.id,
        can_manage=True,
    )


def test_correction_supersedes_without_updating_original(
    db_session, existing_observation, msa_manager,
):
    corrected = MsaObservationService.correct(
        existing_observation.id,
        {"numeric_value": "10.002", "reason": "原紀錄小數點輸入錯誤"},
        actor_id=msa_manager.id,
    )

    db_session.refresh(existing_observation)
    assert existing_observation.is_effective is False
    assert existing_observation.numeric_value == Decimal("10.001")
    assert corrected.supersedes_id == existing_observation.id
    assert corrected.is_effective is True
    assert corrected.correction_reason == "原紀錄小數點輸入錯誤"


def test_correction_requires_a_reason(
    db_session, existing_observation, msa_manager,
):
    with pytest.raises(MsaValidationError) as error:
        MsaObservationService.correct(
            existing_observation.id,
            {"numeric_value": "10.002"},
            actor_id=msa_manager.id,
        )

    assert error.value.code == "MSA_CORRECTION_REASON_REQUIRED"


def test_correcting_an_already_retired_observation_is_a_conflict(
    db_session, existing_observation, msa_manager,
):
    MsaObservationService.correct(
        existing_observation.id,
        {"numeric_value": "10.002", "reason": "第一次修正"},
        actor_id=msa_manager.id,
    )

    with pytest.raises(MsaConflict) as error:
        MsaObservationService.correct(
            existing_observation.id,
            {"numeric_value": "10.003", "reason": "第二次修正"},
            actor_id=msa_manager.id,
        )

    assert error.value.code == "MSA_OBSERVATION_ALREADY_SUPERSEDED"


def test_correction_chain_keeps_only_one_effective_row(
    db_session, existing_observation, msa_manager,
):
    first = MsaObservationService.correct(
        existing_observation.id,
        {"numeric_value": "10.002", "reason": "第一次修正"},
        actor_id=msa_manager.id,
    )
    MsaObservationService.correct(
        first.id,
        {"numeric_value": "10.003", "reason": "第二次修正"},
        actor_id=msa_manager.id,
    )

    effective = MsaObservation.query.filter_by(
        plan_version_id=existing_observation.plan_version_id,
        part_id=existing_observation.part_id,
        appraiser_id=existing_observation.appraiser_id,
        trial_no=existing_observation.trial_no,
        is_effective=True,
    ).all()
    assert len(effective) == 1
    assert effective[0].numeric_value == Decimal("10.003")


# ---------------------------------------------------------------------------
# 完整性驗證
# ---------------------------------------------------------------------------


def test_validate_reports_missing_tasks_before_analysis(
    db_session, collecting_plan, msa_manager,
):
    MsaObservationService.record(
        collecting_plan.id,
        {"task_order": 1, "numeric_value": "10.0"},
        actor_id=msa_manager.id,
        can_manage=True,
    )

    report = MsaObservationService.validate(collecting_plan.id)

    assert report["complete"] is False
    assert report["expected"] == 8
    assert report["recorded"] == 1
    assert len(report["missing"]) == 7


def test_validate_marks_plan_ready_for_analysis_when_complete(
    db_session, collecting_plan, msa_manager,
):
    for item in collecting_plan.randomized_order:
        MsaObservationService.record(
            collecting_plan.id,
            {"task_order": item["requested_order"], "numeric_value": "10.0"},
            actor_id=msa_manager.id,
            can_manage=True,
        )

    report = MsaObservationService.validate(collecting_plan.id)

    db_session.refresh(collecting_plan.study)
    assert report["complete"] is True
    assert report["missing"] == []
    assert collecting_plan.study.status == "ready_for_analysis"


# ---------------------------------------------------------------------------
# Excel 預覽與確認
# ---------------------------------------------------------------------------


def _fixture_path():
    from pathlib import Path
    return Path(__file__).parents[1] / "fixtures" / "msa_observations.xlsx"


def test_fixture_matches_the_frozen_blind_order(collecting_plan):
    """fixture 依固定 seed 產生；順序若變動必須讓測試立即失敗。"""
    codes = {part.id: part.blind_code for part in collecting_plan.parts}
    appraisers = {
        row.id: row.blind_code for row in collecting_plan.appraisers
    }
    actual = [
        (item["requested_order"], codes[item["part_id"]],
         appraisers[item["appraiser_id"]], item["trial_no"])
        for item in collecting_plan.randomized_order
    ]

    assert actual == [
        (1, "P02", "A01", 1), (2, "P02", "A02", 2),
        (3, "P01", "A01", 2), (4, "P01", "A02", 1),
        (5, "P02", "A02", 1), (6, "P01", "A02", 2),
        (7, "P01", "A01", 1), (8, "P02", "A01", 2),
    ]


def test_import_preview_reports_excel_cell_for_invalid_value(
    db_session, collecting_plan, msa_manager,
):
    batch = MsaObservationImportService.preview(
        collecting_plan.id,
        _fixture_path(),
        actor_id=msa_manager.id,
    )

    issue = batch.issues[0]
    assert issue["cell"] == "D7"
    assert issue["sheet"] == "觀測"
    assert issue["code"] == "MSA_OBSERVATION_INVALID"


def test_import_preview_does_not_write_observations(
    db_session, collecting_plan, msa_manager,
):
    MsaObservationImportService.preview(
        collecting_plan.id, _fixture_path(), actor_id=msa_manager.id,
    )

    assert MsaObservation.query.filter_by(
        plan_version_id=collecting_plan.id
    ).count() == 0


def test_import_confirm_writes_only_clean_rows_in_one_transaction(
    db_session, collecting_plan, msa_manager,
):
    batch = MsaObservationImportService.preview(
        collecting_plan.id, _fixture_path(), actor_id=msa_manager.id,
    )

    confirmed = MsaObservationImportService.confirm(
        batch.id, actor_id=msa_manager.id,
    )

    assert confirmed.status == "confirmed"
    assert confirmed.stats["written"] == 7
    assert confirmed.stats["skipped"] == 1
    written = MsaObservation.query.filter_by(
        plan_version_id=collecting_plan.id, is_effective=True,
    ).all()
    assert len(written) == 7
    assert all(row.source == "excel_import" for row in written)
    assert all(row.import_batch_id == confirmed.id for row in written)


def test_import_confirm_is_idempotent_for_the_same_batch(
    db_session, collecting_plan, msa_manager,
):
    batch = MsaObservationImportService.preview(
        collecting_plan.id, _fixture_path(), actor_id=msa_manager.id,
    )
    first = MsaObservationImportService.confirm(
        batch.id, actor_id=msa_manager.id,
    )
    second = MsaObservationImportService.confirm(
        batch.id, actor_id=msa_manager.id,
    )

    assert second.id == first.id
    assert MsaObservation.query.filter_by(
        plan_version_id=collecting_plan.id
    ).count() == 7


def test_preview_of_the_same_file_reuses_the_batch(
    db_session, collecting_plan, msa_manager,
):
    first = MsaObservationImportService.preview(
        collecting_plan.id, _fixture_path(), actor_id=msa_manager.id,
    )
    second = MsaObservationImportService.preview(
        collecting_plan.id, _fixture_path(), actor_id=msa_manager.id,
    )

    assert second.id == first.id


def test_preview_records_plan_hash_for_later_comparison(
    db_session, collecting_plan, msa_manager,
):
    batch = MsaObservationImportService.preview(
        collecting_plan.id, _fixture_path(), actor_id=msa_manager.id,
    )

    assert batch.plan_hash == collecting_plan.plan_hash
    assert batch.file_sha256


def test_import_rejects_blind_code_that_does_not_match_the_plan(
    db_session, collecting_plan, msa_manager, tmp_path,
):
    from openpyxl import Workbook

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "觀測"
    sheet.append(["任務順序", "零件盲碼", "評價人盲碼", "讀值", "量測時間"])
    sheet.append([1, "P99", "A01", "10.001", None])
    path = tmp_path / "wrong_blind_code.xlsx"
    workbook.save(path)

    batch = MsaObservationImportService.preview(
        collecting_plan.id, path, actor_id=msa_manager.id,
    )

    assert batch.issues[0]["code"] == "MSA_OBSERVATION_BLIND_CODE_MISMATCH"
    assert batch.issues[0]["cell"] == "B2"


def test_import_rejects_formula_cells_as_official_readings(
    db_session, collecting_plan, msa_manager, tmp_path,
):
    from openpyxl import Workbook

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "觀測"
    sheet.append(["任務順序", "零件盲碼", "評價人盲碼", "讀值", "量測時間"])
    sheet.append([1, "P02", "A01", "=1+1", None])
    path = tmp_path / "formula.xlsx"
    workbook.save(path)

    batch = MsaObservationImportService.preview(
        collecting_plan.id, path, actor_id=msa_manager.id,
    )

    assert batch.issues[0]["code"] == "MSA_OBSERVATION_FORMULA_NOT_ALLOWED"


def test_import_rejects_non_xlsx_upload(
    db_session, collecting_plan, msa_manager, tmp_path,
):
    path = tmp_path / "observations.csv"
    path.write_text("任務順序,讀值\n1,10.0\n", encoding="utf-8")

    with pytest.raises(MsaValidationError) as error:
        MsaObservationImportService.preview(
            collecting_plan.id, path, actor_id=msa_manager.id,
        )

    assert error.value.code == "MSA_IMPORT_FILE_TYPE_INVALID"
