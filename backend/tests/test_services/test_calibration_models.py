from datetime import date, datetime, timedelta, timezone

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
    User,
)


BLANK_TEMPLATE_REASON_CASES = (
    " ",
    "\t",
    "\n",
    "\r",
    "\v",
    "\f",
    "\u00a0",
    "\u1680",
    "\u2000",
    "\u2007",
    "\u202f",
    "\u205f",
    "\u3000",
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


def _template_version(db_session, *, created_by=None, created_at=None):
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
        created_by=created_by,
        created_at=created_at,
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


def _workflow_user(db_session, suffix):
    user = User(
        username=f"template_workflow_{suffix}",
        password="hashed-password",
        role="admin",
    )
    db_session.add(user)
    db_session.flush()
    return user


def _apply_template_transition(
    version,
    transition,
    actor,
    *,
    successor=None,
):
    actor_id = actor.id
    version.row_version += 1
    if transition == "draft_to_submitted":
        version.status = "submitted"
        version.submitted_by = actor_id
        version.submitted_at = datetime.now(timezone.utc)
    elif transition == "submitted_to_approved":
        version.status = "approved"
        version.approved_by = actor_id
        version.approved_at = datetime.now(timezone.utc)
        version.approval_reason = "核准"
        version.rejection_reason = None
    elif transition == "submitted_to_rejected":
        version.status = "rejected"
        version.approved_by = actor_id
        version.approved_at = datetime.now(timezone.utc)
        version.approval_reason = None
        version.rejection_reason = "退回"
    else:
        version.status = "superseded"
        version.successor_version = successor


def _transition_template_to_status(db_session, version, status):
    """只供測試造境，依正式生命週期建立受控狀態。"""

    if status == "draft":
        db_session.commit()
        return None
    submitter = _workflow_user(
        db_session,
        f"fixture_{version.id}_{status}_submitter",
    )
    _apply_template_transition(
        version,
        "draft_to_submitted",
        submitter,
    )
    db_session.commit()
    if status == "submitted":
        return None

    decision_maker = _workflow_user(
        db_session,
        f"fixture_{version.id}_{status}_decision",
    )
    if status == "rejected":
        _apply_template_transition(
            version,
            "submitted_to_rejected",
            decision_maker,
        )
        db_session.commit()
        return None

    _apply_template_transition(
        version,
        "submitted_to_approved",
        decision_maker,
    )
    db_session.commit()
    if status == "approved":
        return None

    successor = _sibling_template_version(
        db_session,
        version.template,
        version.version_no + 1,
    )
    successor_submitter = _workflow_user(
        db_session,
        f"fixture_{version.id}_{status}_successor_submitter",
    )
    _apply_template_transition(
        successor,
        "draft_to_submitted",
        successor_submitter,
    )
    db_session.commit()
    _apply_template_transition(
        version,
        "approved_to_superseded",
        decision_maker,
        successor=successor,
    )
    db_session.commit()
    return successor


def _prepare_template_transition(db_session, transition):
    creator = _workflow_user(db_session, f"{transition}_creator")
    version = _template_version(db_session, created_by=creator.id)
    submitter = _workflow_user(db_session, f"{transition}_submitter")
    if transition != "draft_to_submitted":
        _apply_template_transition(
            version,
            "draft_to_submitted",
            submitter,
        )
        db_session.commit()
        actor = _workflow_user(db_session, f"{transition}_decision")
    else:
        actor = submitter
    if transition == "approved_to_superseded":
        _apply_template_transition(
            version,
            "submitted_to_approved",
            actor,
        )
        db_session.commit()
        successor = _sibling_template_version(
            db_session,
            version.template,
            2,
        )
        successor_submitter = _workflow_user(
            db_session,
            f"{transition}_successor_submitter",
        )
        _apply_template_transition(
            successor,
            "draft_to_submitted",
            successor_submitter,
        )
        db_session.commit()
    else:
        successor = None
    return version, actor, successor


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
    _transition_template_to_status(db_session, version, status)
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
    _transition_template_to_status(db_session, first, "approved")
    second = _sibling_template_version(
        db_session,
        first.template,
        2,
    )
    _transition_template_to_status(db_session, second, "submitted")
    approver = _workflow_user(db_session, "second_approved_conflict")
    _apply_template_transition(
        second,
        "submitted_to_approved",
        approver,
    )

    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


@pytest.mark.parametrize("assignment", ["foreign_key", "relationship"])
def test_new_template_version_rejects_preassigned_successor(
    db_session,
    assignment,
):
    template = CalibrationTemplate(
        template_code=f"CAL-INSERT-{assignment}",
        name="新增版本後繼防線",
        equipment_type="游標卡尺",
    )
    db_session.add(template)
    successor = _sibling_template_version(
        db_session,
        template,
        2,
    )
    version = CalibrationTemplateVersion(
        template=template,
        version_no=1,
        procedure_code="WI-CAL-001",
        procedure_name="第一版",
        default_repetitions=3,
        environment_requirements={},
        status="draft",
    )
    if assignment == "foreign_key":
        version.successor_version_id = successor.id
    else:
        version.successor_version = successor
    db_session.add(version)

    with pytest.raises(ValueError, match="後繼版本"):
        db_session.commit()
    db_session.rollback()


@pytest.mark.parametrize(
    ("field_name", "field_value"),
    [
        ("status", "submitted"),
        ("status", "approved"),
        ("status", "rejected"),
        ("status", "superseded"),
        ("row_version", 2),
        ("submitted_by", "actor"),
        ("submitted_at", "now"),
        ("approved_by", "actor"),
        ("approved_at", "now"),
        ("approval_reason", "預設核准"),
        ("rejection_reason", "預設退回"),
    ],
)
def test_new_template_version_rejects_non_draft_or_control_audit(
    db_session,
    field_name,
    field_value,
):
    actor = _workflow_user(db_session, f"insert_{field_name}_{field_value}")
    template = CalibrationTemplate(
        template_code=f"CAL-INSERT-GUARD-{field_name}-{field_value}",
        name="新增版本初始狀態防線",
        equipment_type="游標卡尺",
    )
    db_session.add(template)
    version = CalibrationTemplateVersion(
        template=template,
        version_no=1,
        procedure_code="WI-CAL-001",
        procedure_name="第一版",
        default_repetitions=3,
        environment_requirements={},
        status="draft",
    )
    resolved_value = {
        "actor": actor.id,
        "now": datetime.now(timezone.utc),
    }.get(field_value, field_value)
    setattr(version, field_name, resolved_value)
    db_session.add(version)

    with pytest.raises(ValueError, match="新建校正模板版本"):
        db_session.commit()
    db_session.rollback()


def test_new_draft_template_version_allows_created_audit(db_session):
    actor = _workflow_user(db_session, "insert_created_audit")
    created_at = datetime.now(timezone.utc)
    version = _template_version(
        db_session,
        created_by=actor.id,
        created_at=created_at,
    )

    db_session.commit()

    assert version.status == "draft"
    assert version.row_version == 1
    assert version.created_by == actor.id
    assert version.created_at is not None


def test_new_template_version_applies_omitted_orm_defaults(db_session):
    template = CalibrationTemplate(
        template_code="CAL-INSERT-ORM-DEFAULTS",
        name="新增版本預設值",
        equipment_type="游標卡尺",
    )
    version = CalibrationTemplateVersion(
        template=template,
        version_no=1,
        procedure_code="WI-CAL-DEFAULTS",
        procedure_name="預設值測試",
        default_repetitions=3,
        environment_requirements={},
    )
    db_session.add(version)

    db_session.commit()

    assert version.status == "draft"
    assert version.row_version == 1


def test_draft_template_version_allows_content_update_with_row_increment(
    db_session,
):
    version = _template_version(db_session)
    db_session.commit()
    previous_row_version = version.row_version

    version.procedure_name = "游標卡尺內校修訂"
    version.environment_requirements = {
        "temperature": {"required": True, "min": 20, "max": 24},
    }
    version.revision_reason = "更新校正環境要求"
    version.row_version = previous_row_version + 1
    db_session.commit()

    assert version.procedure_name == "游標卡尺內校修訂"
    assert version.revision_reason == "更新校正環境要求"
    assert version.row_version == previous_row_version + 1
    assert version.submitted_by is None
    assert version.approved_by is None
    assert version.successor_version_id is None


@pytest.mark.parametrize(
    "protected_field",
    [
        "created_by",
        "created_at",
        "submitted_by",
        "submitted_at",
        "approved_by",
        "approved_at",
        "approval_reason",
        "rejection_reason",
        "successor_version",
    ],
)
def test_draft_template_version_rejects_audit_prewrite(
    db_session,
    protected_field,
):
    creator = _workflow_user(
        db_session,
        f"draft_guard_creator_{protected_field}",
    )
    version = _template_version(db_session, created_by=creator.id)
    db_session.commit()
    actor = _workflow_user(db_session, f"draft_guard_actor_{protected_field}")
    successor = _sibling_template_version(
        db_session,
        version.template,
        2,
    )
    values = {
        "created_by": actor.id,
        "created_at": version.created_at + timedelta(seconds=1),
        "submitted_by": actor.id,
        "submitted_at": datetime.now(timezone.utc),
        "approved_by": actor.id,
        "approved_at": datetime.now(timezone.utc),
        "approval_reason": "預寫核准",
        "rejection_reason": "預寫退回",
        "successor_version": successor,
    }
    setattr(version, protected_field, values[protected_field])
    version.row_version += 1

    with pytest.raises(ValueError, match="草稿|後繼版本"):
        db_session.commit()
    db_session.rollback()


@pytest.mark.parametrize("row_version_delta", [0, 2])
def test_draft_template_version_requires_exact_row_increment(
    db_session,
    row_version_delta,
):
    version = _template_version(db_session)
    db_session.commit()
    previous_row_version = version.row_version
    version.procedure_name = "草稿內容修訂"
    version.row_version = previous_row_version + row_version_delta

    with pytest.raises(ValueError, match="資料版本"):
        db_session.commit()
    db_session.rollback()


def test_draft_submission_cannot_reuse_prewritten_audit(db_session):
    version = _template_version(db_session)
    submitter = _workflow_user(db_session, "borrowed_submit_audit")
    db_session.commit()
    table = CalibrationTemplateVersion.__table__
    db_session.execute(
        table.update()
        .where(table.c["識別碼"] == version.id)
        .values({
            "送審者ID": submitter.id,
            "送審時間": datetime.now(timezone.utc),
            "資料版本": version.row_version + 1,
        })
    )
    db_session.commit()
    db_session.refresh(version)

    version.status = "submitted"
    version.row_version += 1

    with pytest.raises(ValueError, match="預寫|送審"):
        db_session.commit()
    db_session.rollback()


@pytest.mark.parametrize(
    "transition",
    [
        "draft_to_submitted",
        "submitted_to_approved",
        "submitted_to_rejected",
        "approved_to_superseded",
    ],
)
def test_template_version_allows_controlled_transition_columns(
    db_session,
    transition,
):
    version, actor, successor = _prepare_template_transition(
        db_session,
        transition,
    )
    previous_row_version = version.row_version

    _apply_template_transition(
        version,
        transition,
        actor,
        successor=successor,
    )
    db_session.commit()

    assert version.row_version == previous_row_version + 1
    assert version.status == transition.rsplit("_to_", 1)[1]


@pytest.mark.parametrize(
    "transition",
    [
        "draft_to_submitted",
        "submitted_to_approved",
        "submitted_to_rejected",
        "approved_to_superseded",
    ],
)
@pytest.mark.parametrize("row_version_delta", [0, 2])
def test_template_transition_requires_exact_row_version_increment(
    db_session,
    transition,
    row_version_delta,
):
    version, actor, successor = _prepare_template_transition(
        db_session,
        transition,
    )
    previous_row_version = version.row_version
    _apply_template_transition(
        version,
        transition,
        actor,
        successor=successor,
    )
    version.row_version = previous_row_version + row_version_delta

    with pytest.raises(ValueError, match="資料版本"):
        db_session.commit()
    db_session.rollback()


@pytest.mark.parametrize(
    ("transition", "missing_field", "expected_message"),
    [
        ("draft_to_submitted", "submitted_by", "送審者"),
        ("draft_to_submitted", "submitted_at", "送審時間"),
        ("submitted_to_approved", "approved_by", "核准者"),
        ("submitted_to_approved", "approved_at", "核准時間"),
        ("submitted_to_approved", "approval_reason", "核准理由"),
        ("submitted_to_rejected", "approved_by", "決策者"),
        ("submitted_to_rejected", "approved_at", "決策時間"),
        ("submitted_to_rejected", "rejection_reason", "退回理由"),
    ],
)
def test_template_transition_requires_audit_fields(
    db_session,
    transition,
    missing_field,
    expected_message,
):
    version, actor, successor = _prepare_template_transition(
        db_session,
        transition,
    )
    _apply_template_transition(
        version,
        transition,
        actor,
        successor=successor,
    )
    setattr(version, missing_field, None)

    with pytest.raises(ValueError, match=expected_message):
        db_session.commit()
    db_session.rollback()


@pytest.mark.parametrize(
    ("transition", "reason_field"),
    [
        ("submitted_to_approved", "approval_reason"),
        ("submitted_to_rejected", "rejection_reason"),
    ],
)
@pytest.mark.parametrize("blank_reason", BLANK_TEMPLATE_REASON_CASES)
def test_template_decision_rejects_blank_reason(
    db_session,
    transition,
    reason_field,
    blank_reason,
):
    version, actor, successor = _prepare_template_transition(
        db_session,
        transition,
    )
    _apply_template_transition(
        version,
        transition,
        actor,
        successor=successor,
    )
    setattr(version, reason_field, blank_reason)

    with pytest.raises(ValueError, match="理由"):
        db_session.commit()
    db_session.rollback()


@pytest.mark.parametrize(
    ("transition", "reason_field"),
    [
        ("submitted_to_approved", "approval_reason"),
        ("submitted_to_rejected", "rejection_reason"),
    ],
)
def test_template_decision_allows_visible_reason(
    db_session,
    transition,
    reason_field,
):
    version, actor, successor = _prepare_template_transition(
        db_session,
        transition,
    )
    _apply_template_transition(
        version,
        transition,
        actor,
        successor=successor,
    )
    setattr(version, reason_field, "\u00a0有效理由\u3000")

    db_session.commit()

    assert version.status == transition.rsplit("_to_", 1)[1]


@pytest.mark.parametrize("self_approval_source", ["created", "submitted"])
def test_template_approval_enforces_separation_of_duties(
    db_session,
    self_approval_source,
):
    creator = _workflow_user(db_session, f"sod_creator_{self_approval_source}")
    submitter = _workflow_user(
        db_session,
        f"sod_submitter_{self_approval_source}",
    )
    version = _template_version(db_session, created_by=creator.id)
    _apply_template_transition(
        version,
        "draft_to_submitted",
        submitter,
    )
    db_session.commit()
    approver = creator if self_approval_source == "created" else submitter
    _apply_template_transition(
        version,
        "submitted_to_approved",
        approver,
    )

    with pytest.raises(ValueError, match="職責分離"):
        db_session.commit()
    db_session.rollback()


@pytest.mark.parametrize(
    "transition",
    [
        "draft_to_submitted",
        "submitted_to_approved",
        "submitted_to_rejected",
        "approved_to_superseded",
    ],
)
@pytest.mark.parametrize(
    "tampering",
    [
        "procedure_name",
        "environment_requirements",
        "revision_reason",
        "audit_history",
    ],
)
def test_template_transition_rejects_content_or_audit_tampering(
    db_session,
    transition,
    tampering,
):
    version, actor, successor = _prepare_template_transition(
        db_session,
        transition,
    )
    _apply_template_transition(
        version,
        transition,
        actor,
        successor=successor,
    )
    if tampering == "procedure_name":
        version.procedure_name = "夾帶竄改程序"
    elif tampering == "environment_requirements":
        version.environment_requirements = {"temperature": {"min": 999}}
    elif tampering == "revision_reason":
        version.revision_reason = "夾帶竄改修訂原因"
    elif transition == "draft_to_submitted":
        version.created_by = actor.id
    elif transition in {
        "submitted_to_approved",
        "submitted_to_rejected",
    }:
        version.submitted_by = None
    else:
        version.approved_by = None

    with pytest.raises(ValueError, match="轉態欄位"):
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


@pytest.mark.parametrize(
    "status",
    ["submitted", "rejected", "approved", "superseded"],
)
@pytest.mark.parametrize("operation", ["update", "delete"])
def test_approved_or_superseded_template_version_is_immutable(
    db_session,
    status,
    operation,
):
    version = _template_version(db_session)
    _transition_template_to_status(db_session, version, status)

    if operation == "update":
        version.procedure_name = "嘗試改寫受控版本"
    else:
        db_session.delete(version)

    with pytest.raises(ValueError, match="模板版本"):
        db_session.commit()
    db_session.rollback()


def test_draft_template_version_can_be_deleted(db_session):
    version = _template_version(db_session)
    version_id = version.id
    db_session.delete(version)

    db_session.commit()

    assert db_session.get(CalibrationTemplateVersion, version_id) is None


def test_approved_template_version_allows_controlled_supersession(db_session):
    version = _template_version(db_session)
    _transition_template_to_status(db_session, version, "approved")
    successor = _sibling_template_version(
        db_session,
        version.template,
        2,
    )
    _transition_template_to_status(db_session, successor, "submitted")

    old_row_version = version.row_version
    version.status = "superseded"
    version.successor_version = successor
    version.row_version = old_row_version + 1
    db_session.flush()
    successor_approver = _workflow_user(
        db_session,
        "controlled_supersession_approver",
    )
    _apply_template_transition(
        successor,
        "submitted_to_approved",
        successor_approver,
    )
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
        )
    elif case_name == "backward":
        successor = first
        old = _sibling_template_version(
            db_session,
            first.template,
            2,
        )
    else:
        old = first
        successor = _sibling_template_version(
            db_session,
            first.template,
            2,
        )
    if successor is not old and successor.status == "draft":
        _transition_template_to_status(db_session, successor, "submitted")
    _transition_template_to_status(db_session, old, "approved")

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
    )
    _transition_template_to_status(db_session, successor, "submitted")
    _transition_template_to_status(db_session, old, "approved")

    successor_id = successor.id
    old_row_version = old.row_version
    old.status = "superseded"
    old.successor_version_id = successor_id
    old.row_version = old_row_version + 1
    db_session.commit()
    successor_approver = _workflow_user(
        db_session,
        "cycle_successor_approver",
    )
    _apply_template_transition(
        successor,
        "submitted_to_approved",
        successor_approver,
    )
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
    _transition_template_to_status(db_session, version, status)

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


@pytest.mark.parametrize("status", ["submitted", "approved", "rejected"])
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


@pytest.mark.parametrize("status", ["submitted", "approved", "rejected"])
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


@pytest.mark.parametrize("status", ["submitted", "approved", "rejected"])
def test_submitted_or_approved_reading_cannot_be_updated(db_session, status):
    reading = _reading(db_session, status)
    reading.indicated_value = "99"

    with pytest.raises(ValueError, match="原始讀值不可修改"):
        db_session.commit()
    db_session.rollback()


@pytest.mark.parametrize("status", ["submitted", "approved", "rejected"])
def test_submitted_or_approved_reading_cannot_be_deleted(db_session, status):
    reading = _reading(db_session, status)
    db_session.delete(reading)

    with pytest.raises(ValueError, match="原始讀值不可刪除"):
        db_session.commit()
    db_session.rollback()
