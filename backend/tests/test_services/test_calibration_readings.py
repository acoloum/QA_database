"""校正讀值矩陣的原子保存、後端重算與輸入稽核測試。"""

from datetime import date
from decimal import Decimal
import pytest

from backend.models import (
    AuditLog,
    CalibrationTemplate,
    EquipmentCalibrationReading,
    EquipmentCalibrationRecord,
    MeasurementEquipment,
)
from backend.services.calibration_errors import CalibrationValidationError
from backend.services.calibration_service import CalibrationService
from backend.services.calibration_template_service import (
    CalibrationTemplateService,
)


def _create_two_point_draft(
    db_session, actor_id: int, approver_id: int
) -> dict:
    template = CalibrationTemplate(
        template_code="CAL-READING-ATOMIC",
        name="讀值原子性模板",
        equipment_type="游標卡尺",
        status="active",
    )
    db_session.add(template)
    db_session.flush()
    version_data = CalibrationTemplateService.create_version(
        template.id,
        {
            "procedure_code": "WI-READING",
            "procedure_name": "讀值原子性程序",
            "default_repetitions": 3,
            "environment_requirements": {},
            "allow_limited_use": False,
            "revision_reason": "原子性測試",
            "points": [
                {
                    "point_order": point_order,
                    "point_code": f"P{point_order:02d}",
                    "measurement_mode": "外徑",
                    "nominal_value": nominal,
                    "unit": "mm",
                    "reference_input_mode": "certified_value",
                    "required_repetitions": 3,
                    "error_lower_limit": "-0.05",
                    "error_upper_limit": "0.05",
                    "evaluation_basis": "all_readings",
                    "repeatability_rule": "range",
                    "repeatability_limit": "0.05",
                    "qualification_scope_code": "OD",
                    "qualification_range_start": "0",
                    "qualification_range_end": "150",
                    "uncertainty_required": False,
                    "required": True,
                }
                for point_order, nominal in ((1, "10.000"), (2, "20.000"))
            ],
        },
        actor_id=actor_id,
    )
    submitted = CalibrationTemplateService.submit_version(
        version_data["id"],
        {"expected_version": version_data["row_version"], "reason": "送審"},
        actor_id=actor_id,
    )
    version_data = CalibrationTemplateService.approve_version(
        submitted["id"],
        {"expected_version": submitted["row_version"], "reason": "核准"},
        actor_id=approver_id,
    )
    equipment = MeasurementEquipment(
        equipment_no="EQ-READING-ATOMIC",
        name="讀值原子性卡尺",
        equipment_type="游標卡尺",
        status="active",
        calibration_interval_months=12,
    )
    db_session.add(equipment)
    db_session.commit()
    return CalibrationService.create(
        {
            "equipment_id": equipment.id,
            "template_version_id": version_data["id"],
            "calibration_type": "external",
            "calibration_date": date.today().isoformat(),
        },
        actor_id=actor_id,
    )


def _point_payload(point: dict, values: tuple[str, str, str]) -> dict:
    return {
        "point_id": point["id"],
        "reference_value": point["nominal_value"],
        "readings": [
            {"trial_no": trial_no, "indicated_value": value}
            for trial_no, value in enumerate(values, start=1)
        ],
    }


def test_late_matrix_error_rolls_back_all_readings(
    db_session, calibration_users
):
    """第二點失敗時，第一點讀值、摘要、版本及 audit 都必須零寫入。"""
    actor = calibration_users["manager"]["user"]
    approver = calibration_users["approver"]["user"]
    draft = _create_two_point_draft(db_session, actor.id, approver.id)
    audit_before = db_session.query(AuditLog).count()
    payload = {
        "expected_version": draft["row_version"],
        "points": [
            _point_payload(draft["points"][0], ("10.001", "10.002", "10.003")),
            _point_payload(draft["points"][1], ("20.001", "NaN", "20.003")),
        ],
    }

    with pytest.raises(CalibrationValidationError) as exc:
        CalibrationService.save_readings(
            draft["id"], payload, actor_id=actor.id
        )

    assert exc.value.code == "CALIBRATION_FIELD_INVALID"
    assert exc.value.details["step"] == "readings"
    db_session.expire_all()
    record = db_session.get(EquipmentCalibrationRecord, draft["id"])
    assert record.row_version == draft["row_version"]
    assert record.result == "pending"
    assert record.calculation_summary == {}
    readings = (
        db_session.query(EquipmentCalibrationReading)
        .join(EquipmentCalibrationReading.calibration_point)
        .filter_by(calibration_record_id=record.id)
        .all()
    )
    assert all(reading.indicated_value is None for reading in readings)
    assert db_session.query(AuditLog).count() == audit_before


def test_complete_matrix_is_required_and_failure_is_zero_write(
    db_session, calibration_users
):
    """缺少任一校正點時應拒絕完整請求，不得更新版本。"""
    actor = calibration_users["manager"]["user"]
    approver = calibration_users["approver"]["user"]
    draft = _create_two_point_draft(db_session, actor.id, approver.id)

    with pytest.raises(CalibrationValidationError) as exc:
        CalibrationService.save_readings(
            draft["id"],
            {
                "expected_version": draft["row_version"],
                "points": [
                    _point_payload(
                        draft["points"][0],
                        ("10.001", "10.002", "10.003"),
                    )
                ],
            },
            actor_id=actor.id,
        )

    assert exc.value.details["step"] == "readings"
    assert exc.value.details["expected_count"] == 2
    db_session.expire_all()
    assert (
        db_session.get(EquipmentCalibrationRecord, draft["id"]).row_version
        == draft["row_version"]
    )


def test_trial_rows_are_updated_by_trial_number_not_payload_order(
    db_session, calibration_users
):
    """亂序 payload 仍須依 trial_no 寫入正確的預建讀值列。"""
    actor = calibration_users["manager"]["user"]
    approver = calibration_users["approver"]["user"]
    draft = _create_two_point_draft(db_session, actor.id, approver.id)
    first = draft["points"][0]
    second = draft["points"][1]
    payload = {
        "expected_version": draft["row_version"],
        "points": [
            {
                "point_id": first["id"],
                "reference_value": "10.000",
                "readings": [
                    {"trial_no": 3, "indicated_value": "10.003"},
                    {"trial_no": 1, "indicated_value": "10.001"},
                    {"trial_no": 2, "indicated_value": "10.002"},
                ],
            },
            _point_payload(second, ("20.001", "20.002", "20.003")),
        ],
    }

    result = CalibrationService.save_readings(
        draft["id"], payload, actor_id=actor.id
    )

    first_readings = {
        reading["trial_no"]: reading for reading in result["points"][0]["readings"]
    }
    assert Decimal(first_readings[1]["indicated_value"]) == Decimal("10.001")
    assert Decimal(first_readings[2]["indicated_value"]) == Decimal("10.002")
    assert Decimal(first_readings[3]["indicated_value"]) == Decimal("10.003")
    assert all(
        reading["entered_by"] == actor.id
        and reading["entered_at"] is not None
        and reading["last_modified_by"] == actor.id
        and reading["last_modified_at"] is not None
        for reading in first_readings.values()
    )
