"""端到端分析交易、結果快照與三層判定測試。"""

from datetime import date, timedelta

import pytest

from backend.extensions import db
from backend.models import (
    EquipmentCalibrationRecord,
    MeasurementEquipment,
    MsaCriteriaProfile,
    MsaCriteriaVersion,
    MsaResultVersion,
    MsaWorkflowDecision,
    User,
)
from backend.services import msa_analysis_service as analysis_module
from backend.services.msa_analysis_service import MsaAnalysisService
from backend.services.msa_design_service import MsaDesignService
from backend.services.msa_errors import MsaConflict, MsaValidationError
from backend.services.msa_observation_service import MsaObservationService
from backend.services.msa_study_service import MsaStudyService


@pytest.fixture
def msa_manager(db_session):
    user = User(username="msa_analysis_manager", password="x")
    db_session.add(user)
    db_session.commit()
    return user


def _criteria(db_session, name, thresholds=None):
    profile = MsaCriteriaProfile(name=name)
    db_session.add(profile)
    db_session.flush()
    version = MsaCriteriaVersion(
        profile_id=profile.id,
        version_no=1,
        method_version="MSA4-1.0",
        effective_date=date(2026, 1, 1),
        thresholds=thresholds or {
            "grr_accept_max": 10.0,
            "grr_conditional_max": 30.0,
            "ndc_min": 5,
            "alpha": 0.05,
        },
        status="approved",
    )
    db_session.add(version)
    db_session.flush()
    profile.current_version_id = version.id
    db_session.commit()
    return profile


def _gauge(db_session, equipment_no):
    equipment = MeasurementEquipment(
        equipment_no=equipment_no, name="測試量具", status="active",
        calibration_type="external", resolution="0.001", unit="mm",
    )
    db_session.add(equipment)
    db_session.flush()
    db_session.add(EquipmentCalibrationRecord(
        equipment_id=equipment.id,
        calibration_type="external",
        calibration_date=date.today() - timedelta(days=10),
        next_due_date=date.today() + timedelta(days=300),
        result="pass", status="approved",
    ))
    db_session.commit()
    return equipment


# 3 零件 × 2 評價人 × 3 試驗；零件差異大、量測變異小 → %GRR 應該很小
_READINGS = {
    ("P01", "A01"): [10.001, 10.002, 10.001],
    ("P01", "A02"): [10.003, 10.002, 10.003],
    ("P02", "A01"): [10.301, 10.302, 10.301],
    ("P02", "A02"): [10.303, 10.302, 10.303],
    ("P03", "A01"): [10.601, 10.602, 10.601],
    ("P03", "A02"): [10.603, 10.602, 10.603],
}


def _build_plan(db_session, msa_manager, thresholds=None, **plan_over):
    profile = _criteria(db_session, f"分析準則-{id(plan_over)}", thresholds)
    study = MsaStudyService.create(
        {
            "study_type": "grr_anova",
            "measurement_purpose": "product_control",
            "characteristic": "外徑",
            "unit": "mm",
            "lsl": 9.5,
            "usl": 11.5,
            "criteria_profile_id": profile.id,
            "primary_executor_id": msa_manager.id,
        },
        actor_id=msa_manager.id,
    )
    gauge = _gauge(db_session, f"EQ-ANALYSIS-{study.id}")
    payload = {
        "method_code": "MSA4_GRR_ANOVA_1_0",
        "part_count": 3,
        "appraiser_count": 2,
        "trial_count": 3,
        "random_seed": 99,
        "percent_basis": "tolerance",
        "equipment": [{"equipment_id": gauge.id, "role": "primary_gauge"}],
        "parts": [{"part_identifier": f"件-{index}"} for index in range(1, 4)],
        "appraisers": [{"name": "甲"}, {"name": "乙"}],
    }
    payload.update(plan_over)
    plan = MsaDesignService.create_plan(
        study.id, payload, actor_id=msa_manager.id,
    )
    return MsaDesignService.freeze(plan.id, actor_id=msa_manager.id)


def _fill(plan, msa_manager, readings=None):
    values = readings or _READINGS
    part_codes = {part.id: part.blind_code for part in plan.parts}
    appraiser_codes = {row.id: row.blind_code for row in plan.appraisers}
    for item in plan.randomized_order:
        key = (
            part_codes[item["part_id"]], appraiser_codes[item["appraiser_id"]],
        )
        value = values[key][item["trial_no"] - 1]
        MsaObservationService.record(
            plan.id,
            {"task_order": item["requested_order"], "numeric_value": str(value)},
            actor_id=msa_manager.id,
            can_manage=True,
        )
    # 實際流程是先驗證完整性再分析
    MsaObservationService.validate(plan.id, actor_id=msa_manager.id)
    return plan


@pytest.fixture
def complete_grr_plan(db_session, msa_manager):
    return _fill(_build_plan(db_session, msa_manager), msa_manager)


# ---------------------------------------------------------------------------
# 分析交易
# ---------------------------------------------------------------------------


def test_analyze_persists_exact_input_hash_and_result_snapshot(
    db_session, complete_grr_plan, msa_manager,
):
    result = MsaAnalysisService.analyze(
        complete_grr_plan.id,
        actor_id=msa_manager.id,
        expected_plan_hash=complete_grr_plan.plan_hash,
    )

    assert len(result.data_hash) == 64
    assert result.method_code == "MSA4_GRR_ANOVA_1_0"
    assert result.code_version == analysis_module.CODE_VERSION
    assert result.criteria_snapshot["version_id"]
    assert result.status == "analyzed"
    assert result.result_version_no == 1


def test_raw_data_summary_carries_the_complete_analysis_input(
    db_session, complete_grr_plan, msa_manager,
):
    result = MsaAnalysisService.analyze(
        complete_grr_plan.id, actor_id=msa_manager.id,
    )
    summary = result.raw_data_summary

    assert set(summary) == {
        "study", "plan", "effective_observations", "method", "criteria",
    }
    assert len(summary["effective_observations"]) == 18
    assert summary["plan"]["plan_hash"] == complete_grr_plan.plan_hash
    assert summary["method"]["code"] == "MSA4_GRR_ANOVA_1_0"
    assert summary["method"]["study_variation_multiplier"] == 6.0


def test_analyze_moves_study_to_analyzed_and_records_decision(
    db_session, complete_grr_plan, msa_manager,
):
    result = MsaAnalysisService.analyze(
        complete_grr_plan.id, actor_id=msa_manager.id,
    )

    db_session.refresh(complete_grr_plan.study)
    assert complete_grr_plan.study.status == "analyzed"
    assert complete_grr_plan.study.current_result_version_id == result.id
    decision = MsaWorkflowDecision.query.filter_by(
        study_id=result.study_id, action="analyze",
    ).one()
    assert decision.to_status == "analyzed"


def test_reanalysis_creates_a_new_version_without_touching_the_old_one(
    db_session, complete_grr_plan, msa_manager,
):
    first = MsaAnalysisService.analyze(
        complete_grr_plan.id, actor_id=msa_manager.id,
    )
    first_hash = first.data_hash
    first_statistics = dict(first.statistics)

    second = MsaAnalysisService.analyze(
        complete_grr_plan.id, actor_id=msa_manager.id,
    )

    db_session.refresh(first)
    assert second.id != first.id
    assert second.result_version_no == 2
    assert first.data_hash == first_hash
    assert first.statistics == first_statistics


def test_stale_plan_hash_is_reported_as_data_changed(
    db_session, complete_grr_plan, msa_manager,
):
    with pytest.raises(MsaConflict) as error:
        MsaAnalysisService.analyze(
            complete_grr_plan.id,
            actor_id=msa_manager.id,
            expected_plan_hash="0" * 64,
        )

    assert error.value.code == "MSA_DATA_CHANGED"
    assert MsaResultVersion.query.count() == 0


def test_incomplete_data_blocks_analysis(db_session, msa_manager):
    plan = _build_plan(db_session, msa_manager)
    MsaObservationService.record(
        plan.id, {"task_order": 1, "numeric_value": "10.0"},
        actor_id=msa_manager.id, can_manage=True,
    )

    with pytest.raises(MsaValidationError) as error:
        MsaAnalysisService.analyze(plan.id, actor_id=msa_manager.id)

    assert error.value.code == "MSA_DATA_INCOMPLETE"
    assert MsaResultVersion.query.count() == 0


def test_unfrozen_plan_cannot_be_analyzed(db_session, msa_manager):
    profile = _criteria(db_session, "未凍結分析準則")
    study = MsaStudyService.create(
        {
            "study_type": "grr_anova",
            "measurement_purpose": "product_control",
            "characteristic": "外徑", "unit": "mm",
            "lsl": 9.5, "usl": 11.5,
            "criteria_profile_id": profile.id,
        },
        actor_id=msa_manager.id,
    )
    gauge = _gauge(db_session, "EQ-ANALYSIS-DRAFT")
    plan = MsaDesignService.create_plan(
        study.id,
        {
            "method_code": "MSA4_GRR_ANOVA_1_0",
            "part_count": 3, "appraiser_count": 2, "trial_count": 3,
            "random_seed": 1,
            "equipment": [{"equipment_id": gauge.id, "role": "primary_gauge"}],
            "parts": [{"part_identifier": f"件-{i}"} for i in range(1, 4)],
            "appraisers": [{"name": "甲"}, {"name": "乙"}],
        },
        actor_id=msa_manager.id,
    )

    with pytest.raises(MsaConflict) as error:
        MsaAnalysisService.analyze(plan.id, actor_id=msa_manager.id)

    assert error.value.code == "MSA_PLAN_NOT_FROZEN"


def test_non_finite_engine_output_rolls_back_the_whole_transaction(
    db_session, complete_grr_plan, msa_manager, monkeypatch,
):
    class _Broken:
        applicability = {"applicable": True}
        statistics = {"grr": float("nan")}
        chart_data = {}
        warnings = ()

    descriptor = analysis_module.MsaMethodRegistry.get("MSA4_GRR_ANOVA_1_0")
    monkeypatch.setattr(
        type(descriptor), "engine",
        property(lambda self: lambda *_args, **_kwargs: _Broken()),
    )

    with pytest.raises(MsaValidationError) as error:
        MsaAnalysisService.analyze(
            complete_grr_plan.id, actor_id=msa_manager.id,
        )

    assert error.value.code == "MSA_NUMERIC_FAILURE"
    db.session.rollback()
    assert MsaResultVersion.query.count() == 0
    db_session.refresh(complete_grr_plan.study)
    assert complete_grr_plan.study.status == "ready_for_analysis"


# ---------------------------------------------------------------------------
# 三層判定
# ---------------------------------------------------------------------------


def test_conclusion_keeps_three_layers_separate(
    db_session, complete_grr_plan, msa_manager,
):
    result = MsaAnalysisService.analyze(
        complete_grr_plan.id, actor_id=msa_manager.id,
    )

    assert set(result.conclusion) == {
        "statistical_result", "system_disposition", "engineering_judgment",
        "reasons", "percent_basis",
    }
    assert result.conclusion["engineering_judgment"] is None
    assert result.conclusion["percent_basis"] == "tolerance"


def test_low_grr_is_acceptable(db_session, complete_grr_plan, msa_manager):
    result = MsaAnalysisService.analyze(
        complete_grr_plan.id, actor_id=msa_manager.id,
    )

    assert result.conclusion["system_disposition"] == "acceptable"
    assert result.conclusion["statistical_result"]["percent_grr"] < 10


def test_high_grr_is_unacceptable(db_session, msa_manager):
    """把允收與條件上限壓到極低，讓同一份資料落到不可接受。"""
    plan = _fill(
        _build_plan(
            db_session, msa_manager,
            thresholds={
                "grr_accept_max": 0.01,
                "grr_conditional_max": 0.02,
                "ndc_min": 5,
                "alpha": 0.05,
            },
        ),
        msa_manager,
    )

    result = MsaAnalysisService.analyze(plan.id, actor_id=msa_manager.id)

    assert result.conclusion["system_disposition"] == "unacceptable"


def test_grr_between_thresholds_is_conditional(db_session, msa_manager):
    plan = _fill(
        _build_plan(
            db_session, msa_manager,
            thresholds={
                "grr_accept_max": 0.01,
                "grr_conditional_max": 50.0,
                "ndc_min": 5,
                "alpha": 0.05,
            },
        ),
        msa_manager,
    )

    result = MsaAnalysisService.analyze(plan.id, actor_id=msa_manager.id)

    assert result.conclusion["system_disposition"] == (
        "conditionally_acceptable"
    )


def test_insufficient_ndc_downgrades_from_acceptable(
    db_session, msa_manager,
):
    plan = _fill(
        _build_plan(
            db_session, msa_manager,
            thresholds={
                "grr_accept_max": 10.0,
                "grr_conditional_max": 30.0,
                "ndc_min": 999,
                "alpha": 0.05,
            },
        ),
        msa_manager,
    )

    result = MsaAnalysisService.analyze(plan.id, actor_id=msa_manager.id)

    assert result.conclusion["system_disposition"] == (
        "conditionally_acceptable"
    )
    assert any(
        "ndc" in reason for reason in result.conclusion["reasons"]
    )


def test_percent_basis_is_recorded_and_not_chosen_opportunistically(
    db_session, msa_manager,
):
    plan = _fill(
        _build_plan(db_session, msa_manager, percent_basis="study_variation"),
        msa_manager,
    )

    result = MsaAnalysisService.analyze(plan.id, actor_id=msa_manager.id)

    assert result.criteria_snapshot["percent_basis"] == "study_variation"
    assert result.criteria_snapshot["percent_basis_source"] == "explicit"
    assert result.conclusion["percent_basis"] == "study_variation"


def test_default_percent_basis_is_marked_as_default(db_session, msa_manager):
    plan = _build_plan(db_session, msa_manager)
    plan_without_choice = plan.criteria_snapshot

    assert plan_without_choice["percent_basis"] == "tolerance"
    assert plan_without_choice["percent_basis_source"] == "explicit"
