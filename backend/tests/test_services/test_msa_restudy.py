"""MSA 再研究要求的觸發、冪等與承接測試。"""

from datetime import date, timedelta

import pytest

from backend.extensions import db
from backend.models import (
    EquipmentCalibrationRecord,
    MeasurementEquipment,
    MsaCriteriaProfile,
    MsaCriteriaVersion,
    MsaRestudyRequest,
    MsaStudy,
    MsaStudyEquipment,
    User,
)
from backend.services.msa_equipment_service import MsaEquipmentService
from backend.services.msa_errors import (
    MsaConflict,
    MsaNotFound,
    MsaValidationError,
)
from backend.services.msa_restudy_service import MsaRestudyService
from backend.services.msa_study_service import MsaStudyService


@pytest.fixture
def msa_manager(db_session):
    user = User(username="msa_restudy_manager", password="x")
    db_session.add(user)
    db_session.commit()
    return user


@pytest.fixture
def linked_primary_gauge(db_session):
    equipment = MeasurementEquipment(
        equipment_no="EQ-RESTUDY-1", name="量具", status="active",
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
    return equipment


def _approved_study(db_session, msa_manager, gauge, *, next_due_date=None):
    profile = MsaCriteriaProfile(name=f"再研究準則-{gauge.id}")
    db_session.add(profile)
    db_session.flush()
    version = MsaCriteriaVersion(
        profile_id=profile.id, version_no=1, method_version="MSA4-1.0",
        effective_date=date(2026, 1, 1),
        thresholds={"grr_accept_max": 10, "grr_conditional_max": 30},
        status="approved",
    )
    db_session.add(version)
    db_session.flush()
    profile.current_version_id = version.id
    db_session.commit()

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
    study.status = "approved"
    study.next_due_date = next_due_date
    db_session.add(MsaStudyEquipment(
        study_id=study.id, equipment_id=gauge.id, role="primary_gauge",
    ))
    db_session.commit()
    return study


@pytest.fixture
def approved_study(db_session, msa_manager, linked_primary_gauge):
    return _approved_study(db_session, msa_manager, linked_primary_gauge)


def _maintenance_event(db_session, gauge, msa_manager):
    return MsaEquipmentService.create_status_event(
        gauge.id,
        {
            "event_type": "maintenance",
            "expected_status": "active",
            "target_status": "maintenance",
            "reason": "更換測頭",
            "triggers_msa_restudy": True,
        },
        actor_id=msa_manager.id,
    )


# ---------------------------------------------------------------------------
# 事件觸發
# ---------------------------------------------------------------------------


def test_equipment_maintenance_creates_restudy_for_approved_studies(
    db_session, approved_study, linked_primary_gauge, msa_manager,
):
    _maintenance_event(db_session, linked_primary_gauge, msa_manager)

    requests = MsaRestudyRequest.query.filter_by(
        source_study_id=approved_study.id,
        trigger_type="equipment_maintenance",
    ).all()
    assert len(requests) == 1
    assert requests[0].status == "open"
    assert requests[0].trigger_payload["event_type"] == "maintenance"


def test_same_source_event_does_not_duplicate_restudy(
    db_session, approved_study, linked_primary_gauge, msa_manager,
):
    event = _maintenance_event(db_session, linked_primary_gauge, msa_manager)

    first = MsaRestudyService.from_equipment_event(event["id"])
    second = MsaRestudyService.from_equipment_event(event["id"])

    assert second.id == first.id
    assert MsaRestudyRequest.query.filter_by(
        source_study_id=approved_study.id,
    ).count() == 1


def test_events_not_marked_for_restudy_create_nothing(
    db_session, approved_study, linked_primary_gauge, msa_manager,
):
    MsaEquipmentService.create_status_event(
        linked_primary_gauge.id,
        {
            "event_type": "maintenance",
            "expected_status": "active",
            "target_status": "maintenance",
            "reason": "例行清潔",
            "triggers_msa_restudy": False,
        },
        actor_id=msa_manager.id,
    )

    assert MsaRestudyRequest.query.count() == 0


def test_draft_studies_do_not_receive_restudy_requests(
    db_session, msa_manager, linked_primary_gauge,
):
    """只有結論仍生效的核准研究需要重新確認。"""
    study = _approved_study(db_session, msa_manager, linked_primary_gauge)
    study.status = "draft"
    db_session.commit()

    _maintenance_event(db_session, linked_primary_gauge, msa_manager)

    assert MsaRestudyRequest.query.count() == 0


@pytest.mark.parametrize(
    ("outcome", "trigger_type"),
    [("fail", "calibration_failed"), ("expired", "calibration_expired")],
)
def test_calibration_outcomes_create_restudy_requests(
    db_session, approved_study, linked_primary_gauge, msa_manager,
    outcome, trigger_type,
):
    MsaRestudyService.from_calibration_outcome(
        linked_primary_gauge.id, 12345, outcome, actor_id=msa_manager.id,
    )

    requests = MsaRestudyRequest.query.filter_by(
        source_study_id=approved_study.id, trigger_type=trigger_type,
    ).all()
    assert len(requests) == 1


def test_unsupported_calibration_outcome_is_rejected(
    db_session, approved_study, linked_primary_gauge, msa_manager,
):
    with pytest.raises(MsaValidationError) as error:
        MsaRestudyService.from_calibration_outcome(
            linked_primary_gauge.id, 1, "unknown", actor_id=msa_manager.id,
        )

    assert error.value.code == "MSA_RESTUDY_TRIGGER_INVALID"


# ---------------------------------------------------------------------------
# 人工與週期觸發
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "trigger_type",
    [
        "measurement_method_changed", "fixture_changed", "software_changed",
        "appraiser_population_changed", "product_or_spec_changed",
        "conditional_action_due",
    ],
)
def test_manual_triggers_are_supported(
    db_session, approved_study, msa_manager, trigger_type,
):
    request = MsaRestudyService.create_manual(
        {
            "source_study_id": approved_study.id,
            "trigger_type": trigger_type,
            "source_entity_type": "manual",
            "source_entity_id": 1,
            "due_date": "2026-12-31",
        },
        actor_id=msa_manager.id,
    )

    assert request.trigger_type == trigger_type
    assert request.due_date.isoformat() == "2026-12-31"


def test_manual_trigger_type_must_be_controlled(
    db_session, approved_study, msa_manager,
):
    with pytest.raises(MsaValidationError) as error:
        MsaRestudyService.create_manual(
            {
                "source_study_id": approved_study.id,
                "trigger_type": "隨便打的理由",
            },
            actor_id=msa_manager.id,
        )

    assert error.value.code == "MSA_RESTUDY_TRIGGER_INVALID"


def test_periodic_scan_is_idempotent(
    db_session, msa_manager, linked_primary_gauge,
):
    study = _approved_study(
        db_session, msa_manager, linked_primary_gauge,
        next_due_date=date(2026, 6, 30),
    )

    first = MsaRestudyService.create_periodic_due(date(2026, 7, 27))
    second = MsaRestudyService.create_periodic_due(date(2026, 7, 27))

    assert len(first) == 1
    assert second[0].id == first[0].id
    assert MsaRestudyRequest.query.filter_by(
        source_study_id=study.id, trigger_type="periodic_due",
    ).count() == 1


def test_periodic_scan_skips_studies_not_yet_due(
    db_session, msa_manager, linked_primary_gauge,
):
    _approved_study(
        db_session, msa_manager, linked_primary_gauge,
        next_due_date=date(2027, 1, 1),
    )

    assert MsaRestudyService.create_periodic_due(date(2026, 7, 27)) == []


# ---------------------------------------------------------------------------
# 承接
# ---------------------------------------------------------------------------


def test_start_creates_a_draft_study_referencing_the_previous_one(
    db_session, approved_study, linked_primary_gauge, msa_manager,
):
    _maintenance_event(db_session, linked_primary_gauge, msa_manager)
    request = MsaRestudyRequest.query.one()

    started = MsaRestudyService.start(request.id, actor_id=msa_manager.id)

    new_study = db.session.get(MsaStudy, started.new_study_id)
    assert started.status == "in_progress"
    assert new_study.status == "draft"
    assert new_study.previous_approved_study_id == approved_study.id
    assert new_study.characteristic == approved_study.characteristic
    assert new_study.study_no != approved_study.study_no


def test_start_does_not_copy_any_observations(
    db_session, approved_study, linked_primary_gauge, msa_manager,
):
    _maintenance_event(db_session, linked_primary_gauge, msa_manager)
    request = MsaRestudyRequest.query.one()

    started = MsaRestudyService.start(request.id, actor_id=msa_manager.id)

    new_study = db.session.get(MsaStudy, started.new_study_id)
    assert new_study.plan_versions == []
    assert new_study.result_versions == []
    assert new_study.current_result_version_id is None


def test_restarting_an_already_started_request_is_a_conflict(
    db_session, approved_study, linked_primary_gauge, msa_manager,
):
    _maintenance_event(db_session, linked_primary_gauge, msa_manager)
    request = MsaRestudyRequest.query.one()
    MsaRestudyService.start(request.id, actor_id=msa_manager.id)

    with pytest.raises(MsaConflict) as error:
        MsaRestudyService.start(request.id, actor_id=msa_manager.id)

    assert error.value.code == "MSA_RESTUDY_ALREADY_STARTED"


def test_missing_request_is_reported_as_not_found(db_session, msa_manager):
    with pytest.raises(MsaNotFound) as error:
        MsaRestudyService.start(999999, actor_id=msa_manager.id)

    assert error.value.code == "MSA_RESTUDY_REQUEST_NOT_FOUND"


def test_list_is_bounded_and_sorted_by_due_date(
    db_session, approved_study, msa_manager,
):
    MsaRestudyService.create_manual(
        {
            "source_study_id": approved_study.id,
            "trigger_type": "fixture_changed",
            "source_entity_id": 1,
            "due_date": "2026-12-31",
        },
        actor_id=msa_manager.id,
    )
    MsaRestudyService.create_manual(
        {
            "source_study_id": approved_study.id,
            "trigger_type": "software_changed",
            "source_entity_id": 2,
            "due_date": "2026-08-31",
        },
        actor_id=msa_manager.id,
    )

    page = MsaRestudyService.list({"page": 1, "page_size": 25})

    assert set(page) == {"items", "page", "page_size", "total"}
    assert page["total"] == 2
    assert page["items"][0]["due_date"] == "2026-08-31"


def test_list_rejects_unknown_query_fields(db_session):
    with pytest.raises(MsaValidationError) as error:
        MsaRestudyService.list({"unexpected": "1"})

    assert error.value.code == "MSA_UNKNOWN_FIELDS"
