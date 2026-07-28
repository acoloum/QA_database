import os

import pytest
from flask import Flask
from sqlalchemy import func, text
from sqlalchemy.exc import DBAPIError

from backend.extensions import db
from backend.models import (
    AuditLog,
    CalibrationTemplate,
    CalibrationTemplatePoint,
    CalibrationTemplateVersion,
    User,
)
from backend.services.calibration_errors import (
    CalibrationConflict,
    CalibrationForbidden,
    CalibrationNotFound,
    CalibrationValidationError,
)
from backend.services.calibration_template_service import (
    CalibrationTemplateService,
)
from backend.tests.test_services.test_calibration_migration import (
    _connect,
    migrated_postgresql,
)


def _user(db_session, username: str) -> User:
    user = User(
        username=username,
        password="test-password",
        role="admin",
        is_active=True,
    )
    db_session.add(user)
    db_session.flush()
    return user


def _point(**overrides) -> dict:
    payload = {
        "point_order": 1,
        "point_code": " P01 ",
        "measurement_mode": " 外徑 ",
        "nominal_value": "10.000",
        "unit": " mm ",
        "reference_input_mode": "certified_value",
        "required_repetitions": 3,
        "error_lower_limit": "-0.02",
        "error_upper_limit": "0.02",
        "evaluation_basis": "all_readings",
        "repeatability_rule": "range",
        "repeatability_limit": "0.01",
        "qualification_scope_code": " OD-0-150 ",
        "qualification_range_start": "0",
        "qualification_range_end": "150",
        "uncertainty_required": True,
        "required": True,
        "instruction": " 量測外徑三次 ",
    }
    payload.update(overrides)
    return payload


def _version_payload(**overrides) -> dict:
    payload = {
        "procedure_code": " WI-CAL-001 ",
        "procedure_name": " 游標卡尺內校 ",
        "procedure_description": " 依程序執行 ",
        "default_repetitions": 3,
        "environment_requirements": {
            "temperature": {
                "required": True,
                "minimum": "20",
                "maximum": "26",
                "unit": "°C",
            }
        },
        "allow_limited_use": True,
        "revision_reason": " 初版建立 ",
        "points": [_point()],
    }
    payload.update(overrides)
    return payload


def _template_payload(**overrides) -> dict:
    payload = {
        "template_code": " CAL-CALIPER ",
        "name": " 游標卡尺 ",
        "equipment_type": " 游標卡尺 ",
        "description": " 內校程序模板 ",
    }
    payload.update(overrides)
    return payload


def _create_version(db_session, actor: User, **overrides):
    template = CalibrationTemplateService.create(
        _template_payload(
            template_code=f"CAL-{actor.username.upper()}-{len(db_session.new)}"
        ),
        actor.id,
    )
    version = CalibrationTemplateService.create_version(
        template["id"],
        _version_payload(**overrides),
        actor.id,
    )
    return template, version


def _submit_version(db_session, actor: User, **overrides):
    template, version = _create_version(db_session, actor, **overrides)
    submitted = CalibrationTemplateService.submit_version(
        version["id"],
        {
            "expected_version": version["row_version"],
            "reason": " 送請核准 ",
        },
        actor.id,
    )
    return template, submitted


def test_create_normalizes_template_and_decimal_evidence(db_session):
    actor = _user(db_session, "template_author")
    template = CalibrationTemplateService.create(
        _template_payload(),
        actor.id,
    )
    version = CalibrationTemplateService.create_version(
        template["id"],
        _version_payload(),
        actor.id,
    )

    assert template == {
        "id": template["id"],
        "template_code": "CAL-CALIPER",
        "name": "游標卡尺",
        "equipment_type": "游標卡尺",
        "description": "內校程序模板",
        "status": "active",
        "current_approved_version_id": None,
    }
    point = version["points"][0]
    assert point["point_code"] == "P01"
    assert point["measurement_mode"] == "外徑"
    assert point["unit"] == "mm"
    assert point["qualification_scope_code"] == "OD-0-150"
    assert point["instruction"] == "量測外徑三次"
    assert point["nominal_value"] == "10"
    assert point["error_lower_limit"] == "-0.02"
    assert point["qualification_range_start"] == "0"
    assert point["qualification_range_end"] == "150"
    assert isinstance(point["nominal_value"], str)


@pytest.mark.parametrize("payload", [None, [], "not-an-object", 3])
def test_mutations_reject_non_object_payload_without_writes(
    db_session,
    payload,
):
    actor = _user(db_session, f"non_object_{type(payload).__name__}")
    before = CalibrationTemplate.query.count()

    with pytest.raises(CalibrationValidationError) as error:
        CalibrationTemplateService.create(payload, actor.id)

    assert error.value.code == "CALIBRATION_PAYLOAD_INVALID"
    assert CalibrationTemplate.query.count() == before


def test_create_rejects_unknown_fields_without_writes(db_session):
    actor = _user(db_session, "unknown_field")

    with pytest.raises(CalibrationValidationError) as error:
        CalibrationTemplateService.create(
            _template_payload(status="approved"),
            actor.id,
        )

    assert error.value.code == "CALIBRATION_UNKNOWN_FIELDS"
    assert error.value.details == {"unknown_fields": ["status"]}
    assert CalibrationTemplate.query.count() == 0


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("template_code", " "),
        ("name", 123),
        ("equipment_type", "x" * 81),
    ],
)
def test_create_rejects_invalid_template_strings_without_writes(
    db_session,
    field,
    value,
):
    actor = _user(db_session, f"invalid_string_{field}")

    with pytest.raises(CalibrationValidationError) as error:
        CalibrationTemplateService.create(
            _template_payload(**{field: value}),
            actor.id,
        )

    assert error.value.code == "CALIBRATION_FIELD_INVALID"
    assert error.value.details["field"] == field
    assert CalibrationTemplate.query.count() == 0


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("default_repetitions", True),
        ("default_repetitions", 0),
        ("default_repetitions", 101),
        ("default_repetitions", 10**1000),
    ],
)
def test_create_version_rejects_unbounded_integer_fields(
    db_session,
    field,
    value,
):
    actor = _user(db_session, f"invalid_int_{field}_{str(value)[:8]}")
    template = CalibrationTemplateService.create(
        _template_payload(
            template_code=f"CAL-INT-{len(str(value))}-{int(bool(value))}"
        ),
        actor.id,
    )

    with pytest.raises(CalibrationValidationError) as error:
        CalibrationTemplateService.create_version(
            template["id"],
            _version_payload(**{field: value}),
            actor.id,
        )

    assert error.value.code == "CALIBRATION_FIELD_INVALID"
    assert error.value.details["field"] == field
    assert CalibrationTemplateVersion.query.count() == 0


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("nominal_value", "NaN"),
        ("nominal_value", "Infinity"),
        ("nominal_value", "1e1001"),
        ("nominal_value", "1" * 51),
        ("error_lower_limit", "-Infinity"),
        ("repeatability_limit", "-0.001"),
    ],
)
def test_create_version_rejects_non_finite_or_unbounded_decimals(
    db_session,
    field,
    value,
):
    actor = _user(db_session, f"invalid_decimal_{field}_{len(value)}")
    template = CalibrationTemplateService.create(
        _template_payload(
            template_code=f"CAL-DEC-{field[:6]}-{len(value)}"
        ),
        actor.id,
    )

    with pytest.raises(CalibrationValidationError) as error:
        CalibrationTemplateService.create_version(
            template["id"],
            _version_payload(points=[_point(**{field: value})]),
            actor.id,
        )

    assert error.value.code == "CALIBRATION_POINT_INVALID"
    assert error.value.details["field"] == field
    assert CalibrationTemplateVersion.query.count() == 0
    assert CalibrationTemplatePoint.query.count() == 0


@pytest.mark.parametrize(
    ("points", "field"),
    [
        (
            [_point(), _point(point_order=2, point_code=" P01 ")],
            "point_code",
        ),
        (
            [_point(), _point(point_order=1, point_code="P02")],
            "point_order",
        ),
        ([_point(point_order=0)], "point_order"),
        ([_point(point_order=10_001)], "point_order"),
    ],
)
def test_create_version_rejects_duplicate_or_unreasonable_point_identity(
    db_session,
    points,
    field,
):
    actor = _user(db_session, f"invalid_identity_{field}_{len(points)}")
    template = CalibrationTemplateService.create(
        _template_payload(
            template_code=f"CAL-ID-{field.upper()}-{len(points)}"
        ),
        actor.id,
    )

    with pytest.raises(CalibrationValidationError) as error:
        CalibrationTemplateService.create_version(
            template["id"],
            _version_payload(points=points),
            actor.id,
        )

    assert error.value.code == "CALIBRATION_POINT_INVALID"
    assert error.value.details["field"] == field
    assert CalibrationTemplateVersion.query.count() == 0
    assert CalibrationTemplatePoint.query.count() == 0


@pytest.mark.parametrize(
    ("point", "field"),
    [
        (_point(qualification_scope_code=" "), "qualification_scope_code"),
        (
            _point(qualification_range_start="0", qualification_range_end=None),
            "qualification_range_end",
        ),
        (
            _point(qualification_range_start=None, qualification_range_end="150"),
            "qualification_range_start",
        ),
        (
            _point(qualification_range_start="151", qualification_range_end="150"),
            "qualification_range_start",
        ),
    ],
)
def test_create_version_requires_complete_qualification_scope(
    db_session,
    point,
    field,
):
    actor = _user(db_session, f"invalid_scope_{field}")
    template = CalibrationTemplateService.create(
        _template_payload(template_code=f"CAL-SCOPE-{field[:8]}"),
        actor.id,
    )

    with pytest.raises(CalibrationValidationError) as error:
        CalibrationTemplateService.create_version(
            template["id"],
            _version_payload(points=[point]),
            actor.id,
        )

    assert error.value.code == "CALIBRATION_POINT_INVALID"
    assert error.value.details["field"] == field
    assert CalibrationTemplatePoint.query.count() == 0


@pytest.mark.parametrize(
    ("point", "field"),
    [
        (_point(reference_input_mode="manual"), "reference_input_mode"),
        (_point(evaluation_basis="median"), "evaluation_basis"),
        (_point(error_lower_limit=None, error_upper_limit=None), "error_lower_limit"),
        (
            _point(error_lower_limit="0.02", error_upper_limit="-0.02"),
            "error_lower_limit",
        ),
        (
            _point(repeatability_rule="none", repeatability_limit="0.01"),
            "repeatability_limit",
        ),
        (
            _point(repeatability_rule="range", repeatability_limit=None),
            "repeatability_limit",
        ),
        (
            _point(repeatability_rule="stddev", required_repetitions=1),
            "required_repetitions",
        ),
    ],
)
def test_create_version_requires_paired_reference_evaluation_and_repeatability(
    db_session,
    point,
    field,
):
    actor = _user(db_session, f"invalid_rules_{field}")
    template = CalibrationTemplateService.create(
        _template_payload(template_code=f"CAL-RULE-{field[:8]}"),
        actor.id,
    )

    with pytest.raises(CalibrationValidationError) as error:
        CalibrationTemplateService.create_version(
            template["id"],
            _version_payload(points=[point]),
            actor.id,
        )

    assert error.value.code == "CALIBRATION_POINT_INVALID"
    assert error.value.details["field"] == field
    assert CalibrationTemplatePoint.query.count() == 0


def test_create_version_rolls_back_all_points_when_later_point_is_invalid(
    db_session,
):
    actor = _user(db_session, "atomic_point_create")
    template = CalibrationTemplateService.create(
        _template_payload(template_code="CAL-ATOMIC-POINT"),
        actor.id,
    )

    with pytest.raises(CalibrationValidationError):
        CalibrationTemplateService.create_version(
            template["id"],
            _version_payload(
                points=[
                    _point(),
                    _point(
                        point_order=2,
                        point_code="P02",
                        nominal_value="NaN",
                    ),
                ]
            ),
            actor.id,
        )

    assert CalibrationTemplateVersion.query.count() == 0
    assert CalibrationTemplatePoint.query.count() == 0


def test_create_version_returns_not_found_without_writes(db_session):
    actor = _user(db_session, "missing_template")

    with pytest.raises(CalibrationNotFound) as error:
        CalibrationTemplateService.create_version(
            999_999,
            _version_payload(),
            actor.id,
        )

    assert error.value.code == "CALIBRATION_TEMPLATE_NOT_FOUND"
    assert CalibrationTemplateVersion.query.count() == 0


def test_update_version_requires_draft_and_matching_expected_version(
    db_session,
):
    actor = _user(db_session, "optimistic_update")
    _template, version = _create_version(db_session, actor)

    with pytest.raises(CalibrationConflict) as error:
        CalibrationTemplateService.update_version(
            version["id"],
            {
                "expected_version": version["row_version"] + 1,
                "procedure_name": "新程序名稱",
            },
            actor.id,
        )

    assert error.value.code == "CALIBRATION_VERSION_CONFLICT"
    persisted = db_session.get(CalibrationTemplateVersion, version["id"])
    assert persisted.procedure_name == "游標卡尺內校"
    assert persisted.row_version == version["row_version"]


def test_update_version_replaces_points_atomically_and_increments_once(
    db_session,
):
    actor = _user(db_session, "replace_points")
    _template, version = _create_version(db_session, actor)

    updated = CalibrationTemplateService.update_version(
        version["id"],
        {
            "expected_version": version["row_version"],
            "procedure_name": " 更新後程序 ",
            "points": [
                _point(
                    point_order=2,
                    point_code="P02",
                    nominal_value="20.00",
                )
            ],
        },
        actor.id,
    )

    assert updated["procedure_name"] == "更新後程序"
    assert updated["row_version"] == version["row_version"] + 1
    assert [point["point_code"] for point in updated["points"]] == ["P02"]
    assert CalibrationTemplatePoint.query.count() == 1


def test_update_version_rolls_back_scalar_and_point_changes_together(
    db_session,
):
    actor = _user(db_session, "atomic_update")
    _template, version = _create_version(db_session, actor)

    with pytest.raises(CalibrationValidationError):
        CalibrationTemplateService.update_version(
            version["id"],
            {
                "expected_version": version["row_version"],
                "procedure_name": "不得殘留",
                "points": [_point(nominal_value="Infinity")],
            },
            actor.id,
        )

    db_session.expire_all()
    persisted = db_session.get(CalibrationTemplateVersion, version["id"])
    assert persisted.procedure_name == "游標卡尺內校"
    assert persisted.row_version == version["row_version"]
    assert [point.point_code for point in persisted.points] == ["P01"]


def test_submit_requires_at_least_one_required_point(db_session):
    actor = _user(db_session, "required_point")
    _template, version = _create_version(
        db_session,
        actor,
        points=[_point(required=False)],
    )

    with pytest.raises(CalibrationValidationError) as error:
        CalibrationTemplateService.submit_version(
            version["id"],
            {
                "expected_version": version["row_version"],
                "reason": "送審",
            },
            actor.id,
        )

    assert error.value.code == "CALIBRATION_REQUIRED_POINT_MISSING"
    persisted = db_session.get(CalibrationTemplateVersion, version["id"])
    assert persisted.status == "draft"
    assert persisted.row_version == version["row_version"]
    assert persisted.submitted_by is None


def test_submit_persists_reason_actor_time_and_increments_version(db_session):
    actor = _user(db_session, "submitter")
    _template, version = _create_version(db_session, actor)

    submitted = CalibrationTemplateService.submit_version(
        version["id"],
        {
            "expected_version": version["row_version"],
            "reason": " 程序內容已複核 ",
        },
        actor.id,
    )

    assert submitted["status"] == "submitted"
    assert submitted["row_version"] == version["row_version"] + 1
    assert submitted["submitted_by"] == actor.id
    assert submitted["submitted_at"] is not None
    assert submitted["approval_reason"] is None
    assert submitted["rejection_reason"] is None
    audit = AuditLog.query.filter_by(
        module="calibration_template",
        record_id=version["id"],
        action="submit_version",
    ).one()
    assert audit.new_value["reason"] == "程序內容已複核"


def test_approver_cannot_approve_own_template_version(db_session):
    manager = _user(db_session, "self_approver")
    template, submitted = _submit_version(db_session, manager)

    with pytest.raises(CalibrationForbidden) as error:
        CalibrationTemplateService.approve_version(
            submitted["id"],
            {
                "expected_version": submitted["row_version"],
                "reason": "內容符合內校程序",
            },
            manager.id,
        )

    assert error.value.code == "CALIBRATION_SELF_APPROVAL_FORBIDDEN"
    persisted = db_session.get(CalibrationTemplateVersion, submitted["id"])
    assert persisted.status == "submitted"
    assert persisted.row_version == submitted["row_version"]
    assert (
        db_session.get(CalibrationTemplate, template["id"])
        .current_approved_version_id
        is None
    )


def test_approver_cannot_approve_version_they_created(db_session):
    author = _user(db_session, "version_author")
    submitter = _user(db_session, "different_submitter")
    approver = author
    _template, version = _create_version(db_session, author)
    submitted = CalibrationTemplateService.submit_version(
        version["id"],
        {
            "expected_version": version["row_version"],
            "reason": "送審",
        },
        submitter.id,
    )

    with pytest.raises(CalibrationForbidden) as error:
        CalibrationTemplateService.approve_version(
            submitted["id"],
            {
                "expected_version": submitted["row_version"],
                "reason": "核准",
            },
            approver.id,
        )

    assert error.value.code == "CALIBRATION_SELF_APPROVAL_FORBIDDEN"
    assert (
        db_session.get(CalibrationTemplateVersion, submitted["id"]).status
        == "submitted"
    )


def test_approve_requires_submitted_and_matching_expected_version(db_session):
    author = _user(db_session, "approve_author")
    approver = _user(db_session, "approve_manager")
    _template, version = _create_version(db_session, author)

    with pytest.raises(CalibrationConflict) as status_error:
        CalibrationTemplateService.approve_version(
            version["id"],
            {
                "expected_version": version["row_version"],
                "reason": "核准",
            },
            approver.id,
        )

    assert status_error.value.code == "CALIBRATION_STATUS_CONFLICT"

    submitted = CalibrationTemplateService.submit_version(
        version["id"],
        {
            "expected_version": version["row_version"],
            "reason": "送審",
        },
        author.id,
    )
    with pytest.raises(CalibrationConflict) as version_error:
        CalibrationTemplateService.approve_version(
            submitted["id"],
            {
                "expected_version": submitted["row_version"] + 1,
                "reason": "核准",
            },
            approver.id,
        )

    assert version_error.value.code == "CALIBRATION_VERSION_CONFLICT"
    persisted = db_session.get(CalibrationTemplateVersion, submitted["id"])
    assert persisted.status == "submitted"
    assert persisted.row_version == submitted["row_version"]


def test_new_approval_supersedes_old_version_in_same_transaction(db_session):
    author = _user(db_session, "successor_author")
    approver = _user(db_session, "successor_approver")
    template, submitted_v1 = _submit_version(db_session, author)
    approved_v1 = CalibrationTemplateService.approve_version(
        submitted_v1["id"],
        {
            "expected_version": submitted_v1["row_version"],
            "reason": "核准第一版",
        },
        approver.id,
    )
    draft_v2 = CalibrationTemplateService.create_version(
        template["id"],
        _version_payload(revision_reason="擴充量程"),
        author.id,
    )
    submitted_v2 = CalibrationTemplateService.submit_version(
        draft_v2["id"],
        {
            "expected_version": draft_v2["row_version"],
            "reason": "送審第二版",
        },
        author.id,
    )

    approved_v2 = CalibrationTemplateService.approve_version(
        submitted_v2["id"],
        {
            "expected_version": submitted_v2["row_version"],
            "reason": "核准第二版",
        },
        approver.id,
    )

    db_session.expire_all()
    old = db_session.get(CalibrationTemplateVersion, approved_v1["id"])
    current = db_session.get(CalibrationTemplateVersion, approved_v2["id"])
    persisted_template = db_session.get(CalibrationTemplate, template["id"])
    assert old.status == "superseded"
    assert old.successor_version_id == current.id
    assert old.row_version == approved_v1["row_version"] + 1
    assert current.status == "approved"
    assert persisted_template.current_approved_version_id == current.id
    assert [
        version.id
        for version in persisted_template.versions
        if version.status == "approved"
    ] == [current.id]


def test_reject_only_accepts_submitted_and_persists_reason(db_session):
    author = _user(db_session, "reject_author")
    approver = _user(db_session, "reject_approver")
    _template, version = _create_version(db_session, author)

    with pytest.raises(CalibrationConflict) as error:
        CalibrationTemplateService.reject_version(
            version["id"],
            {
                "expected_version": version["row_version"],
                "reason": "退回",
            },
            approver.id,
        )

    assert error.value.code == "CALIBRATION_STATUS_CONFLICT"

    submitted = CalibrationTemplateService.submit_version(
        version["id"],
        {
            "expected_version": version["row_version"],
            "reason": "送審",
        },
        author.id,
    )
    rejected = CalibrationTemplateService.reject_version(
        submitted["id"],
        {
            "expected_version": submitted["row_version"],
            "reason": " 量程分組不足 ",
        },
        approver.id,
    )

    assert rejected["status"] == "rejected"
    assert rejected["row_version"] == submitted["row_version"] + 1
    assert rejected["approved_by"] == approver.id
    assert rejected["approved_at"] is not None
    assert rejected["approval_reason"] is None
    assert rejected["rejection_reason"] == "量程分組不足"


@pytest.mark.parametrize("operation", ["update", "delete_point", "delete_version"])
@pytest.mark.parametrize("status", ["approved", "superseded"])
def test_approved_or_superseded_template_evidence_is_orm_immutable(
    db_session,
    operation,
    status,
):
    author = _user(db_session, f"frozen_author_{operation}_{status}")
    approver = _user(db_session, f"frozen_approver_{operation}_{status}")
    template, submitted = _submit_version(db_session, author)
    approved = CalibrationTemplateService.approve_version(
        submitted["id"],
        {
            "expected_version": submitted["row_version"],
            "reason": "核准",
        },
        approver.id,
    )
    frozen = db_session.get(CalibrationTemplateVersion, approved["id"])
    if status == "superseded":
        draft = CalibrationTemplateService.create_version(
            template["id"],
            _version_payload(revision_reason="建立新版"),
            author.id,
        )
        submitted_v2 = CalibrationTemplateService.submit_version(
            draft["id"],
            {
                "expected_version": draft["row_version"],
                "reason": "送審新版",
            },
            author.id,
        )
        CalibrationTemplateService.approve_version(
            submitted_v2["id"],
            {
                "expected_version": submitted_v2["row_version"],
                "reason": "核准新版",
            },
            approver.id,
        )
        db_session.expire_all()
        frozen = db_session.get(CalibrationTemplateVersion, approved["id"])

    if operation == "update":
        frozen.procedure_name = "嘗試竄改"
    elif operation == "delete_point":
        db_session.delete(frozen.points[0])
    else:
        db_session.delete(frozen)

    with pytest.raises(ValueError, match="模板"):
        db_session.commit()
    db_session.rollback()


@pytest.mark.parametrize("status", ["approved", "superseded"])
@pytest.mark.parametrize(
    ("target", "operation"),
    [
        ("version", "update"),
        ("version", "delete"),
        ("point", "update"),
        ("point", "delete"),
    ],
)
def test_postgresql_trigger_blocks_frozen_template_evidence_changes(
    migrated_postgresql,
    status,
    target,
    operation,
):
    connection = _connect(migrated_postgresql)
    try:
        template_id = connection.execute(
            text(
                """
                INSERT INTO "校正模板" (
                    "模板代碼", "名稱", "適用設備類型"
                ) VALUES (
                    :code, '游標卡尺', '游標卡尺'
                )
                RETURNING "識別碼"
                """
            ),
            {"code": f"CAL-FROZEN-{status}-{target}-{operation}"},
        ).scalar_one()
        version_id = connection.execute(
            text(
                """
                INSERT INTO "校正模板版本" (
                    "模板ID", "版本號", "程序代碼", "程序名稱",
                    "預設重複次數", "環境要求", "允許限制使用",
                    "狀態"
                ) VALUES (
                    :template_id, 1, 'WI-CAL-001', '游標卡尺內校',
                    3, '{}'::jsonb, FALSE, 'draft'
                )
                RETURNING "識別碼"
                """
            ),
            {"template_id": template_id},
        ).scalar_one()
        point_id = connection.execute(
            text(
                """
                INSERT INTO "校正模板校正點" (
                    "模板版本ID", "點位順序", "點位代碼", "量測模式",
                    "名目值", "單位", "參考值輸入模式", "必要重複次數",
                    "誤差下限", "誤差上限", "判定基礎", "重複性規則",
                    "重複性上限", "資格範圍代碼", "必填"
                ) VALUES (
                    :version_id, 1, 'P01', '外徑', 10, 'mm',
                    'certified_value', 3, -0.02, 0.02,
                    'all_readings', 'range', 0.01, 'OD-0-150', TRUE
                )
                RETURNING "識別碼"
                """
            ),
            {"version_id": version_id},
        ).scalar_one()
        submitter_id = connection.execute(
            text('INSERT INTO "使用者" DEFAULT VALUES RETURNING "識別碼"')
        ).scalar_one()
        approver_id = connection.execute(
            text('INSERT INTO "使用者" DEFAULT VALUES RETURNING "識別碼"')
        ).scalar_one()
        connection.execute(
            text(
                """
                UPDATE "校正模板版本"
                SET "狀態" = 'submitted',
                    "送審者ID" = :submitter_id,
                    "送審時間" = CURRENT_TIMESTAMP,
                    "資料版本" = "資料版本" + 1
                WHERE "識別碼" = :version_id
                """
            ),
            {
                "submitter_id": submitter_id,
                "version_id": version_id,
            },
        )
        connection.execute(
            text(
                """
                UPDATE "校正模板版本"
                SET "狀態" = 'approved',
                    "核准者ID" = :approver_id,
                    "核准時間" = CURRENT_TIMESTAMP,
                    "核准理由" = '核准',
                    "退回理由" = NULL,
                    "資料版本" = "資料版本" + 1
                WHERE "識別碼" = :version_id
                """
            ),
            {
                "approver_id": approver_id,
                "version_id": version_id,
            },
        )
        if status == "superseded":
            successor_id = connection.execute(
                text(
                    """
                    INSERT INTO "校正模板版本" (
                        "模板ID", "版本號", "程序代碼", "程序名稱",
                        "預設重複次數", "環境要求", "允許限制使用",
                        "狀態"
                    ) VALUES (
                        :template_id, 2, 'WI-CAL-002', '游標卡尺內校',
                        3, '{}'::jsonb, FALSE, 'draft'
                    )
                    RETURNING "識別碼"
                    """
                ),
                {"template_id": template_id},
            ).scalar_one()
            connection.execute(
                text(
                    """
                    UPDATE "校正模板版本"
                    SET "狀態" = 'submitted',
                        "送審者ID" = :submitter_id,
                        "送審時間" = CURRENT_TIMESTAMP,
                        "資料版本" = "資料版本" + 1
                    WHERE "識別碼" = :successor_id
                    """
                ),
                {
                    "submitter_id": submitter_id,
                    "successor_id": successor_id,
                },
            )
            connection.execute(
                text(
                    """
                    UPDATE "校正模板版本"
                    SET "狀態" = 'superseded',
                        "後繼版本ID" = :successor_id,
                        "資料版本" = "資料版本" + 1
                    WHERE "識別碼" = :version_id
                    """
                ),
                {
                    "successor_id": successor_id,
                    "version_id": version_id,
                },
            )
            connection.execute(
                text(
                    """
                    UPDATE "校正模板版本"
                    SET "狀態" = 'approved',
                        "核准者ID" = :approver_id,
                        "核准時間" = CURRENT_TIMESTAMP,
                        "核准理由" = '核准',
                        "退回理由" = NULL,
                        "資料版本" = "資料版本" + 1
                    WHERE "識別碼" = :successor_id
                    """
                ),
                {
                    "approver_id": approver_id,
                    "successor_id": successor_id,
                },
            )
        connection.commit()

        statements = {
            ("version", "update"): (
                'UPDATE "校正模板版本" SET "程序名稱" = \'竄改\' '
                'WHERE "識別碼" = :id'
            ),
            ("version", "delete"): (
                'DELETE FROM "校正模板版本" WHERE "識別碼" = :id'
            ),
            ("point", "update"): (
                'UPDATE "校正模板校正點" SET "名目值" = 99 '
                'WHERE "識別碼" = :id'
            ),
            ("point", "delete"): (
                'DELETE FROM "校正模板校正點" WHERE "識別碼" = :id'
            ),
        }
        target_id = version_id if target == "version" else point_id
        with pytest.raises(DBAPIError, match="模板"):
            connection.execute(
                text(statements[(target, operation)]),
                {"id": target_id},
            )
        connection.rollback()

        assert connection.execute(
            text(
                'SELECT COUNT(*) FROM "校正模板版本" '
                'WHERE "識別碼" = :id'
            ),
            {"id": version_id},
        ).scalar_one() == 1
        assert connection.execute(
            text(
                'SELECT COUNT(*) FROM "校正模板校正點" '
                'WHERE "識別碼" = :id'
            ),
            {"id": point_id},
        ).scalar_one() == 1
    finally:
        connection.close()


def test_postgresql_service_orders_controlled_supersession_before_new_approval(
    migrated_postgresql,
):
    database_url = os.environ["CALIBRATION_TEST_DATABASE_URL"]
    engine, schema_name = migrated_postgresql
    with engine.connect() as connection:
        connection.execute(
            text(f'SET search_path TO "{schema_name}", public')
        )
        connection.execute(
            text(
                """
                CREATE TABLE "操作日誌" (
                    "識別碼" SERIAL PRIMARY KEY,
                    "使用者ID" INTEGER REFERENCES "使用者"("識別碼"),
                    "操作類型" VARCHAR(20) NOT NULL,
                    "模組" VARCHAR(30) NOT NULL,
                    "資料ID" INTEGER,
                    "操作前" JSONB,
                    "操作後" JSONB,
                    "建立時間" TIMESTAMPTZ NOT NULL
                        DEFAULT CURRENT_TIMESTAMP
                );
                INSERT INTO "使用者" DEFAULT VALUES;
                INSERT INTO "使用者" DEFAULT VALUES;
                """
            )
        )
        connection.commit()

    pg_app = Flask("calibration-template-postgresql-service")
    pg_app.config.update(
        TESTING=True,
        SQLALCHEMY_DATABASE_URI=database_url,
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        SQLALCHEMY_ENGINE_OPTIONS={
            "pool_pre_ping": True,
            "connect_args": {
                "options": f"-csearch_path={schema_name},public",
            },
        },
    )
    db.init_app(pg_app)

    with pg_app.app_context():
        try:
            template = CalibrationTemplateService.create(
                _template_payload(template_code="CAL-PG-ORDER"),
                actor_id=1,
            )
            draft_v1 = CalibrationTemplateService.create_version(
                template["id"],
                _version_payload(),
                actor_id=1,
            )
            submitted_v1 = CalibrationTemplateService.submit_version(
                draft_v1["id"],
                {
                    "expected_version": draft_v1["row_version"],
                    "reason": "送審第一版",
                },
                actor_id=1,
            )
            approved_v1 = CalibrationTemplateService.approve_version(
                submitted_v1["id"],
                {
                    "expected_version": submitted_v1["row_version"],
                    "reason": "核准第一版",
                },
                actor_id=2,
            )
            draft_v2 = CalibrationTemplateService.create_version(
                template["id"],
                _version_payload(revision_reason="建立第二版"),
                actor_id=1,
            )
            submitted_v2 = CalibrationTemplateService.submit_version(
                draft_v2["id"],
                {
                    "expected_version": draft_v2["row_version"],
                    "reason": "送審第二版",
                },
                actor_id=1,
            )

            approved_v2 = CalibrationTemplateService.approve_version(
                submitted_v2["id"],
                {
                    "expected_version": submitted_v2["row_version"],
                    "reason": "核准第二版",
                },
                actor_id=2,
            )

            old = db.session.get(
                CalibrationTemplateVersion,
                approved_v1["id"],
            )
            current = db.session.get(
                CalibrationTemplateVersion,
                approved_v2["id"],
            )
            persisted_template = db.session.get(
                CalibrationTemplate,
                template["id"],
            )
            assert old.status == "superseded"
            assert old.successor_version is current
            assert old.row_version == approved_v1["row_version"] + 1
            assert current.status == "approved"
            assert persisted_template.current_approved_version_id == current.id
            assert db.session.execute(
                db.select(func.count())
                .select_from(CalibrationTemplateVersion)
                .where(
                    CalibrationTemplateVersion.template_id == template["id"],
                    CalibrationTemplateVersion.status == "approved",
                )
            ).scalar_one() == 1
        finally:
            db.session.remove()
            db.engine.dispose()


def test_list_uses_bounded_pagination_and_deterministic_decimal_strings(
    db_session,
):
    actor = _user(db_session, "list_templates")
    template, _version = _create_version(db_session, actor)

    result = CalibrationTemplateService.list(
        {"page": "1", "page_size": "25", "sort": "template_code", "order": "asc"}
    )

    assert result["page"] == 1
    assert result["page_size"] == 25
    assert result["total"] == 1
    assert result["items"][0]["id"] == template["id"]
    nominal = result["items"][0]["versions"][0]["points"][0]["nominal_value"]
    assert nominal == "10"
    assert not isinstance(nominal, float)


@pytest.mark.parametrize(
    ("field", "value", "code"),
    [
        ("page", "9" * 10_000, "CALIBRATION_PAGE_INVALID"),
        ("page", str(10_001), "CALIBRATION_PAGE_INVALID"),
        ("page_size", "9" * 10_000, "CALIBRATION_PAGE_SIZE_INVALID"),
        ("page_size", "101", "CALIBRATION_PAGE_SIZE_INVALID"),
    ],
)
def test_list_rejects_huge_or_out_of_range_pagination(
    db_session,
    field,
    value,
    code,
):
    with pytest.raises(CalibrationValidationError) as error:
        CalibrationTemplateService.list({field: value})

    assert error.value.code == code
    assert error.value.details["field"] == field


def test_get_returns_not_found_with_stable_identifier(db_session):
    with pytest.raises(CalibrationNotFound) as error:
        CalibrationTemplateService.get(999_999)

    assert error.value.code == "CALIBRATION_TEMPLATE_NOT_FOUND"
    assert error.value.details == {"template_id": 999_999}
