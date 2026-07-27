"""MSA 正式研究的設備資格與快照契約。"""

from datetime import date, timedelta
from decimal import Decimal

import pytest

from backend.models import (
    EquipmentCalibrationRecord,
    EquipmentCorrectionPoint,
    MeasurementEquipment,
)
from backend.services.msa_equipment_service import MsaEquipmentService
from backend.services.msa_errors import MsaValidationError
from backend.services.msa_errors import MsaNotFound


STUDY_DATE = date(2026, 7, 27)


def _equipment(db_session, equipment_no, **kwargs):
    equipment = MeasurementEquipment(
        equipment_no=equipment_no,
        name="MSA 測試量具",
        **kwargs,
    )
    db_session.add(equipment)
    db_session.flush()
    return equipment


def _calibration(db_session, equipment, **kwargs):
    values = {
        "equipment_id": equipment.id,
        "calibration_type": "external",
        "calibration_date": STUDY_DATE - timedelta(days=10),
        "next_due_date": STUDY_DATE + timedelta(days=30),
        "result": "pass",
        "status": "approved",
    }
    values.update(kwargs)
    record = EquipmentCalibrationRecord(**values)
    db_session.add(record)
    db_session.flush()
    return record


def test_pending_equipment_cannot_be_used_for_official_study(db_session):
    """防止待審核設備略過正式資格閘門。"""
    equipment = _equipment(
        db_session, "EQ-PENDING", status="pending_review"
    )
    db_session.commit()

    with pytest.raises(MsaValidationError) as error:
        MsaEquipmentService.assert_officially_usable(
            equipment.id, on_date=STUDY_DATE
        )

    assert error.value.code == "MSA_EQUIPMENT_PENDING_REVIEW"
    assert error.value.status_code == 422


def test_missing_equipment_returns_the_stable_not_found_contract(db_session):
    """防止正式研究引用已不存在設備時得到不穩定的底層例外。"""
    with pytest.raises(MsaNotFound) as error:
        MsaEquipmentService.assert_officially_usable(
            999_999, on_date=STUDY_DATE
        )

    assert error.value.code == "MSA_EQUIPMENT_NOT_FOUND"
    assert error.value.status_code == 404


@pytest.mark.parametrize("status", ["maintenance", "inactive", "scrapped"])
def test_blocked_equipment_status_cannot_be_used_for_official_study(
    db_session, status
):
    """防止維修或報廢量具以有效校驗紀錄通過正式研究。"""
    equipment = _equipment(db_session, f"EQ-{status}", status=status)
    _calibration(db_session, equipment)
    db_session.commit()

    with pytest.raises(MsaValidationError) as error:
        MsaEquipmentService.assert_officially_usable(
            equipment.id, on_date=STUDY_DATE
        )

    assert error.value.code == "MSA_EQUIPMENT_STATUS_BLOCKED"


def test_official_study_rejects_missing_approved_calibration(db_session):
    """防止啟用設備在沒有核准校驗證據時通過研究。"""
    equipment = _equipment(db_session, "EQ-NO-CAL", status="active")
    db_session.commit()

    with pytest.raises(MsaValidationError) as error:
        MsaEquipmentService.assert_officially_usable(
            equipment.id, on_date=STUDY_DATE
        )

    assert error.value.code == "MSA_EQUIPMENT_CALIBRATION_MISSING"


@pytest.mark.parametrize("result", ["fail", "pending"])
def test_official_study_rejects_failed_or_pending_calibration(
    db_session, result
):
    """防止最近核准校驗為失敗或待定時仍被採用。"""
    equipment = _equipment(db_session, f"EQ-CAL-{result}", status="active")
    _calibration(db_session, equipment, result=result)
    db_session.commit()

    with pytest.raises(MsaValidationError) as error:
        MsaEquipmentService.assert_officially_usable(
            equipment.id, on_date=STUDY_DATE
        )

    assert error.value.code == "MSA_EQUIPMENT_CALIBRATION_FAILED"


def test_expired_calibration_is_rejected(db_session):
    """防止研究日期晚於校驗到期日仍使用設備。"""
    equipment = _equipment(db_session, "EQ-EXPIRED", status="active")
    _calibration(
        db_session,
        equipment,
        next_due_date=STUDY_DATE - timedelta(days=1),
    )
    db_session.commit()

    with pytest.raises(MsaValidationError) as error:
        MsaEquipmentService.assert_officially_usable(
            equipment.id, on_date=STUDY_DATE
        )

    assert error.value.code == "MSA_EQUIPMENT_CALIBRATION_EXPIRED"


def test_latest_approved_calibration_overrides_an_older_pass_record(db_session):
    """防止服務錯選舊的通過校驗而略過最新失敗證據。"""
    equipment = _equipment(db_session, "EQ-LATEST", status="active")
    _calibration(
        db_session,
        equipment,
        calibration_date=STUDY_DATE - timedelta(days=20),
        result="pass",
    )
    _calibration(
        db_session,
        equipment,
        calibration_date=STUDY_DATE - timedelta(days=1),
        result="fail",
    )
    db_session.commit()

    with pytest.raises(MsaValidationError) as error:
        MsaEquipmentService.assert_officially_usable(
            equipment.id, on_date=STUDY_DATE
        )

    assert error.value.code == "MSA_EQUIPMENT_CALIBRATION_FAILED"


def test_limited_use_requires_an_exact_matching_measurement_mode(db_session):
    """防止受限校驗被套用到未核准的量測模式。"""
    equipment = _equipment(db_session, "EQ-LIMITED", status="active")
    _calibration(
        db_session,
        equipment,
        result="limited_use",
        applicable_modes=["內徑量測", " 外徑量測 "],
        restriction_conditions="僅限既定量程",
    )
    db_session.commit()

    eligible = MsaEquipmentService.assert_officially_usable(
        equipment.id, on_date=STUDY_DATE, measurement_mode="外徑量測"
    )
    snapshot = MsaEquipmentService.build_snapshot(
        equipment.id, on_date=STUDY_DATE, measurement_mode="外徑量測"
    )

    assert eligible.eligible is True
    assert eligible.limitation == "僅限既定量程"
    assert snapshot.calibration["applicable_modes"] == ["內徑量測", "外徑量測"]
    assert snapshot.calibration["restriction_conditions"] == "僅限既定量程"

    with pytest.raises(MsaValidationError) as error:
        MsaEquipmentService.assert_officially_usable(
            equipment.id, on_date=STUDY_DATE, measurement_mode="厚度量測"
        )

    assert error.value.code == "MSA_EQUIPMENT_CALIBRATION_LIMITED_USE_RESTRICTED"
    assert error.value.status_code == 422


def test_limited_use_rejects_blank_structured_modes(db_session):
    """防止非空 JSON 陣列內仍以空白字串繞過模式限制。"""
    equipment = _equipment(db_session, "EQ-LIMITED-BLANK", status="active")
    record = _calibration(
        db_session,
        equipment,
        result="limited_use",
        applicable_modes=["內徑量測"],
    )
    db_session.commit()
    equipment_id = equipment.id
    record.applicable_modes = ["  "]

    with db_session.no_autoflush:
        with pytest.raises(MsaValidationError) as error:
            MsaEquipmentService.assert_officially_usable(
                equipment_id, on_date=STUDY_DATE, measurement_mode="內徑量測"
            )

    assert error.value.code == "MSA_EQUIPMENT_CALIBRATION_LIMITED_USE_RESTRICTED"


def test_exempt_equipment_requires_reason_and_snapshots_it(db_session):
    """防止缺少豁免依據的設備通過，或快照遺失豁免追溯資料。"""
    equipment = _equipment(
        db_session,
        "EQ-EXEMPT",
        status="active",
        calibration_type="exempt",
        calibration_exemption_reason="依內控規範免校驗",
        resolution=Decimal("0.01"),
        unit="mm",
    )
    db_session.commit()

    eligible = MsaEquipmentService.assert_officially_usable(
        equipment.id, on_date=STUDY_DATE
    )
    snapshot = MsaEquipmentService.build_snapshot(
        equipment.id, on_date=STUDY_DATE
    )

    assert eligible.eligible is True
    assert eligible.calibration_record_id is None
    assert snapshot.calibration["exemption_reason"] == "依內控規範免校驗"
    assert snapshot.calibration["applicable_modes"] == []


def test_exempt_equipment_rejects_blank_reason_even_before_persistence(
    db_session,
):
    """防止上游尚未寫入時，空白豁免理由被 service 當成有效證據。"""
    equipment = _equipment(
        db_session,
        "EQ-EXEMPT-BLANK",
        status="active",
        calibration_type="exempt",
        calibration_exemption_reason="有效豁免理由",
    )
    db_session.commit()
    equipment_id = equipment.id
    equipment.calibration_exemption_reason = "  "

    with db_session.no_autoflush:
        with pytest.raises(MsaValidationError) as error:
            MsaEquipmentService.assert_officially_usable(
                equipment_id, on_date=STUDY_DATE
            )

    assert error.value.code == "MSA_EQUIPMENT_EXEMPTION_REASON_MISSING"


def test_passing_calibration_returns_snapshot_with_correction_evidence(db_session):
    """防止資格通過時遺失設備身分、校驗與逐點補正證據。"""
    equipment = _equipment(
        db_session,
        "EQ-PASS",
        status="active",
        resolution=Decimal("0.001"),
        unit="mm",
    )
    record = _calibration(
        db_session,
        equipment,
        certificate_no="CERT-100",
        traceability_standard="CNS 1234",
        uncertainty_statement="U=0.002 mm",
    )
    db_session.add(
        EquipmentCorrectionPoint(
            calibration_record_id=record.id,
            measurement_mode="外徑量測",
            nominal_value=Decimal("10.000"),
            indicated_value=Decimal("10.002"),
            error_value=Decimal("0.002"),
            correction_value=Decimal("-0.002"),
            unit="mm",
        )
    )
    db_session.commit()

    eligible = MsaEquipmentService.assert_officially_usable(
        equipment.id, on_date=STUDY_DATE
    )
    snapshot = MsaEquipmentService.build_snapshot(
        equipment.id, on_date=STUDY_DATE
    )

    assert eligible.calibration_record_id == record.id
    assert snapshot.equipment_no == "EQ-PASS"
    assert snapshot.resolution == Decimal("0.001")
    assert snapshot.calibration == {
        "record_id": record.id,
        "calibration_type": "external",
        "calibration_date": STUDY_DATE - timedelta(days=10),
        "effective_date": None,
        "next_due_date": STUDY_DATE + timedelta(days=30),
        "result": "pass",
        "status": "approved",
        "certificate_no": "CERT-100",
        "traceability_standard": "CNS 1234",
        "uncertainty_statement": "U=0.002 mm",
        "applicable_modes": [],
        "restriction_conditions": None,
        "exemption_reason": None,
        "correction_points": [
            {
                "id": 1,
                "measurement_mode": "外徑量測",
                "nominal_value": Decimal("10.000"),
                "indicated_value": Decimal("10.002"),
                "error_value": Decimal("0.002"),
                "correction_value": Decimal("-0.002"),
                "unit": "mm",
                "range_start": None,
                "range_end": None,
            }
        ],
    }
