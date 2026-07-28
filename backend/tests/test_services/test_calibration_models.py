from datetime import date

import pytest
from sqlalchemy.exc import IntegrityError

from backend.models import (
    CalibrationReferenceSnapshot,
    CalibrationTemplate,
    CalibrationTemplatePoint,
    CalibrationTemplateVersion,
    EquipmentCalibrationPoint,
    EquipmentCalibrationReading,
    EquipmentCalibrationRecord,
    MeasurementEquipment,
)


def _template_version(db_session):
    template = CalibrationTemplate(
        template_code="CAL-CALIPER",
        name="游標卡尺",
        equipment_type="游標卡尺",
    )
    db_session.add(template)
    db_session.flush()
    version = CalibrationTemplateVersion(
        template_id=template.id,
        version_no=1,
        procedure_code="WI-CAL-001",
        procedure_name="游標卡尺內校",
        default_repetitions=3,
        environment_requirements={"temperature": {"required": True}},
        allow_limited_use=True,
        status="draft",
    )
    db_session.add(version)
    db_session.flush()
    return version


def _template_point(db_session, **overrides):
    template_version_id = overrides.pop("template_version_id", None)
    if template_version_id is None:
        template_version_id = _template_version(db_session).id
    values = {
        "template_version_id": template_version_id,
        "point_order": 1,
        "point_code": "P01",
        "measurement_mode": "外徑",
        "nominal_value": "10",
        "unit": "mm",
        "reference_input_mode": "certified_value",
        "required_repetitions": 3,
        "error_lower_limit": "-0.02",
        "error_upper_limit": "0.02",
        "evaluation_basis": "all_readings",
        "repeatability_rule": "range",
        "repeatability_limit": "0.01",
        "qualification_scope_code": "OD-0-150",
        "required": True,
    }
    values.update(overrides)
    point = CalibrationTemplatePoint(**values)
    db_session.add(point)
    return point


def _equipment(db_session, equipment_no):
    equipment = MeasurementEquipment(
        equipment_no=equipment_no,
        name="測試游標卡尺",
        equipment_type="游標卡尺",
    )
    db_session.add(equipment)
    db_session.flush()
    return equipment


def _calibration_record(db_session, *, data_level, status="draft"):
    equipment = _equipment(
        db_session,
        f"EQ-{data_level}-{status}-{len(db_session.new)}",
    )
    values = {
        "equipment_id": equipment.id,
        "calibration_type": "internal",
        "calibration_date": date(2026, 7, 28),
        "result": "pending",
        "status": status,
        "data_level": data_level,
    }
    if data_level == "detailed":
        version = _template_version(db_session)
        values.update(
            template_version_id=version.id,
            template_snapshot={"template_code": "CAL-CALIPER", "version_no": 1},
        )
    record = EquipmentCalibrationRecord(**values)
    db_session.add(record)
    db_session.flush()
    return record


def _actual_point(db_session, status):
    record = _calibration_record(
        db_session,
        data_level="detailed",
        status=status,
    )
    template_point = _template_point(
        db_session,
        template_version_id=record.template_version_id,
    )
    db_session.flush()
    point = EquipmentCalibrationPoint(
        calibration_record_id=record.id,
        template_point_id=template_point.id,
        point_order=1,
        point_code="P01",
        measurement_mode="外徑",
        nominal_value="10",
        unit="mm",
        reference_value="10",
        error_lower_limit="-0.02",
        error_upper_limit="0.02",
        evaluation_basis="all_readings",
        repeatability_rule="range",
        repeatability_limit="0.01",
        result="pass",
    )
    db_session.add(point)
    db_session.flush()
    db_session.commit()
    return point


def _reading(db_session, status):
    point = _actual_point(db_session, status)
    reading = EquipmentCalibrationReading(
        calibration_point_id=point.id,
        trial_no=1,
        indicated_value="10.001",
        error_value="0.001",
        result="pass",
    )
    db_session.add(reading)
    db_session.commit()
    return reading


def test_template_point_number_is_unique_within_version(db_session):
    version = _template_version(db_session)
    for code in ("P01", "P01"):
        db_session.add(
            CalibrationTemplatePoint(
                template_version_id=version.id,
                point_order=1,
                point_code=code,
                measurement_mode="外徑",
                nominal_value="10",
                unit="mm",
                reference_input_mode="certified_value",
                required_repetitions=3,
                error_lower_limit="-0.02",
                error_upper_limit="0.02",
                evaluation_basis="all_readings",
                repeatability_rule="range",
                repeatability_limit="0.01",
                qualification_scope_code="OD-0-150",
                required=True,
            )
        )

    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_template_point_requires_positive_repetitions(db_session):
    _template_point(db_session, required_repetitions=0)

    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_template_point_rejects_reversed_error_limits(db_session):
    _template_point(
        db_session,
        error_lower_limit="0.02",
        error_upper_limit="-0.02",
    )

    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


@pytest.mark.parametrize("rule", ["range", "stddev"])
def test_repeatability_rule_requires_non_negative_limit(db_session, rule):
    _template_point(
        db_session,
        repeatability_rule=rule,
        repeatability_limit="-0.001",
    )

    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_summary_legacy_record_may_omit_template_version(db_session):
    record = _calibration_record(db_session, data_level="summary_legacy")

    db_session.commit()

    assert record.template_version_id is None
    assert record.template_snapshot is None


def test_calibration_relationships_are_bidirectional(db_session):
    version = _template_version(db_session)
    version.template.current_approved_version = version
    assert version.template in version.current_for_templates

    equipment = _equipment(db_session, "EQ-RELATIONSHIP")
    record = EquipmentCalibrationRecord(
        equipment_id=equipment.id,
        calibration_type="internal",
        calibration_date=date(2026, 7, 28),
        result="pending",
        status="draft",
        data_level="detailed",
        template_version=version,
        template_snapshot={"template_code": "CAL-CALIPER", "version_no": 1},
    )
    db_session.add(record)
    reference_equipment = _equipment(db_session, "EQ-REFERENCE-SNAPSHOT")
    snapshot = CalibrationReferenceSnapshot(
        calibration_record=record,
        reference_standard_equipment=reference_equipment,
        equipment_no=reference_equipment.equipment_no,
        name=reference_equipment.name,
        snapshot_data={"certificate_no": "REF-001"},
    )
    db_session.add(snapshot)
    assert snapshot in record.reference_snapshots
    assert snapshot in reference_equipment.reference_standard_snapshots

    successor = _calibration_record(db_session, data_level="summary_legacy")
    record.successor = successor
    assert record in successor.predecessors


@pytest.mark.parametrize(
    ("template_version", "template_snapshot"),
    [
        (None, {"template_code": "CAL-CALIPER"}),
        ("present", None),
    ],
)
def test_detailed_record_requires_template_and_snapshot(
    db_session,
    template_version,
    template_snapshot,
):
    equipment = _equipment(
        db_session,
        f"EQ-DETAILED-{template_version}-{template_snapshot is None}",
    )
    version = _template_version(db_session)
    record = EquipmentCalibrationRecord(
        equipment_id=equipment.id,
        calibration_type="internal",
        calibration_date=date(2026, 7, 28),
        result="pending",
        status="draft",
        data_level="detailed",
        template_version_id=version.id if template_version else None,
        template_snapshot=template_snapshot,
    )
    db_session.add(record)

    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_trial_number_is_unique_within_actual_calibration_point(db_session):
    reading = _reading(db_session, "draft")
    db_session.add(
        EquipmentCalibrationReading(
            calibration_point_id=reading.calibration_point_id,
            trial_no=1,
            indicated_value="10.002",
            error_value="0.002",
            result="pass",
        )
    )

    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


@pytest.mark.parametrize("status", ["submitted", "approved"])
@pytest.mark.parametrize("operation", ["update", "reparent", "delete"])
def test_submitted_or_approved_point_is_immutable(
    db_session,
    status,
    operation,
):
    point = _actual_point(db_session, status)
    if operation == "update":
        point.remarks = "嘗試改寫已凍結點位"
    elif operation == "reparent":
        draft_record = _calibration_record(
            db_session,
            data_level="summary_legacy",
        )
        point.calibration_record_id = draft_record.id
    else:
        db_session.delete(point)

    action = "刪除" if operation == "delete" else "修改"
    with pytest.raises(ValueError, match=f"校正點不可{action}"):
        db_session.commit()
    db_session.rollback()


@pytest.mark.parametrize("status", ["submitted", "approved"])
def test_draft_point_cannot_be_reparented_into_frozen_record(
    db_session,
    status,
):
    point = _actual_point(db_session, "draft")
    frozen_record = _calibration_record(
        db_session,
        data_level="summary_legacy",
        status=status,
    )
    point.calibration_record_id = frozen_record.id

    with pytest.raises(ValueError, match="校正點不可修改"):
        db_session.commit()
    db_session.rollback()


@pytest.mark.parametrize("status", ["submitted", "approved"])
def test_submitted_or_approved_reading_cannot_be_updated(db_session, status):
    reading = _reading(db_session, status)
    reading.indicated_value = "99"

    with pytest.raises(ValueError, match="原始讀值不可修改"):
        db_session.commit()
    db_session.rollback()


@pytest.mark.parametrize("status", ["submitted", "approved"])
def test_submitted_or_approved_reading_cannot_be_deleted(db_session, status):
    reading = _reading(db_session, status)
    db_session.delete(reading)

    with pytest.raises(ValueError, match="原始讀值不可刪除"):
        db_session.commit()
    db_session.rollback()
