"""MSA 與獨立校正資格服務之歷史相容契約。"""

from datetime import date, timedelta

import pytest

from backend.models import EquipmentCalibrationRecord, MeasurementEquipment
from backend.services.msa_equipment_service import MsaEquipmentService
from backend.services.msa_errors import MsaValidationError


ON_DATE = date(2026, 7, 28)


def _equipment(db_session, equipment_no: str) -> MeasurementEquipment:
    equipment = MeasurementEquipment(
        equipment_no=equipment_no,
        name="資格相容測試量具",
        status="active",
        calibration_type="external",
    )
    db_session.add(equipment)
    db_session.flush()
    return equipment


def _record(db_session, equipment, **overrides) -> EquipmentCalibrationRecord:
    values = {
        "equipment_id": equipment.id,
        "calibration_type": "external",
        "calibration_date": ON_DATE - timedelta(days=1),
        "next_due_date": ON_DATE + timedelta(days=30),
        "result": "pass",
        "status": "approved",
        "data_level": "summary_legacy",
    }
    values.update(overrides)
    record = EquipmentCalibrationRecord(**values)
    db_session.add(record)
    db_session.flush()
    return record


def test_msa_uses_new_approved_detailed_calibration_qualification(db_session):
    """防止 MSA 仍讀取舊摘要而遺失已核准詳細校正證據。"""
    equipment = _equipment(db_session, "EQ-DETAILED")
    detailed = _record(
        db_session,
        equipment,
        data_level="detailed",
        template_version_id=1,
        template_snapshot={"version": "CAL-1"},
        data_hash="a" * 64,
    )
    db_session.commit()

    qualification = MsaEquipmentService.assert_officially_usable(
        equipment.id,
        on_date=ON_DATE,
    )

    assert qualification.calibration_record_id == detailed.id
    assert qualification.data_level == "detailed"
    assert qualification.data_hash == "a" * 64


def test_msa_keeps_unexpired_legacy_pass_qualified_without_claiming_raw_evidence(
    db_session,
):
    """防止歷史摘要遭拒絕，或被誤標為可還原的詳細原始證據。"""
    equipment = _equipment(db_session, "EQ-LEGACY")
    legacy = _record(db_session, equipment)
    db_session.commit()

    qualification = MsaEquipmentService.assert_officially_usable(
        equipment.id,
        on_date=ON_DATE,
    )
    snapshot = MsaEquipmentService.build_snapshot(equipment.id, on_date=ON_DATE)

    assert qualification.calibration_record_id == legacy.id
    assert qualification.data_level == "summary_legacy"
    assert qualification.data_hash is None
    assert snapshot.calibration["data_level"] == "summary_legacy"
    assert snapshot.calibration["correction_points"] == []


@pytest.mark.parametrize("status", ["submitted", "rejected", "voided"])
def test_unapproved_detailed_calibration_never_qualifies_msa(
    db_session,
    status: str,
):
    """防止送審、退回或作廢詳細紀錄被錯當正式資格。"""
    equipment = _equipment(db_session, f"EQ-{status}")
    _record(
        db_session,
        equipment,
        status=status,
        data_level="detailed",
        template_version_id=1,
        template_snapshot={"version": "CAL-1"},
        data_hash="b" * 64,
    )
    db_session.commit()

    with pytest.raises(MsaValidationError) as error:
        MsaEquipmentService.assert_officially_usable(
            equipment.id,
            on_date=ON_DATE,
        )

    assert error.value.code == "MSA_EQUIPMENT_CALIBRATION_MISSING"


def test_latest_approved_detailed_fail_overrides_legacy_pass(db_session):
    """防止新核准失敗證據被較舊的歷史通過摘要掩蓋。"""
    equipment = _equipment(db_session, "EQ-FAIL-OVERRIDES")
    _record(
        db_session,
        equipment,
        calibration_date=ON_DATE - timedelta(days=10),
    )
    failed = _record(
        db_session,
        equipment,
        calibration_date=ON_DATE - timedelta(days=1),
        result="fail",
        data_level="detailed",
        template_version_id=1,
        template_snapshot={"version": "CAL-1"},
        data_hash="c" * 64,
    )
    db_session.commit()

    with pytest.raises(MsaValidationError) as error:
        MsaEquipmentService.assert_officially_usable(
            equipment.id,
            on_date=ON_DATE,
        )

    assert error.value.code == "MSA_EQUIPMENT_CALIBRATION_FAILED"
    assert error.value.details["calibration_record_id"] == failed.id


def test_limited_use_requires_exact_mode_from_detailed_qualification(db_session):
    """防止相近或經過修剪的量測模式越過詳細校正使用限制。"""
    equipment = _equipment(db_session, "EQ-EXACT-MODE")
    _record(
        db_session,
        equipment,
        result="limited_use",
        applicable_modes=["外徑量測"],
        restriction_conditions="只限外徑量測",
        data_level="detailed",
        template_version_id=1,
        template_snapshot={"version": "CAL-1"},
        data_hash="d" * 64,
    )
    db_session.commit()

    qualification = MsaEquipmentService.assert_officially_usable(
        equipment.id,
        on_date=ON_DATE,
        measurement_mode="外徑量測",
    )
    assert qualification.is_qualified is True

    with pytest.raises(MsaValidationError) as error:
        MsaEquipmentService.assert_officially_usable(
            equipment.id,
            on_date=ON_DATE,
            measurement_mode=" 外徑量測 ",
        )

    assert error.value.code == "MSA_EQUIPMENT_CALIBRATION_LIMITED_USE_RESTRICTED"


def test_missing_due_date_is_never_serialized_as_valid(db_session):
    """防止缺少下次校正日的詳細紀錄被設備摘要標示為有效。"""
    equipment = _equipment(db_session, "EQ-NO-DUE")
    _record(
        db_session,
        equipment,
        next_due_date=None,
        data_level="detailed",
        template_version_id=1,
        template_snapshot={"version": "CAL-1"},
        data_hash="e" * 64,
    )
    db_session.commit()

    summary = MsaEquipmentService.list({"as_of": ON_DATE.isoformat()})

    assert summary["items"][0]["calibration_status"] == "missing"
    assert summary["items"][0]["calibration_status"] != "valid"
