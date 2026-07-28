from datetime import date

import pytest
from sqlalchemy import inspect as sa_inspect
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


@pytest.mark.parametrize(
    ("model", "expected_attributes"),
    [
        (
            CalibrationTemplateVersion,
            {
                "revision_reason",
                "submitted_by",
                "submitted_at",
                "approval_reason",
                "rejection_reason",
                "successor_version_id",
            },
        ),
        (
            CalibrationTemplatePoint,
            {
                "qualification_range_start",
                "qualification_range_end",
                "uncertainty_required",
                "instruction",
            },
        ),
        (
            EquipmentCalibrationRecord,
            {
                "procedure_code",
                "procedure_name",
                "calibration_location",
                "started_at",
                "completed_at",
            },
        ),
        (
            EquipmentCalibrationPoint,
            {
                "reference_input_mode",
                "required_repetitions",
                "qualification_range_start",
                "qualification_range_end",
                "uncertainty_required",
                "required",
                "mean_error",
                "mean_correction",
                "minimum_error",
                "maximum_error",
                "error_range",
                "sample_stddev",
                "expanded_uncertainty",
                "coverage_factor",
                "completed_reading_count",
            },
        ),
        (
            EquipmentCalibrationReading,
            {
                "standard_reading",
                "effective_reference",
                "correction_value",
                "last_modified_by",
                "last_modified_at",
                "revision_reason",
            },
        ),
        (
            CalibrationReferenceSnapshot,
            {
                "model",
                "serial_no",
                "range_min",
                "range_max",
                "resolution",
                "unit",
                "approved_calibration_record_id",
                "calibration_date",
                "result",
                "data_hash",
            },
        ),
    ],
)
def test_calibration_models_expose_approved_design_fields(
    model,
    expected_attributes,
):
    actual_attributes = {
        attribute.key
        for attribute in sa_inspect(model).column_attrs
    }
    assert expected_attributes <= actual_attributes


def test_calibration_models_expose_approved_design_relationships():
    version_relationships = {
        relationship.key
        for relationship in sa_inspect(
            CalibrationTemplateVersion
        ).relationships
    }
    snapshot_relationships = {
        relationship.key
        for relationship in sa_inspect(
            CalibrationReferenceSnapshot
        ).relationships
    }

    assert {"successor_version", "predecessor_versions"} <= (
        version_relationships
    )
    assert "approved_calibration_record" in snapshot_relationships


def test_template_version_has_single_approved_partial_unique_index():
    indexes = {
        index.name: index
        for index in CalibrationTemplateVersion.__table__.indexes
    }
    index = indexes.get("uq_calibration_template_one_approved")

    assert index is not None
    assert index.unique is True
    assert str(index.dialect_options["postgresql"]["where"]) == (
        '"狀態" = \'approved\''
    )
    assert str(index.dialect_options["sqlite"]["where"]) == (
        '"狀態" = \'approved\''
    )


@pytest.mark.parametrize(
    ("model", "attribute_name", "expected_default"),
    [
        (CalibrationTemplatePoint, "uncertainty_required", "false"),
        (CalibrationTemplatePoint, "required", "true"),
        (EquipmentCalibrationPoint, "uncertainty_required", "false"),
        (EquipmentCalibrationPoint, "required", "true"),
        (EquipmentCalibrationPoint, "completed_reading_count", "0"),
    ],
)
def test_calibration_boolean_and_count_defaults_match_migration(
    model,
    attribute_name,
    expected_default,
):
    column = getattr(model, attribute_name).property.columns[0]

    assert column.nullable is False
    assert column.server_default is not None
    assert str(column.server_default.arg).lower() == expected_default


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


def _sibling_template_version(
    db_session,
    template,
    version_no,
    *,
    status="draft",
):
    version = CalibrationTemplateVersion(
        template=template,
        version_no=version_no,
        procedure_code=f"WI-CAL-{version_no:03d}",
        procedure_name=f"游標卡尺校正第 {version_no} 版",
        default_repetitions=3,
        environment_requirements={},
        status=status,
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
        reference_input_mode="certified_value",
        required_repetitions=3,
        uncertainty_required=False,
        required=True,
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


def test_template_version_rejects_unknown_status(db_session):
    version = _template_version(db_session)
    version.status = "unknown"

    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_template_point_rejects_reversed_qualification_range(db_session):
    _template_point(
        db_session,
        qualification_range_start="150",
        qualification_range_end="0",
    )

    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


@pytest.mark.parametrize(
    ("field_name", "invalid_value"),
    [
        ("reference_input_mode", "unknown"),
        ("evaluation_basis", "unknown"),
        ("repeatability_rule", "unknown"),
    ],
)
def test_template_point_rejects_unknown_rule_value(
    db_session,
    field_name,
    invalid_value,
):
    point = _template_point(db_session)
    setattr(point, field_name, invalid_value)

    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


@pytest.mark.parametrize(
    "status",
    ["submitted", "rejected", "approved", "superseded"],
)
def test_controlled_template_version_rejects_new_point(
    db_session,
    status,
):
    version = _template_version(db_session)
    version.status = status
    db_session.commit()
    _template_point(
        db_session,
        template_version_id=version.id,
        point_order=2,
        point_code="P02",
    )

    with pytest.raises(ValueError, match="模板校正點"):
        db_session.commit()
    db_session.rollback()


def test_draft_template_version_allows_new_point(db_session):
    version = _template_version(db_session)
    point = _template_point(
        db_session,
        template_version_id=version.id,
        point_order=2,
        point_code="P02",
    )

    db_session.commit()

    assert point.template_version_id == version.id


def test_template_rejects_two_approved_versions(db_session):
    first = _template_version(db_session)
    _sibling_template_version(
        db_session,
        first.template,
        2,
        status="approved",
    )
    first.status = "approved"

    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


@pytest.mark.parametrize("status", ["in_progress", "ready_for_submission"])
def test_detailed_record_accepts_execution_status(db_session, status):
    record = _calibration_record(
        db_session,
        data_level="detailed",
        status=status,
    )

    db_session.commit()

    assert record.status == status


@pytest.mark.parametrize(
    ("field_name", "invalid_value"),
    [
        ("required_repetitions", 0),
        ("completed_reading_count", -1),
        ("completed_reading_count", 4),
    ],
)
def test_actual_point_rejects_invalid_count(
    db_session,
    field_name,
    invalid_value,
):
    point = _actual_point(db_session, "draft")
    setattr(point, field_name, invalid_value)

    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_actual_point_rejects_reversed_qualification_range(db_session):
    point = _actual_point(db_session, "draft")
    point.qualification_range_start = "150"
    point.qualification_range_end = "0"

    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


@pytest.mark.parametrize(
    ("field_name", "invalid_value"),
    [
        ("reference_input_mode", "unknown"),
        ("evaluation_basis", "unknown"),
        ("repeatability_rule", "unknown"),
        ("result", "unknown"),
    ],
)
def test_actual_point_rejects_unknown_rule_value(
    db_session,
    field_name,
    invalid_value,
):
    point = _actual_point(db_session, "draft")
    setattr(point, field_name, invalid_value)

    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_paired_reading_point_allows_empty_fixed_reference(db_session):
    point = _actual_point(db_session, "draft")
    point.reference_input_mode = "paired_reading"
    point.reference_value = None

    db_session.commit()

    assert point.reference_value is None


def test_certified_value_point_requires_fixed_reference(db_session):
    point = _actual_point(db_session, "draft")
    point.reference_value = None

    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_draft_reading_placeholder_allows_empty_measurement(db_session):
    point = _actual_point(db_session, "draft")
    reading = EquipmentCalibrationReading(
        calibration_point_id=point.id,
        trial_no=1,
    )
    db_session.add(reading)

    db_session.commit()

    assert reading.indicated_value is None
    assert reading.result == "pending"


def test_reading_rejects_unknown_result(db_session):
    reading = _reading(db_session, "draft")
    reading.result = "unknown"

    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


@pytest.mark.parametrize("status", ["approved", "superseded"])
@pytest.mark.parametrize("operation", ["update", "delete"])
def test_approved_or_superseded_template_version_is_immutable(
    db_session,
    status,
    operation,
):
    version = _template_version(db_session)
    version.status = status
    db_session.commit()

    if operation == "update":
        version.procedure_name = "嘗試改寫受控版本"
    else:
        db_session.delete(version)

    with pytest.raises(ValueError, match="模板版本"):
        db_session.commit()
    db_session.rollback()


def test_approved_template_version_allows_controlled_supersession(db_session):
    version = _template_version(db_session)
    version.status = "approved"
    db_session.commit()
    successor = _sibling_template_version(
        db_session,
        version.template,
        2,
        status="submitted",
    )

    version.status = "superseded"
    version.successor_version = successor
    version.row_version += 1
    db_session.flush()
    successor.status = "approved"
    version.template.current_approved_version = successor
    db_session.commit()

    assert version.status == "superseded"
    assert version.successor_version is successor
    assert successor.status == "approved"
    assert version.template.current_approved_version is successor


@pytest.mark.parametrize(
    ("case_name", "row_version_delta"),
    [
        ("self", 1),
        ("cross_template", 1),
        ("backward", 1),
        ("row_version_unchanged", 0),
        ("row_version_jump", 2),
    ],
)
def test_controlled_supersession_rejects_invalid_successor(
    db_session,
    case_name,
    row_version_delta,
):
    first = _template_version(db_session)
    if case_name == "self":
        old = first
        successor = first
    elif case_name == "cross_template":
        old = first
        other_template = CalibrationTemplate(
            template_code="CAL-CROSS-TEMPLATE",
            name="跨模板",
            equipment_type="游標卡尺",
        )
        db_session.add(other_template)
        successor = _sibling_template_version(
            db_session,
            other_template,
            2,
            status="submitted",
        )
    elif case_name == "backward":
        successor = first
        old = _sibling_template_version(
            db_session,
            first.template,
            2,
            status="approved",
        )
    else:
        old = first
        successor = _sibling_template_version(
            db_session,
            first.template,
            2,
            status="submitted",
        )
    old.status = "approved"
    db_session.commit()

    next_row_version = old.row_version + row_version_delta
    old.status = "superseded"
    if case_name == "self":
        with pytest.raises(ValueError, match="後繼版本"):
            old.successor_version = successor
        db_session.rollback()
        return
    old.successor_version = successor
    old.row_version = next_row_version

    expected_message = (
        "資料版本" if case_name.startswith("row_version") else "後繼版本"
    )
    with pytest.raises(ValueError, match=expected_message):
        db_session.commit()
    db_session.rollback()


def test_controlled_supersession_rejects_two_version_cycle(db_session):
    old = _template_version(db_session)
    successor = _sibling_template_version(
        db_session,
        old.template,
        2,
        status="submitted",
    )
    old.status = "approved"
    db_session.commit()

    successor_id = successor.id
    old_row_version = old.row_version
    old.status = "superseded"
    old.successor_version_id = successor_id
    old.row_version = old_row_version + 1
    db_session.commit()
    successor.status = "approved"
    db_session.commit()

    successor_row_version = successor.row_version
    successor.status = "superseded"
    successor.successor_version = old
    successor.row_version = successor_row_version + 1

    with pytest.raises(ValueError, match="後繼版本"):
        db_session.commit()
    db_session.rollback()


@pytest.mark.parametrize(
    "status",
    ["submitted", "approved", "rejected", "superseded"],
)
@pytest.mark.parametrize("operation", ["update", "reparent", "delete"])
def test_controlled_template_point_is_immutable(
    db_session,
    status,
    operation,
):
    point = _template_point(db_session)
    version = db_session.get(
        CalibrationTemplateVersion,
        point.template_version_id,
    )
    version.status = status
    db_session.commit()

    if operation == "update":
        point.instruction = "嘗試改寫受控校正點"
    elif operation == "reparent":
        target_template = CalibrationTemplate(
            template_code=f"CAL-TARGET-{status}",
            name="重掛目標模板",
            equipment_type="游標卡尺",
        )
        target_version = CalibrationTemplateVersion(
            template=target_template,
            version_no=1,
            procedure_code="WI-CAL-TARGET",
            procedure_name="重掛目標程序",
            default_repetitions=3,
            environment_requirements={},
            status="draft",
        )
        db_session.add(target_version)
        db_session.flush()
        point.template_version_id = target_version.id
    else:
        db_session.delete(point)

    with pytest.raises(ValueError, match="模板校正點"):
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
        approved_calibration_record=_calibration_record(
            db_session,
            data_level="summary_legacy",
            status="approved",
        ),
        equipment_no=reference_equipment.equipment_no,
        name=reference_equipment.name,
        calibration_date=date(2026, 7, 1),
        result="pass",
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
